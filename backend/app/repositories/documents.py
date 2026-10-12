from uuid import UUID, uuid4

from sqlalchemy import Connection, Engine, text

from app.models.document import Document, DocumentError, Passage, Unit
from app.services.embeddings import INDEX_VERSION

COLUMNS = (
    "id, filename, size_bytes, extension, state, stage, error_code, cr"
    "eated_at, unit_count, parser_version, chunk_count, embedded_count, index_version"
)


def enqueue(
    connection: Connection, document_id: UUID, owner_id: UUID, kind: str, generation: int
) -> None:
    connection.execute(
        text(
            "INSERT INTO ingestion_jobs (id, document_id, owner_id, kind, generation) "
            "VALUES (:id, :document, :owner, :kind, :generation) ON CONFLICT DO NOTHING"
        ),
        {
            "id": uuid4(),
            "document": document_id,
            "owner": owner_id,
            "kind": kind,
            "generation": generation,
        },
    )


class DocumentRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def list_documents(self, owner: UUID, offset: int, limit: int) -> list[Document]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                text(
                    "SELECT " + COLUMNS + " FROM documents WHERE owner_id=:owner "
                    "AND state<>'deleting' ORDER BY created_at DESC,id LIMIT :limit OFFSET :offset"
                ),
                {"owner": owner, "limit": limit, "offset": offset},
            ).mappings()
            return [Document.model_validate(dict(row)) for row in rows]

    def get(self, owner: UUID, document_id: UUID) -> Document:
        with self.engine.connect() as connection:
            row = (
                connection.execute(
                    text(
                        "SELECT " + COLUMNS + " FROM documents "
                        "WHERE id=:id AND owner_id=:owner AND state<>'deleting'"
                    ),
                    {"id": document_id, "owner": owner},
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise DocumentError(404, "not_found")
            return Document.model_validate(dict(row))

    def units(self, owner: UUID, document_id: UUID, offset: int, limit: int) -> list[Unit]:
        self.get(owner, document_id)
        with self.engine.connect() as connection:
            rows = connection.execute(
                text(
                    "SELECT u.ordinal,u.kind,u.number,u.text FROM extracted_"
                    "units u JOIN documents d "
                    "ON d.id=u.document_id AND d.owner_id=u.owner_id WHERE u.document_id=:id "
                    "AND u.owner_id=:owner AND d.state<>'deleting' ORDER BY "
                    "ordinal LIMIT :limit OFFSET :offset"
                ),
                {"id": document_id, "owner": owner, "limit": limit, "offset": offset},
            ).mappings()
            return [Unit.model_validate(dict(row)) for row in rows]

    def passages(self, owner: UUID, document_id: UUID, offset: int, limit: int) -> list[Passage]:
        self.get(owner, document_id)
        with self.engine.connect() as connection:
            rows = connection.execute(
                text(
                    "SELECT c.ordinal,c.text,c.token_count,c.start_offset,c.end_offset,c.kind,"
                    "c.start_number,c.end_number,c.start_unit,c.end_unit FROM index_chunks c "
                    "JOIN documents d ON d.id=c.document_id AND d.owner_id=c.owner_id "
                    "JOIN index_runs r ON r.document_id=c.document_id AND r.owner_id=c.owner_id "
                    "AND r.generation=c.generation WHERE c.document_id=:id AND c.owner_id=:owner "
                    "AND d.state='ready' AND d.generation=c.generation AND r.index_version=:version"
                    " "
                    "AND d.index_version=:version AND c.embedding IS NOT NULL ORDER BY c.ordinal "
                    "LIMIT :limit OFFSET :offset"
                ),
                {
                    "id": document_id,
                    "owner": owner,
                    "version": INDEX_VERSION,
                    "limit": limit,
                    "offset": offset,
                },
            ).mappings()
            return [Passage.model_validate(dict(row)) for row in rows]

    def finalize(
        self, owner: UUID, document_id: UUID, size: int, digest: str
    ) -> tuple[Document, bool]:
        with self.engine.begin() as connection:
            connection.execute(text("SELECT pg_advisory_xact_lock(3719301)"))
            row = (
                connection.execute(
                    text(
                        "SELECT * FROM documents WHERE id=:id AND owner_id=:owner "
                        "AND state<>'deleting' FOR UPDATE"
                    ),
                    {"id": document_id, "owner": owner},
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise DocumentError(404, "not_found")
            if row["state"] != "uploading":
                return Document.model_validate(dict(row)), False
            if (
                row["stage"] != "uploaded"
                or row["actual_size"] != size
                or row["size_bytes"] != size
            ):
                raise DocumentError(409, "upload_incomplete")
            duplicate = (
                connection.execute(
                    text(
                        "SELECT " + COLUMNS + " FROM documents WHERE owner_id=:owner "
                        "AND sha256=:hash AND state<>'deleting' AND id<>:id"
                    ),
                    {"owner": owner, "hash": digest, "id": document_id},
                )
                .mappings()
                .one_or_none()
            )
            if duplicate is not None:
                connection.execute(
                    text(
                        "UPDATE documents SET state='deleting',stage='cleanup',upload_hash=NULL "
                        "WHERE id=:id"
                    ),
                    {"id": document_id},
                )
                enqueue(connection, document_id, owner, "delete", row["generation"])
                return Document.model_validate(dict(duplicate)), True
            result = (
                connection.execute(
                    text(
                        "UPDATE documents SET state='queued',stage='extraction',sha256=:hash,"
                        "updated_at=now() WHERE id=:id RETURNING " + COLUMNS
                    ),
                    {"id": document_id, "hash": digest},
                )
                .mappings()
                .one()
            )
            enqueue(connection, document_id, owner, "extract", row["generation"])
            return Document.model_validate(dict(result)), False

    def retry(self, owner: UUID, document_id: UUID) -> Document:
        with self.engine.begin() as connection:
            row = (
                connection.execute(
                    text(
                        "SELECT * FROM documents WHERE id=:id AND owner_id=:owner "
                        "AND state<>'deleting' FOR UPDATE"
                    ),
                    {"id": document_id, "owner": owner},
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise DocumentError(404, "not_found")
            if row["state"] in {"queued", "processing"}:
                return Document.model_validate(dict(row))
            if row["state"] != "failed":
                raise DocumentError(409, "retry_unavailable")
            if row["stage"] == "indexing":
                connection.execute(
                    text(
                        "UPDATE documents SET state='queued',error_code=NULL,updated_at=now() "
                        "WHERE id=:id AND owner_id=:owner"
                    ),
                    {"id": document_id, "owner": owner},
                )
                connection.execute(
                    text(
                        "UPDATE ingestion_jobs SET status='pending',attempts=0,lease_token=NULL,l"
                        "ease_u"
                        "ntil=NULL "
                        "WHERE document_id=:id AND owner_id=:owner AND generation=:generation AND"
                        " kind="
                        "'index'"
                    ),
                    {"id": document_id, "owner": owner, "generation": row["generation"]},
                )
                return Document.model_validate({**dict(row), "state": "queued", "error_code": None})
            result = (
                connection.execute(
                    text(
                        "UPDATE documents SET state='queued',stage='extraction',error_code=NULL,"
                        "generation=generation+1,updated_at=now() WHERE id=:id RETURNING " + COLUMNS
                    ),
                    {"id": document_id},
                )
                .mappings()
                .one()
            )
            enqueue(connection, document_id, owner, "extract", row["generation"] + 1)
            return Document.model_validate(dict(result))

    def delete(self, owner: UUID, document_id: UUID) -> None:
        with self.engine.begin() as connection:
            row = (
                connection.execute(
                    text(
                        "SELECT generation FROM documents WHERE id=:id AND owner_id=:owner "
                        "FOR UPDATE"
                    ),
                    {"id": document_id, "owner": owner},
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise DocumentError(404, "not_found")
            connection.execute(
                text(
                    "UPDATE documents SET state='deleting',stage='cleanup',upload_hash=NULL "
                    "WHERE id=:id AND owner_id=:owner"
                ),
                {"id": document_id, "owner": owner},
            )
            enqueue(connection, document_id, owner, "delete", row["generation"])
