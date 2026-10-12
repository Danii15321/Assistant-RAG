from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Engine, text

from app.repositories.documents import enqueue
from app.services.extraction import PARSER_VERSION, ExtractedUnit


class JobRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def claim(self, include_index: bool = True) -> Mapping[str, Any] | None:
        with self.engine.begin() as connection:
            connection.execute(text("SELECT pg_advisory_xact_lock(3719302)"))
            row = (
                connection.execute(
                    text(
                        "SELECT j.*,d.extension FROM ingestion_jobs j JOIN documents d "
                        "ON d.id=j.document_id AND d.owner_id=j.owner_id "
                        "WHERE (:include_index OR j.kind<>'index') AND (j.status='pending' OR (j."
                        "status"
                        "='running' AND j."
                        "lease_until<now())) "
                        "AND NOT EXISTS (SELECT 1 FROM ingestion_jobs WHERE stat"
                        "us='running' AND lease_until>=now()) "
                        "AND NOT EXISTS(SELECT 1 FROM search_jobs WHERE "
                        "status='running' AND lease_until>=now()) "
                        "ORDER BY CASE j.kind WHEN 'delete' THEN 0 ELSE 1 END,j.created_at "
                        "LIMIT 1 FOR UPDATE OF j SKIP LOCKED"
                    ),
                    {"include_index": include_index},
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                return None
            job = dict(row)
            job["lease_token"] = uuid4()
            job["attempts"] += 1
            connection.execute(
                text(
                    "UPDATE ingestion_jobs SET status='running',attempts=attempts+1,"
                    "lease_token=:lease_token,lease_until=now()+CASE WHEN kind='index' "
                    "THEN interval '120 seconds' ELSE interval '60 seconds' END WHERE id=:id"
                ),
                job,
            )
            if job["kind"] == "extract":
                connection.execute(
                    text(
                        "UPDATE documents SET state='processing',stage='extracti"
                        "on',updated_at=now() "
                        "WHERE id=:document_id AND owner_id=:owner_id AND generation=:generation "
                        "AND state IN ('queued','processing') AND stage<>'extracted'"
                    ),
                    job,
                )
            elif job["kind"] == "index":
                connection.execute(
                    text(
                        "UPDATE documents SET state='processing' WHERE id=:document_id "
                        "AND owner_id=:owner_id AND generation=:generation AND state IN ('queued'"
                        ",'proc"
                        "essing')"
                    ),
                    job,
                )
            return job

    def finish(
        self,
        job: Mapping[str, Any],
        units: Sequence[ExtractedUnit] | None = None,
        error: str | None = None,
        transient: bool = False,
    ) -> bool:
        with self.engine.begin() as connection:
            locked = connection.execute(
                text(
                    "SELECT id FROM ingestion_jobs WHERE id=:id AND status='running' "
                    "AND lease_token=:lease_token AND lease_until>now() FOR UPDATE"
                ),
                dict(job),
            ).one_or_none()
            if locked is None:
                return False
            doc = (
                connection.execute(
                    text(
                        "SELECT state,generation,stage FROM documents WHERE id=:document_id "
                        "AND owner_id=:owner_id FOR UPDATE"
                    ),
                    dict(job),
                )
                .mappings()
                .one_or_none()
            )
            valid = (
                doc is not None
                and doc["state"] == "processing"
                and doc["generation"] == job["generation"]
                and doc["stage"] != "extracted"
            )
            if valid:
                if transient and job["attempts"] < 3:
                    connection.execute(
                        text("UPDATE documents SET state='queued' WHERE id=:document_id"), dict(job)
                    )
                    connection.execute(
                        text(
                            "UPDATE ingestion_jobs SET status='pending',lease_until=NULL WHERE"
                            " id=:id"
                        ),
                        dict(job),
                    )
                    return True
                if units is not None:
                    connection.execute(
                        text(
                            "DELETE FROM extracted_units WHERE document_id=:document_id AND ow"
                            "ner_id=:owner_id"
                        ),
                        dict(job),
                    )
                    connection.execute(
                        text(
                            "INSERT INTO extracted_units (document_id,owner_id,ordin"
                            "al,kind,number,text) "
                            "VALUES (:document_id,:owner_id,:ordinal,:kind,:number,:text)"
                        ),
                        [
                            {
                                "document_id": job["document_id"],
                                "owner_id": job["owner_id"],
                                "ordinal": i,
                                "kind": u.kind,
                                "number": u.number,
                                "text": u.text,
                            }
                            for i, u in enumerate(units, 1)
                        ],
                    )
                    connection.execute(
                        text(
                            "UPDATE documents SET stage='extracted',parser_version=:"
                            "version,unit_count=:count,"
                            "error_code=NULL,updated_at=now() WHERE id=:document_id"
                        ),
                        {**job, "version": PARSER_VERSION, "count": len(units)},
                    )
                    enqueue(
                        connection, job["document_id"], job["owner_id"], "index", job["generation"]
                    )
                else:
                    connection.execute(
                        text(
                            "UPDATE documents SET state='failed',stage='extraction',"
                            "error_code=:error,"
                            "updated_at=now() WHERE id=:document_id"
                        ),
                        {**job, "error": error or "processing_failed"},
                    )
            connection.execute(
                text("UPDATE ingestion_jobs SET status='done',lease_until=NULL WHERE id=:id"),
                dict(job),
            )
            return valid

    def delete(self, job: Mapping[str, Any]) -> bool:
        with self.engine.begin() as connection:
            row = connection.execute(
                text(
                    "SELECT j.id FROM ingestion_jobs j JOIN documents d ON d.id=j.document_id "
                    "AND d.owner_id=j.owner_id WHERE j.id=:id AND j.lease_to"
                    "ken=:lease_token AND j.status='running' "
                    "AND j.lease_until>now() AND d.state='deleting' FOR UPDATE OF j,d"
                ),
                dict(job),
            ).one_or_none()
            if row is None:
                return False
            connection.execute(
                text("DELETE FROM documents WHERE id=:document_id AND owner_id=:owner_id"),
                dict(job),
            )
            return True

    def reconcile(self) -> set[UUID]:
        with self.engine.begin() as connection:
            rows = connection.execute(
                text(
                    "UPDATE documents SET state='deleting',stage='cleanup',upload_hash=NULL "
                    "WHERE state='uploading' AND expires_at<now() RETURNING id,owner_id,generation"
                )
            ).mappings()
            for row in rows:
                enqueue(connection, row["id"], row["owner_id"], "delete", row["generation"])
            return set(connection.execute(text("SELECT id FROM documents")).scalars())
