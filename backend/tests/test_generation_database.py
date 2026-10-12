from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.models.document import DocumentError
from app.repositories.generation import GenerationRepository

pytest_plugins = ["test_documents"]
pytestmark = pytest.mark.integration


def test_generation_global_lease_atomic_reservations_and_stale_release(context):
    engine, owners, *_ = context
    repo = GenerationRepository(engine)
    with ThreadPoolExecutor(max_workers=2) as pool:

        def reserve(index):
            try:
                return repo.acquire(owners[index], ["alice", "bob"][index], 3100)
            except DocumentError as e:
                return e.code

        result = list(pool.map(reserve, [0, 1]))
    claimed = [r for r in result if not isinstance(r, str)]
    assert len(claimed) == 1 and "generation_busy" in result
    lease, attempt = claimed[0]
    repo.finish_attempt(attempt, "failed")
    repo.release(uuid4())
    with pytest.raises(DocumentError, match="generation_busy"):
        repo.acquire(owners[0], "alice", 3100)
    repo.release(lease)
    lease, attempt = repo.acquire(owners[0], "alice", 3100)
    repo.release(lease)
    with pytest.raises(DocumentError, match="generation_quota"):
        repo.acquire(owners[0], "alice", 3100)
    with engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM generation_attempts")).scalar_one() == 2


def test_generation_daily_limits_retries_session_and_provider_cooldown(context):
    engine, owners, *_ = context
    repo = GenerationRepository(engine)
    with pytest.raises(DocumentError, match="session_expired"):
        repo.acquire(owners[0], "bob", 3100)
    lease, attempt = repo.acquire(owners[0], "alice", 3100)
    retry = repo.reserve(owners[0], "alice", lease, 3100)
    assert retry != attempt
    with pytest.raises(DocumentError, match="generation_quota"):
        repo.reserve(owners[0], "alice", lease, 3100)
    repo.block(60)
    repo.release(lease)
    with pytest.raises(DocumentError, match="provider_quota"):
        repo.acquire(owners[1], "bob", 3100)
    with engine.begin() as c:
        c.execute(text("UPDATE generation_limits SET blocked_until=NULL"))
        c.execute(text("UPDATE generation_attempts SET created_at=now()-interval '2 minutes'"))
        for _ in range(8):
            c.execute(
                text(
                    "INSERT INTO generation_attempts(id,owner_id,reserved_tokens,outcome) "
                    "VALUES (:id,:owner,3100,'failed')"
                ),
                {"id": uuid4(), "owner": owners[0]},
            )
    with pytest.raises(DocumentError, match="generation_quota"):
        repo.acquire(owners[0], "alice", 3100)
    with engine.begin() as c:
        c.execute(text("UPDATE generation_attempts SET created_at=now()-interval '2 minutes'"))
        c.execute(text("DELETE FROM generation_attempts"))
        for _ in range(50):
            c.execute(
                text(
                    "INSERT INTO generation_attempts(id,owner_id,reserved_tokens,outcome) "
                    "VALUES (:id,:owner,3100,'failed')"
                ),
                {"id": uuid4(), "owner": owners[1]},
            )
        c.execute(text("UPDATE generation_attempts SET created_at=now()-interval '2 minutes'"))
    with pytest.raises(DocumentError, match="generation_quota"):
        repo.acquire(owners[0], "alice", 3100)


def test_generation_migration_is_additive_and_rollback_preserves_sessions(context, database):
    from alembic import command

    engine, config = database
    _, owners, *_ = context
    repo = GenerationRepository(engine)
    repo.acquire(owners[0], "alice", 3100)
    command.downgrade(config, "0005_search")
    command.upgrade(config, "head")
    with engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM generation_attempts")).scalar_one() == 0
        assert c.execute(text("SELECT count(*) FROM auth_session")).scalar_one() == 2


def test_expired_generation_lease_cannot_release_replacement(context):
    engine, owners, *_ = context
    repo = GenerationRepository(engine)
    old, _ = repo.acquire(owners[0], "alice", 3100)
    with engine.begin() as c:
        c.execute(text("UPDATE generation_limits SET lease_until=now()-interval '1 second'"))
    current, _ = repo.acquire(owners[1], "bob", 3100)
    assert not repo.active(old) and repo.active(current)
    repo.release(old)
    assert repo.active(current)
    repo.release(current)


def test_sent_sources_are_reverified_after_deletion_and_owner_isolation(context):
    from test_indexation import vectors
    from test_search_database import ready

    from app.repositories.search import SearchRepository

    engine, owners, documents, *_ = context
    doc = ready(context)
    repo = SearchRepository(engine)
    hits = repo.candidates(owners[0], [doc.id], vectors(1)[0])
    repo.verify_hits(owners[0], hits)
    with pytest.raises(DocumentError, match="source_unavailable"):
        repo.verify_hits(owners[1], hits)
    documents.delete(owners[0], doc.id)
    with pytest.raises(DocumentError, match="source_unavailable"):
        repo.verify_hits(owners[0], hits)
