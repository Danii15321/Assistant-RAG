import math

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from test_chunking import WordTokenizer
from test_documents import uploaded

from app.models.document import DocumentError
from app.repositories.indexes import IndexRepository
from app.services.chunking import split_units
from app.services.embeddings import INDEX_VERSION, validate_vectors
from app.services.extraction import ExtractedUnit

pytest_plugins = ["test_documents"]

pytestmark = pytest.mark.integration


def prepared(context):
    engine, owners, repo, storage, service, jobs, worker = context
    doc = uploaded(context)
    service.finalize(owners[0], doc.id)
    assert worker.run_once()
    job = jobs.claim()
    assert job and job["kind"] == "index"
    index = IndexRepository(engine)
    chunks = split_units([ExtractedUnit("line", 1, "mot " * 600)], WordTokenizer())
    assert index.prepare(job, chunks)
    return doc, job, index, chunks


def vectors(count):
    return [[1.0] + [0.0] * 383 for _ in range(count)]


def test_atomic_publication_checkpoint_recovery_and_owner_isolation(context):
    engine, owners, repo, _, _, jobs, _ = context
    doc, first, index, chunks = prepared(context)
    assert repo.passages(owners[0], doc.id, 0, 50) == []
    batch = index.batch(first, 1)
    assert index.save(first, [batch[0]["ordinal"]], vectors(1))
    assert repo.get(owners[0], doc.id).state != "ready"
    resumed = jobs.claim()
    assert resumed and resumed["attempts"] == 1
    assert not index.save(first, [chunks[-1].ordinal], vectors(1))
    assert index.prepare(resumed, chunks)
    batch = index.batch(resumed, 16)
    assert len(batch) == len(chunks) - 1
    assert index.save(resumed, [c["ordinal"] for c in batch], vectors(len(batch)))
    ready = repo.get(owners[0], doc.id)
    assert ready.state == "ready" and ready.chunk_count == ready.embedded_count == len(chunks)
    assert ready.index_version == INDEX_VERSION
    assert len(repo.passages(owners[0], doc.id, 0, 50)) == len(chunks)
    with pytest.raises(DocumentError) as error:
        repo.passages(owners[1], doc.id, 0, 50)
    assert error.value.status == 404
    with engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM index_chunks")).scalar_one() == len(chunks)


def test_expired_lease_and_deletion_cannot_publish(context):
    engine, owners, repo, storage, _, jobs, worker = context
    doc, stale, index, chunks = prepared(context)
    with engine.begin() as c:
        c.execute(
            text("UPDATE ingestion_jobs SET lease_until=now()-interval '1 second' WHERE id=:id"),
            stale,
        )
    current = jobs.claim()
    assert current
    assert not index.save(stale, [1], vectors(1))
    repo.delete(owners[0], doc.id)
    assert not index.save(current, [1], vectors(1))
    assert repo.list_documents(owners[0], 0, 50) == []
    assert worker.run_once()
    with engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM index_chunks")).scalar_one() == 0
        assert c.execute(text("SELECT count(*) FROM index_runs")).scalar_one() == 0
    assert not storage.path(doc.id).exists()


def test_shared_passage_quota_and_owner_foreign_key(context):
    engine, owners, repo, _, service, jobs, worker = context
    doc, job, index, chunks = prepared(context)
    with pytest.raises(IntegrityError), engine.begin() as c:
        c.execute(
            text("UPDATE index_chunks SET owner_id=:owner WHERE document_id=:id"),
            {"id": doc.id, "owner": owners[1]},
        )
    index.fail(job, "embedding_unavailable")
    second = uploaded(context, content=b"Un autre texte.")
    service.finalize(owners[0], second.id)
    assert worker.run_once()
    next_job = jobs.claim()
    assert next_job
    with pytest.raises(DocumentError, match="passage_quota"):
        IndexRepository(engine, user_limit=len(chunks), global_limit=len(chunks)).prepare(
            next_job, chunks
        )
    assert repo.get(owners[0], second.id).chunk_count == 0


