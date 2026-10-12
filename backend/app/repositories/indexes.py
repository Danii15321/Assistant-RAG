import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from typing import Any

from sqlalchemy import Connection, Engine, text

from app.models.document import DocumentError
from app.services.chunking import Chunk
from app.services.embeddings import INDEX_VERSION, validate_vectors
from app.services.extraction import ExtractedUnit


def lock_job(connection: Connection, job: Mapping[str, Any]) -> bool:
    row = connection.execute(
        text(
            "SELECT id FROM ingestion_jobs WHERE id=:id AND kind='index' AND status='running' "
            "AND lease_token=:lease_token AND lease_until>now() FOR UPDATE"
        ),
        dict(job),
    ).one_or_none()
    if row is None:
        return False
    doc = connection.execute(
        text(
            "SELECT id FROM documents WHERE id=:document_id AND owner_id=:owner_id "
            "AND generation=:generation AND state='processing' AND stage IN ('extracted','i"
            "ndexing') "
            "FOR UPDATE"
        ),
        dict(job),
    ).one_or_none()
    if doc is None:
        connection.execute(
            text("UPDATE ingestion_jobs SET status='done',lease_until=NULL WHERE id=:id"), dict(job)
        )
    return doc is not None


class IndexRepository:
    def __init__(self, engine: Engine, user_limit: int = 10000, global_limit: int = 20000) -> None:
        self.engine = engine
        self.user_limit = user_limit
        self.global_limit = global_limit

    def units(self, job: Mapping[str, Any]) -> list[ExtractedUnit]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                text(
                    "SELECT u.kind,u.number,u.text FROM extracted_units u JOIN documents d "
                    "ON d.id=u.document_id AND d.owner_id=u.owner_id WHERE u.document_id=:document_"
                    "id "
                    "AND u.owner_id=:owner_id AND d.generation=:generation AND d.state='processing'"
                    " "
                    "ORDER BY u.ordinal"
                ),
                dict(job),
            ).mappings()
            return [ExtractedUnit(**dict(row)) for row in rows]

    def exists(self, job: Mapping[str, Any]) -> bool:
        with self.engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT index_version FROM index_runs WHERE document_id=:document_id "
                    "AND owner_id=:owner_id AND generation=:generation"
                ),
                dict(job),
            ).scalar_one_or_none()
            if row is not None and row != INDEX_VERSION:
                raise DocumentError(409, "index_incompatible")
            return row is not None

    def prepare(self, job: Mapping[str, Any], chunks: Sequence[Chunk]) -> bool:
        if not chunks:
            raise DocumentError(422, "no_text")
        manifest = hashlib.sha256(
            json.dumps([asdict(c) for c in chunks], ensure_ascii=False, sort_keys=True).encode()
        ).hexdigest()
        with self.engine.begin() as connection:
            if not lock_job(connection, job):
                return False
            existing = (
                connection.execute(
                    text(
                        "SELECT index_version,manifest_sha256 FROM index_runs WHERE "
                        "document_id=:document_id AND owner_id=:owner_id AND generation=:generation"
                    ),
                    dict(job),
                )
                .mappings()
                .one_or_none()
            )
            if existing is not None:
                if (
                    existing["index_version"] != INDEX_VERSION
                    or existing["manifest_sha256"] != manifest
                ):
                    raise DocumentError(409, "index_incompatible")
                return True
            connection.execute(text("SELECT pg_advisory_xact_lock(3719303)"))
            counts = (
                connection.execute(
                    text(
                        "SELECT coalesce(sum(expected_count),0) AS total, "
                        "coalesce(sum(expected_count) FILTER (WHERE owner_id=:owner_id),0) AS owned"
                        " "
                        "FROM index_runs"
                    ),
                    dict(job),
                )
                .mappings()
                .one()
            )
            if (
                counts["total"] + len(chunks) > self.global_limit
                or counts["owned"] + len(chunks) > self.user_limit
            ):
                raise DocumentError(429, "passage_quota")
            if (
                connection.execute(text("SELECT pg_database_size(current_database())")).scalar_one()
                >= 600 * 1024 * 1024
            ):
                raise DocumentError(429, "storage_quota")
            connection.execute(
                text(
                    "INSERT INTO index_runs (document_id,owner_id,generation,index_version,expected"
                    "_count,manifest_sha256) "
                    "VALUES (:document_id,:owner_id,:generation,:version,:count,:manifest)"
                ),
                {**job, "version": INDEX_VERSION, "count": len(chunks), "manifest": manifest},
            )
            connection.execute(
                text(
                    "INSERT INTO index_chunks (document_id,owner_id,generation,ordinal,text,token_c"
                    "ount,"
                    "start_offset,end_offset,kind,start_number,end_number,start_unit,end_unit) VALU"
                    "ES "
                    "(:document_id,:owner_id,:generation,:ordinal,:text,:token_count,:start_offset,"
                    ":end_offset,:kind,:start_number,:end_number,:start_unit,:end_unit)"
                ),
                [{**job, **asdict(chunk)} for chunk in chunks],
            )
            connection.execute(
                text(
                    "UPDATE documents SET stage='indexing',chunk_count=:count,embedded_count=0,"
                    "index_version=:version,updated_at=now() WHERE id=:document_id AND owner_id=:ow"
                    "ner_id"
                ),
                {**job, "count": len(chunks), "version": INDEX_VERSION},
            )
            connection.execute(
                text(
                    "UPDATE ingestion_jobs SET lease_until=now()+interval '120 seconds' "
                    "WHERE id=:id"
                ),
                dict(job),
            )
            return True

    def batch(self, job: Mapping[str, Any], limit: int = 16) -> list[Mapping[str, Any]]:
        if not 1 <= limit <= 16:
            raise ValueError("embedding_batch")
        with self.engine.connect() as connection:
            rows = connection.execute(
                text(
                    "SELECT c.ordinal,c.text FROM index_chunks c JOIN documents d ON "
                    "d.id=c.document_id AND d.owner_id=c.owner_id JOIN index_runs r ON "
                    "r.document_id=c.document_id AND r.owner_id=c.owner_id AND r.generation=c.gener"
                    "ation "
                    "JOIN ingestion_jobs j ON j.document_id=c.document_id AND j.owner_id=c.owner_id"
                    " "
                    "AND j.generation=c.generation WHERE c.document_id=:document_id AND c.owner_id="
                    ":owner_id "
                    "AND c.generation=:generation AND d.generation=:generation AND d.state='process"
                    "ing' "
                    "AND r.index_version=:version AND j.id=:id AND j.lease_token=:lease_token "
                    "AND j.status='running' AND j.lease_until>now() AND c.embedding IS NULL "
                    "ORDER BY c.ordinal LIMIT :limit"
                ),
                {**job, "version": INDEX_VERSION, "limit": limit},
            ).mappings()
            return [dict(row) for row in rows]

    def save(
        self, job: Mapping[str, Any], ordinals: Sequence[int], vectors: Sequence[Sequence[float]]
    ) -> bool:
        validate_vectors(vectors, len(ordinals))
        if len(set(ordinals)) != len(ordinals):
            raise ValueError("embedding_ordinals")
        with self.engine.begin() as connection:
            if not lock_job(connection, job):
                return False
            version = connection.execute(
                text(
                    "SELECT index_version FROM index_runs WHERE document_id=:document_id "
                    "AND owner_id=:owner_id AND generation=:generation"
                ),
                dict(job),
            ).scalar_one()
            if version != INDEX_VERSION:
                raise DocumentError(409, "index_incompatible")
            for ordinal, vector in zip(ordinals, vectors):
                row = connection.execute(
                    text(
                        "UPDATE index_chunks SET embedding=CAST(:vector AS vector) WHERE "
                        "document_id=:document_id AND owner_id=:owner_id AND generation=:generation"
                        " "
                        "AND ordinal=:ordinal AND embedding IS NULL RETURNING ordinal"
                    ),
                    {**job, "ordinal": ordinal, "vector": json.dumps(list(vector))},
                ).one_or_none()
                if row is None:
                    raise ValueError("embedding_checkpoint")
            count = connection.execute(
                text(
                    "SELECT count(*) FROM index_chunks WHERE document_id=:document_id AND "
                    "owner_id=:owner_id AND generation=:generation AND embedding IS NOT NULL"
                ),
                dict(job),
            ).scalar_one()
            total = connection.execute(
                text(
                    "SELECT expected_count FROM index_runs WHERE document_id=:document_id "
                    "AND owner_id=:owner_id AND generation=:generation"
                ),
                dict(job),
            ).scalar_one()
            complete = count == total
            connection.execute(
                text(
                    "UPDATE documents SET embedded_count=:count,state=:state,stage=:stage,error_cod"
                    "e=NULL,"
                    "updated_at=now() WHERE id=:document_id AND owner_id=:owner_id"
                ),
                {
                    **job,
                    "count": count,
                    "state": "ready" if complete else "processing",
                    "stage": "indexed" if complete else "indexing",
                },
            )
            connection.execute(
                text(
                    "UPDATE ingestion_jobs SET status=:status,attempts=0,lease_until=NULL,lease_tok"
                    "en=NULL "
                    "WHERE id=:id"
                ),
                {**job, "status": "done" if complete else "pending"},
            )
            return True

    def fail(self, job: Mapping[str, Any], error: str, transient: bool = False) -> None:
        with self.engine.begin() as connection:
            if not lock_job(connection, job):
                return
            retry = transient and job["attempts"] < 3
            connection.execute(
                text(
                    "UPDATE documents SET state=:state,stage='indexing',error_code=:error,updated_a"
                    "t=now() "
                    "WHERE id=:document_id AND owner_id=:owner_id"
                ),
                {
                    **job,
                    "state": "processing" if retry else "failed",
                    "error": None if retry else error,
                },
            )
            connection.execute(
                text(
                    "UPDATE ingestion_jobs SET status=:status,lease_until=NULL,lease_token=NULL WHE"
                    "RE id=:id"
                ),
                {**job, "status": "pending" if retry else "done"},
            )
