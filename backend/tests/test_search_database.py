from uuid import uuid4

import pytest
from sqlalchemy import text
from test_documents import uploaded
from test_indexation import prepared, vectors

from app.models.document import DocumentError
from app.repositories.query_jobs import QueryJobRepository
from app.repositories.search import SearchRepository

pytest_plugins = ["test_documents"]
pytestmark = pytest.mark.integration


def ready(context):
    doc, job, index, chunks = prepared(context)
    index.save(job, [c.ordinal for c in chunks], vectors(len(chunks)))
    return doc


def test_cosine_search_filters_owner_selection_state_and_version_before_ranking(context):
    engine, owners, repo, _, service, jobs, worker = context
    doc = ready(context)
    search = SearchRepository(engine)
    assert search.validate_selection(owners[0], None)
    assert not search.validate_selection(owners[1], None)
    assert len(search.candidates(owners[0], [doc.id], vectors(1)[0])) > 0
    assert search.candidates(owners[1], None, vectors(1)[0]) == []
    for selection in [[doc.id], [uuid4()]]:
        with pytest.raises(DocumentError) as error:
            search.validate_selection(owners[1], selection)
        assert error.value.status == 404
    pending = uploaded(context, content=b"Pending")
    with pytest.raises(DocumentError, match="selection_unavailable"):
        search.validate_selection(owners[0], [pending.id])
    with engine.begin() as c:
        c.execute(
            text("UPDATE documents SET index_version='obsolete' WHERE id=:id"), {"id": doc.id}
        )
    assert search.candidates(owners[0], None, vectors(1)[0]) == []
    with pytest.raises(DocumentError, match="selection_unavailable"):
        search.validate_selection(owners[0], [doc.id])


def test_deleted_selection_is_not_silently_widened_and_scores_are_real(context):
    engine, owners, repo, _, _, _, _ = context
    doc = ready(context)
    search = SearchRepository(engine)
    hits = search.candidates(owners[0], None, vectors(1)[0])
    assert all(abs(h.score - 1) < 0.00001 for h in hits)
    repo.delete(owners[0], doc.id)
    assert search.candidates(owners[0], None, vectors(1)[0]) == []
    with pytest.raises(DocumentError, match="selection_unavailable"):
        search.candidates(owners[0], [doc.id], vectors(1)[0])
    with pytest.raises(DocumentError, match="selection_unavailable"):
        search.validate_selection(owners[0], [doc.id])


def test_query_queue_owner_quota_lease_fencing_cleanup_and_revocation(context):
    engine, owners, *_ = context
    jobs = QueryJobRepository(engine)
    identifier = jobs.submit(owners[0], "alice", "Une question")
    assert jobs.result(owners[1], identifier) is None
    with pytest.raises(DocumentError, match="search_busy"):
        jobs.submit(owners[0], "alice", "Autre")
    first = jobs.claim()
    assert first and jobs.claim() is None
    with engine.begin() as c:
        c.execute(
            text("UPDATE search_jobs SET lease_until=now()-interval '1 second' WHERE id=:id"),
            {"id": identifier},
        )
    current = jobs.claim()
    assert current and not jobs.finish(first, vectors(1)[0])
    assert jobs.finish(current, vectors(1)[0])
    assert jobs.result(owners[0], identifier)["status"] == "done"
    jobs.remove(owners[0], identifier)
    assert jobs.result(owners[0], identifier) is None
    identifier = jobs.submit(owners[0], "alice", "Une question")
    current = jobs.claim()
    with engine.begin() as c:
        c.execute(text("DELETE FROM auth_session WHERE id='alice'"))
    assert not jobs.finish(current, vectors(1)[0])
    assert jobs.result(owners[0], identifier) is None


def test_query_jobs_and_ingestion_share_the_cpu_lease(context):
    engine, owners, _, _, service, ingestion, _ = context
    doc = uploaded(context)
    service.finalize(owners[0], doc.id)
    query = QueryJobRepository(engine)
    identifier = query.submit(owners[0], "alice", "Question")
    running = query.claim()
    assert running and ingestion.claim() is None
    query.finish(running, vectors(1)[0])
    index = ingestion.claim()
    assert index
    query.remove(owners[0], identifier)
    query.submit(owners[0], "alice", "Autre")
    assert query.claim() is None


def test_global_queue_cap_expiry_and_session_owner_binding(context):
    from app.repositories.identity import IdentityRepository

    engine, owners, *_ = context
    jobs = QueryJobRepository(engine)
    with pytest.raises(DocumentError, match="session_expired"):
        jobs.submit(owners[0], "bob", "Question")
    for number in range(9):
        subject = f"quota{number}"
        with engine.begin() as c:
            c.execute(
                text(
                    'INSERT INTO auth_user(id,name,email,"emailVerified",userna'
                    "me) VALUES (:s,:s,:e,false,:s)"
                ),
                {"s": subject, "e": subject + "@accounts.invalid"},
            )
            c.execute(
                text(
                    'INSERT INTO auth_session(id,"userId",token,"expiresAt","up'
                    "datedAt\") VALUES (:s,:s,:s,now()+interval '1 day',now())"
                ),
                {"s": subject},
            )
        owner = IdentityRepository(engine).current_user(subject).id
        if number < 8:
            jobs.submit(owner, subject, "Question")
        else:
            with pytest.raises(DocumentError, match="search_busy"):
                jobs.submit(owner, subject, "Question")
    with engine.begin() as c:
        c.execute(text("UPDATE search_jobs SET expires_at=now()-interval '1 second'"))
    identifier = jobs.submit(owners[0], "alice", "Nouvelle question")
    with engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM search_jobs")).scalar_one() == 1
    jobs.remove(owners[0], identifier)


def test_search_migration_rollback_preserves_published_indexes(context, database):
    from alembic import command

    engine, config = database
    _, owners, *_ = context
    doc = ready(context)
    jobs = QueryJobRepository(engine)
    jobs.submit(owners[0], "alice", "Question")
    with engine.connect() as c:
        before = c.execute(
            text("SELECT embedding::text FROM index_chunks WHERE document_id=:id ORDER BY ordinal"),
            {"id": doc.id},
        ).all()
    command.downgrade(config, "0004_indexes")
    command.upgrade(config, "head")
    with engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM search_jobs")).scalar_one() == 0
        assert (
            c.execute(
                text(
                    "SELECT embedding::text FROM index_chunks WHERE "
                    "document_id=:id ORDER BY ordinal"
                ),
                {"id": doc.id},
            ).all()
            == before
        )
    with engine.begin() as c:
        c.execute(text("DELETE FROM documents WHERE id=:id"), {"id": doc.id})


def test_cpu_guard_survives_search_cancellation_and_session_revocation(context):
    from app.worker.cpu_guard import cpu_guard

    engine, owners, *_ = context
    jobs = QueryJobRepository(engine)
    identifier = jobs.submit(owners[0], "alice", "Question")
    with pytest.raises(RuntimeError, match="interrupted"):
        with cpu_guard(engine) as acquired:
            assert acquired
            running = jobs.claim()
            assert running
            jobs.remove(owners[0], identifier)
            with cpu_guard(engine) as second:
                assert not second
            with engine.begin() as c:
                c.execute(text("DELETE FROM auth_session WHERE id='alice'"))
            with cpu_guard(engine) as second:
                assert not second
            assert not jobs.finish(running, vectors(1)[0])
            raise RuntimeError("interrupted")
    with cpu_guard(engine) as acquired:
        assert acquired
