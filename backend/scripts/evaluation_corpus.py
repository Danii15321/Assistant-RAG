"""Private synthetic evaluation corpus; never main/test DB, never final questions."""

import hashlib
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.adapters.storage import PrivateStorage
from app.config import Settings, build_engine
from app.models.document import UploadRequest
from app.repositories.documents import DocumentRepository
from app.repositories.identity import IdentityRepository
from app.repositories.indexes import IndexRepository
from app.repositories.jobs import JobRepository
from app.services.documents import DocumentService
from app.worker.consumer import Consumer
from app.worker.indexer import Indexer


@contextmanager
def evaluation_corpus():
    settings = Settings()
    url = make_url(settings.database_url or "")
    assert url.database == "assistant_rag_evaluation" and url.host == "db"
    command.upgrade(Config("alembic.ini"), "head")
    engine = build_engine(settings)
    assert engine is not None
    subject = "evaluation-" + str(uuid4())
    storage = PrivateStorage(settings.private_storage_path)
    indexer = Indexer(IndexRepository(engine), settings.embedding_path)
    owner = None
    identifiers = {}
    try:
        with engine.begin() as c:
            c.execute(
                text(
                    "INSERT INTO "
                    'auth_user(id,name,email,"emailVerified",username) '
                    "VALUES (:s,:s,:e,false,:s)"
                ),
                {"s": subject, "e": subject + "@accounts.invalid"},
            )
            c.execute(
                text(
                    "INSERT INTO "
                    'auth_session(id,"userId",token,"expiresAt","update'
                    'dAt") VALUES '
                    "(:s,:s,:s,now()+make_interval(hours=>1),now())"
                ),
                {"s": subject},
            )
        owner = IdentityRepository(engine).current_user(subject).id
        documents = DocumentRepository(engine)
        service = DocumentService(documents, storage, settings)
        consumer = Consumer(JobRepository(engine), storage, indexer)
        for filename in [
            "atelier-rag.pdf",
            "parcours-2026.docx",
            "reseau.txt",
            "politique-2025.txt",
        ]:
            file = Path("/evaluation/corpus") / filename
            raw = file.read_bytes()
            mime = {
                "pdf": "application/pdf",
                "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "txt": "text/plain",
            }[file.suffix[1:]]
            doc, token = service.reserve(
                owner,
                subject,
                UploadRequest(filename=filename, size_bytes=len(raw), content_type=mime),
            )
            identifiers[file.stem] = doc.id
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            service.uploads.begin_upload(doc.id, token_hash)
            temporary = storage.temporary()
            temporary.write_bytes(raw)
            service.uploads.complete_upload(
                doc.id, token_hash, len(raw), lambda: storage.commit(temporary, doc.id)
            )
            temporary.unlink()
            service.finalize(owner, doc.id)
        start = time.monotonic()
        while any(documents.get(owner, id).state != "ready" for id in identifiers.values()):
            if time.monotonic() - start > 180 or not consumer.run_once():
                raise RuntimeError("Real indexing failed")
        yield settings, engine, owner, subject, indexer, identifiers
    finally:
        indexer.close()
        for id in identifiers.values():
            storage.delete(id)
        with engine.begin() as c:
            if owner is not None:
                c.execute(text("DELETE FROM documents WHERE owner_id=:owner"), {"owner": owner})
                c.execute(text("DELETE FROM users WHERE id=:owner"), {"owner": owner})
            c.execute(text('DELETE FROM auth_session WHERE "userId"=:s'), {"s": subject})
            c.execute(text("DELETE FROM auth_user WHERE id=:s"), {"s": subject})
        engine.dispose()
