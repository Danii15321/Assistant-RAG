import asyncio
import hashlib
import os
import secrets
from pathlib import PurePath
from uuid import UUID

from fastapi import Request

from app.adapters.storage import PrivateStorage
from app.config import Settings
from app.models.document import Document, DocumentError, UploadRequest
from app.repositories.documents import DocumentRepository
from app.repositories.uploads import UploadRepository

CONTENT_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "txt": "text/plain",
}


class DocumentService:
    def __init__(
        self, repository: DocumentRepository, storage: PrivateStorage, settings: Settings
    ) -> None:
        self.repository = repository
        self.uploads = UploadRepository(repository.engine)
        self.storage = storage
        self.settings = settings

    def reserve(self, owner: UUID, session_id: str, request: UploadRequest) -> tuple[Document, str]:
        name = request.filename
        if (
            name != PurePath(name).name
            or any(c in name for c in "\\/\x00")
            or any(ord(c) < 32 for c in name)
        ):
            raise DocumentError(400, "invalid_filename")
        extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        if extension not in CONTENT_TYPES or request.content_type != CONTENT_TYPES[extension]:
            raise DocumentError(415, "unsupported_format")
        token = secrets.token_urlsafe(32)
        document = self.uploads.reserve(
            owner,
            session_id,
            request,
            hashlib.sha256(token.encode()).hexdigest(),
            self.settings.max_file_bytes,
            self.settings.user_storage_bytes,
            self.settings.global_storage_bytes,
        )
        return document, token

    def finalize(self, owner: UUID, document_id: UUID) -> tuple[Document, bool]:
        document = self.repository.get(owner, document_id)
        if document.state != "uploading":
            return document, False
        if document.stage != "uploaded":
            raise DocumentError(409, "upload_incomplete")
        try:
            size, digest = self.storage.metadata(document_id)
        except OSError as error:
            raise DocumentError(503, "storage_unavailable") from error
        return self.repository.finalize(owner, document_id, size, digest)

    async def upload(self, document_id: UUID, token: str, request: Request) -> None:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        reservation = self.uploads.begin_upload(document_id, token_hash)
        temporary = None
        try:
            temporary = self.storage.temporary()
            declared = request.headers.get("content-length")
            if declared is not None and declared != str(reservation["size_bytes"]):
                raise DocumentError(422, "size_mismatch")
            if request.headers.get("content-type", "").split(";")[0] != reservation["content_type"]:
                raise DocumentError(415, "unsupported_format")

            target = temporary

            async def transfer() -> int:
                size = 0
                with target.open("wb") as stream:
                    async for chunk in request.stream():
                        size += len(chunk)
                        if size > reservation["size_bytes"] or size > self.settings.max_file_bytes:
                            raise DocumentError(413, "file_too_large")
                        stream.write(chunk)
                    stream.flush()
                    os.fsync(stream.fileno())
                return size

            size = await asyncio.wait_for(transfer(), timeout=120)
            self.uploads.complete_upload(
                document_id, token_hash, size, lambda: self.storage.commit(temporary, document_id)
            )
        except asyncio.TimeoutError as error:
            raise DocumentError(504, "upload_timeout") from error
        except OSError as error:
            raise DocumentError(503, "storage_unavailable") from error
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
            self.uploads.abort_upload(document_id, token_hash)
