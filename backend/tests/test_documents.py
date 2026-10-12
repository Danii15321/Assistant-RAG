import hashlib
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, text

from app.adapters.storage import PrivateStorage
from app.config import Settings
from app.models.document import DocumentError, UploadRequest
from app.repositories.documents import DocumentRepository, enqueue
from app.repositories.identity import IdentityRepository
from app.repositories.jobs import JobRepository
from app.services.documents import DocumentService
from app.services.extraction import ExtractedUnit
from app.worker.consumer import Consumer

pytestmark = pytest.mark.integration


@pytest.fixture
def context(database: tuple[Engine, Config], tmp_path: Path):
    engine, config = database
    command.upgrade(config, "head")
    with engine.begin() as c:
        for name in ["alice", "bob"]:
            c.execute(
                text(
                    'INSERT INTO auth_user (id,name,email,"emailVerified",username) VA'
                    "LUES (:n,:n,:email,false,:n)"
                ),
                {"n": name, "email": name + "@accounts.invalid"},
            )
            c.execute(
                text(
                    'INSERT INTO auth_session (id,"userId",token,"expiresAt","updatedA'
                    "t\") VALUES (:n,:n,:n,now()+interval '1 day',now())"
                ),
                {"n": name},
            )
    identities = IdentityRepository(engine)
    owners = [identities.current_user(n).id for n in ["alice", "bob"]]
    repo = DocumentRepository(engine)
    storage = PrivateStorage(tmp_path / "private")
    service = DocumentService(repo, storage, Settings())
    jobs = JobRepository(engine)
    return engine, owners, repo, storage, service, jobs, Consumer(jobs, storage)


def uploaded(context, owner_index=0, content=b"Premiere ligne.\n\nTroisieme ligne."):
    _, owners, repo, storage, service, _, _ = context
    doc, token = service.reserve(
        owners[owner_index],
        ["alice", "bob"][owner_index],
        UploadRequest(filename="notes.txt", size_bytes=len(content), content_type="text/plain"),
    )
    service.uploads.begin_upload(doc.id, hashlib.sha256(token.encode()).hexdigest())
    path = storage.temporary()
    path.write_bytes(content)
    service.uploads.complete_upload(
        doc.id,
        hashlib.sha256(token.encode()).hexdigest(),
        len(content),
        lambda: storage.commit(path, doc.id),
    )
    path.unlink()
    return doc


def test_transactional_delivery_deduplication_owner_and_cleanup(context):
    engine, owners, repo, storage, service, jobs, worker = context
    doc = uploaded(context)
    result, duplicate = service.finalize(owners[0], doc.id)
    assert result.state == "queued" and not duplicate
    assert service.finalize(owners[0], doc.id)[0].id == doc.id
    with engine.begin() as c:
        enqueue(c, doc.id, owners[0], "extract", 1)
        assert c.execute(text("SELECT count(*) FROM ingestion_jobs")).scalar_one() == 1
    assert worker.run_once()
    result = repo.get(owners[0], doc.id)
    assert result.stage == "extracted" and result.state != "ready"
    assert [(u.number, u.text) for u in repo.units(owners[0], doc.id, 0, 50)] == [
        (1, "Premiere ligne."),
        (3, "Troisieme ligne."),
    ]
    assert not worker.run_once()
    other = uploaded(context)
    assert service.finalize(owners[0], other.id) == (result, True)
    separate = uploaded(context, 1)
    assert service.finalize(owners[1], separate.id)[0].id != doc.id
    for action in [
        lambda: repo.get(owners[1], doc.id),
        lambda: repo.units(owners[1], doc.id, 0, 10),
        lambda: repo.retry(owners[1], doc.id),
        lambda: repo.delete(owners[1], doc.id),
    ]:
        with pytest.raises(DocumentError) as e:
            action()
        assert e.value.status == 404
    repo.delete(owners[0], doc.id)
    repo.delete(owners[0], doc.id)
    assert all(d.id != doc.id for d in repo.list_documents(owners[0], 0, 50))
    while worker.run_once():
        pass
    assert not storage.path(doc.id).exists() and not storage.path(other.id).exists()
    assert repo.get(owners[1], separate.id).stage == "extracted"
    with engine.connect() as c:
        assert (
            c.execute(
                text("SELECT count(*) FROM extracted_units WHERE document_id=:id"), {"id": doc.id}
            ).scalar_one()
            == 0
        )


def test_interruption_lease_fencing_and_deletion_during_extraction(context):
    engine, owners, repo, storage, service, jobs, worker = context
    doc = uploaded(context)
    service.finalize(owners[0], doc.id)
    stale = jobs.claim()
    assert stale and jobs.claim() is None
    with engine.begin() as c:
        c.execute(text("UPDATE ingestion_jobs SET lease_until=now()-interval '1 second'"))
    current = jobs.claim()
    assert current and current["attempts"] == 2
    assert not jobs.finish(stale, [ExtractedUnit("line", 1, "obsolete")])
    repo.delete(owners[0], doc.id)
    assert not jobs.finish(current, [ExtractedUnit("line", 1, "obsolete")])
    assert worker.run_once()
    assert not storage.path(doc.id).exists()
    with engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM extracted_units")).scalar_one() == 0


