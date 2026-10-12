from collections.abc import Callable, Mapping
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Engine, text

from app.models.document import Document, DocumentError, UploadRequest
from app.repositories.documents import COLUMNS


class UploadRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def reserve(
        self,
        owner: UUID,
        session_id: str,
        request: UploadRequest,
        token_hash: str,
        max_file_bytes: int,
        user_bytes: int,
        global_bytes: int,
    ) -> Document:
        with self.engine.begin() as connection:
            connection.execute(text("SELECT pg_advisory_xact_lock(3719301)"))
            counts = (
                connection.execute(
                    text(
                        "SELECT count(*) total, coalesce(sum(size_bytes),0) bytes, "
                        "count(*) FILTER (WHERE owner_id=:owner) owned, "
                        "coalesce(sum(size_bytes) FILTER (WHERE owner_id=:owner)"
                        ",0) owned_bytes FROM documents"
                    ),
                    {"owner": owner},
                )
                .mappings()
                .one()
            )
            if request.size_bytes > max_file_bytes:
                raise DocumentError(413, "file_too_large")
            if (
                counts["total"] >= 100
                or counts["owned"] >= 50
                or counts["bytes"] + request.size_bytes > global_bytes
                or counts["owned_bytes"] + request.size_bytes > user_bytes
                or connection.execute(
                    text("SELECT pg_database_size(current_database())")
                ).scalar_one()
                >= global_bytes
            ):
                raise DocumentError(429, "storage_quota")
            row = (
                connection.execute(
                    text(
                        "INSERT INTO documents (id,owner_id,filename,extension,c"
                        "ontent_type,size_bytes,state,"
                        "expires_at,upload_hash,session_id) VALUES (:id,:owner,:"
                        "filename,:extension,:content_type,"
                        ":size_bytes,'uploading',now()+interval '10 minutes',:hash,:sid) RETURNING "
                        + COLUMNS
                    ),
                    {
                        **request.model_dump(),
                        "id": uuid4(),
                        "owner": owner,
                        "extension": request.filename.rsplit(".", 1)[-1].lower(),
                        "hash": token_hash,
                        "sid": session_id,
                    },
                )
                .mappings()
                .one()
            )
            return Document.model_validate(dict(row))

    def begin_upload(self, document_id: UUID, token_hash: str) -> Mapping[str, Any]:
        with self.engine.begin() as connection:
            row = (
                connection.execute(
                    text(
                        "UPDATE documents d SET stage='receiving',updated_at=now() WHERE id=:id "
                        "AND upload_hash=:hash AND state='uploading' AND stage='"
                        "upload' AND expires_at>now() "
                        "AND EXISTS (SELECT 1 FROM auth_session s WHERE s.id=d.session_id AND "
                        's."expiresAt">now() AND s."userId"=(SELECT auth_user_id'
                        " FROM users WHERE id=d.owner_id)) "
                        "RETURNING id,owner_id,size_bytes,content_type"
                    ),
                    {"id": document_id, "hash": token_hash},
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise DocumentError(404, "not_found")
            return dict(row)

    def abort_upload(self, document_id: UUID, token_hash: str) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE documents SET stage='upload',updated_at=now() WHERE id=:id "
                    "AND upload_hash=:hash AND state='uploading' AND stage='receiving'"
                ),
                {"id": document_id, "hash": token_hash},
            )

    def complete_upload(
        self, document_id: UUID, token_hash: str, size: int, publish: Callable[[], None]
    ) -> None:
        # Database row lock fences deletion/expiry while the adapter publishes its object.
        with self.engine.begin() as connection:
            row = (
                connection.execute(
                    text(
                        "SELECT d.* FROM documents d WHERE id=:id AND upload_hash=:hash "
                        "AND state='uploading' AND stage='receiving' AND expires_at>now() "
                        "AND EXISTS (SELECT 1 FROM auth_session s WHERE s.id=d.session_id AND "
                        's."expiresAt">now() AND s."userId"=(SELECT auth_user_id'
                        " FROM users WHERE id=d.owner_id)) FOR UPDATE"
                    ),
                    {"id": document_id, "hash": token_hash},
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise DocumentError(404, "not_found")
            if row["size_bytes"] != size:
                raise DocumentError(422, "size_mismatch")
            publish()
            connection.execute(
                text(
                    "UPDATE documents SET stage='uploaded',actual_size=:size,upload_hash=NULL,"
                    "updated_at=now() WHERE id=:id"
                ),
                {"id": document_id, "size": size},
            )

    def complete_external(self, owner: UUID, document_id: UUID, size: int) -> None:
        """Only server-measured Blob bytes can complete an owner's live reservation."""
        with self.engine.begin() as connection:
            row = (
                connection.execute(
                    text(
                        "SELECT d.* FROM documents d WHERE id=:id AND owner_id=:owner "
                        "AND state='uploading' AND expires_at>now() "
                        "AND EXISTS (SELECT 1 FROM auth_session s WHERE s.id=d.session_id AND "
                        's."expiresAt">now() AND s."userId"=(SELECT auth_user_id '
                        "FROM users WHERE id=d.owner_id)) FOR UPDATE"
                    ),
                    {"id": document_id, "owner": owner},
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise DocumentError(404, "not_found")
            if row["size_bytes"] != size:
                raise DocumentError(422, "size_mismatch")
            connection.execute(
                text(
                    "UPDATE documents SET stage='uploaded',actual_size=:size,upload_hash=NULL,"
                    "updated_at=now() WHERE id=:id"
                ),
                {"id": document_id, "size": size},
            )