def test_failed_index_retry_keeps_checkpoint_and_fences_incompatible_version(context):
    engine, owners, repo, _, _, jobs, _ = context
    doc, job, index, chunks = prepared(context)
    batch = index.batch(job, 1)
    index.save(job, [batch[0]["ordinal"]], vectors(1))
    job = jobs.claim()
    index.fail(job, "embedding_unavailable")
    assert repo.get(owners[0], doc.id).state == "failed"
    repo.retry(owners[0], doc.id)
    repo.retry(owners[0], doc.id)
    job = jobs.claim()
    assert job and job["kind"] == "index" and job["generation"] == 1
    assert len(index.batch(job, 16)) == len(chunks) - 1
    with engine.begin() as c:
        c.execute(text("UPDATE index_runs SET index_version='incompatible'"))
    with pytest.raises(DocumentError, match="index_incompatible"):
        index.prepare(job, chunks)


def test_malformed_vectors_are_rejected_before_checkpoint(context):
    _, _, _, _, _, _, _ = context
    doc, job, index, chunks = prepared(context)
    for invalid in [[[0.0] * 384], [[math.nan] + [0.0] * 383], [[1.0] * 383]]:
        with pytest.raises(ValueError):
            index.save(job, [1], invalid)
    assert len(index.batch(job, 16)) == len(chunks)


def test_l2_and_batch_size_validation():
    validate_vectors(vectors(2), 2)
    for invalid in [vectors(1), [[2.0] + [0.0] * 383] * 2]:
        with pytest.raises(ValueError):
            validate_vectors(invalid, 2)


def test_additive_migration_enqueues_existing_extracted_documents(context, database):
    from alembic import command

    engine, config = database
    _, owners, repo, _, service, jobs, worker = context
    command.downgrade(config, "0003_documents")
    # The previous schema and its extraction are retained, as on a step-3 installation.
    with engine.begin() as c:
        from uuid import uuid4

        identifier = uuid4()
        c.execute(
            text(
                "INSERT INTO documents (id,owner_id,filename,extension,content_type,size_bytes,"
                "state,stage,unit_count,parser_version,expires_at,session_id) VALUES "
                "(:id,:owner,'existing.txt','txt',"
                "'text/plain',8,'processing','extracted',1,'previous-parser',now(),'alice')"
            ),
            {"id": identifier, "owner": owners[0]},
        )
        c.execute(
            text(
                "INSERT INTO extracted_units (document_id,owner_id,ordinal,kind,number,text) "
                "VALUES (:id,:owner,1,'line',4,'Préservé')"
            ),
            {"id": identifier, "owner": owners[0]},
        )
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    assert repo.get(owners[0], identifier).parser_version == "previous-parser"
    assert repo.units(owners[0], identifier, 0, 10)[0].number == 4
    with engine.connect() as c:
        assert (
            c.execute(text("SELECT count(*) FROM ingestion_jobs WHERE kind='index'")).scalar_one()
            == 1
        )
    assert jobs.claim()["kind"] == "index"
    with engine.begin() as c:
        c.execute(
            text("DELETE FROM documents WHERE id=:id AND owner_id=:owner"),
            {"id": identifier, "owner": owners[0]},
        )


def test_downgrade_keeps_extraction_usable_and_upgrade_requeues_partial_index(context, database):
    from alembic import command

    engine, config = database
    _, owners, repo, _, _, _, _ = context
    doc, job, index, chunks = prepared(context)
    index.save(job, [1], vectors(1))
    command.downgrade(config, "0003_documents")
    with engine.connect() as c:
        state, stage = c.execute(
            text("SELECT state,stage FROM documents WHERE id=:id"), {"id": doc.id}
        ).one()
        assert state == "processing" and stage == "extracted"
        assert c.execute(text("SELECT count(*) FROM extracted_units")).scalar_one() == 2
    command.upgrade(config, "head")
    assert repo.get(owners[0], doc.id).embedded_count == 0
    with engine.connect() as c:
        assert (
            c.execute(
                text("SELECT count(*) FROM ingestion_jobs WHERE kind='index' AND status='pending'")
            ).scalar_one()
            == 1
        )
        assert c.execute(text("SELECT count(*) FROM index_chunks")).scalar_one() == 0
    with engine.begin() as c:
        c.execute(
            text("DELETE FROM documents WHERE id=:id AND owner_id=:owner"),
            {"id": doc.id, "owner": owners[0]},
        )