def test_failed_retry_is_idempotent_and_attempts_bounded(context):
    engine, owners, repo, storage, service, jobs, worker = context
    doc = uploaded(context, content=b"\xff")
    service.finalize(owners[0], doc.id)
    assert worker.run_once()
    assert repo.get(owners[0], doc.id).error_code == "invalid_encoding"
    repo.retry(owners[0], doc.id)
    repo.retry(owners[0], doc.id)
    with engine.connect() as c:
        assert (
            c.execute(
                text("SELECT count(*) FROM ingestion_jobs WHERE status='pending'")
            ).scalar_one()
            == 1
        )
    for _ in range(3):
        job = jobs.claim()
        assert job
        jobs.finish(job, error="storage_unavailable", transient=True)
    assert repo.get(owners[0], doc.id).state == "failed"
    assert jobs.claim() is None


def test_abandoned_upload_capability_revocation_and_orphans(context):
    engine, owners, repo, storage, service, jobs, worker = context
    doc, token = service.reserve(
        owners[0], "alice", UploadRequest(filename="x.txt", size_bytes=5, content_type="text/plain")
    )
    with pytest.raises(DocumentError):
        service.uploads.begin_upload(doc.id, hashlib.sha256(b"wrong").hexdigest())
    with engine.begin() as c:
        c.execute(text("DELETE FROM auth_session WHERE id=:id"), {"id": "alice"})
    with pytest.raises(DocumentError):
        service.uploads.begin_upload(doc.id, hashlib.sha256(token.encode()).hexdigest())
    with engine.begin() as c:
        c.execute(text("UPDATE documents SET expires_at=now()-interval '1 second'"))
    expired, expired_token = service.reserve(
        owners[1],
        "bob",
        UploadRequest(filename="expired.txt", size_bytes=5, content_type="text/plain"),
    )
    with engine.begin() as c:
        c.execute(
            text("UPDATE documents SET expires_at=now()-interval '1 second' WHERE id=:id"),
            {"id": expired.id},
        )
    with pytest.raises(DocumentError):
        service.uploads.begin_upload(expired.id, hashlib.sha256(expired_token.encode()).hexdigest())
    jobs.reconcile()
    assert worker.run_once()
    assert worker.run_once()
    assert repo.list_documents(owners[0], 0, 50) == []
    orphan = storage.path(uuid4())
    orphan.write_text("private")
    part = storage.temporary()
    assert storage.collect_orphans(jobs.reconcile(), grace_seconds=0) == 2
    assert not part.exists()


def test_validation_size_quota_and_exact_twenty_mebibyte_upload(context):
    engine, owners, repo, storage, service, jobs, worker = context
    for filename, mime, size, status in [
        ("../x.txt", "text/plain", 5, 400),
        ("x.exe", "application/octet-stream", 5, 415),
        ("x.pdf", "text/plain", 5, 415),
        ("x.txt", "text/plain", 20 * 1024 * 1024 + 1, 413),
    ]:
        with pytest.raises(DocumentError) as e:
            service.reserve(
                owners[0],
                "alice",
                UploadRequest(filename=filename, content_type=mime, size_bytes=size),
            )
        assert e.value.status == status
    prefix = b"Vingt Mio.\n"
    doc = uploaded(context, content=prefix + b" " * (20 * 1024 * 1024 - len(prefix)))
    assert service.finalize(owners[0], doc.id)[0].size_bytes == 20 * 1024 * 1024
    assert worker.run_once()
    assert repo.get(owners[0], doc.id).stage == "extracted"
    assert repo.units(owners[0], doc.id, 0, 50)[0].text == "Vingt Mio."
    with engine.begin() as c:
        c.execute(text("UPDATE documents SET size_bytes=100*1024*1024"))
    with pytest.raises(DocumentError) as e:
        service.reserve(
            owners[0],
            "alice",
            UploadRequest(filename="x.txt", size_bytes=1, content_type="text/plain"),
        )
    assert e.value.code == "storage_quota"


def test_concurrent_reservations_and_owner_foreign_keys(context):
    from concurrent.futures import ThreadPoolExecutor

    from sqlalchemy.exc import IntegrityError

    engine, owners, repo, storage, _, jobs, worker = context
    service = DocumentService(repo, storage, Settings(user_storage_bytes=10))

    def reserve_one(index):
        try:
            service.reserve(
                owners[0],
                "alice",
                UploadRequest(filename=f"{index}.txt", size_bytes=6, content_type="text/plain"),
            )
            return "accepted"
        except DocumentError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(reserve_one, range(4)))
    assert results.count("accepted") == 1
    assert results.count("storage_quota") == 3
    doc = repo.list_documents(owners[0], 0, 50)[0]
    with pytest.raises(IntegrityError), engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO extracted_units (document_id,owner_id,ordin"
                "al,kind,number,text) VALUES (:id,:owner,1,'line',1,'for"
                "ged')"
            ),
            {"id": doc.id, "owner": owners[1]},
        )
