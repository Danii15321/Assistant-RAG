import json
from collections.abc import Mapping
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Engine, text

from app.models.document import DocumentError
from app.services.embeddings import validate_vectors


class QueryJobRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def submit(self, owner: UUID, session: str, question: str) -> UUID:
        identifier = uuid4()
        with self.engine.begin() as c:
            c.execute(text("SELECT pg_advisory_xact_lock(3719304)"))
            c.execute(text("DELETE FROM search_jobs WHERE expires_at<=now()"))
            counts = (
                c.execute(
                    text(
                        "SELECT count(*) AS total,count(*) FILTER (WHERE "
                        "owner_id=:owner) AS owned FROM search_jobs"
                    ),
                    {"owner": owner},
                )
                .mappings()
                .one()
            )
            if counts["owned"] >= 1 or counts["total"] >= 8:
                raise DocumentError(429, "search_busy")
            row = c.execute(
                text(
                    "INSERT INTO search_jobs(id,owner_id,session_id,question) "
                    "SELECT :id,u.id,s.id,:question FROM users u JOIN "
                    'auth_session s ON s."userId"=u.auth_user_id '
                    'WHERE u.id=:owner AND s.id=:session AND s."expiresAt">now() RETURNING id'
                ),
                {"id": identifier, "owner": owner, "session": session, "question": question},
            ).one_or_none()
            if row is None:
                raise DocumentError(401, "session_expired")
        return identifier

    def result(self, owner: UUID, identifier: UUID) -> Mapping[str, Any] | None:
        with self.engine.connect() as c:
            row = (
                c.execute(
                    text(
                        "SELECT status,embedding::text,error_code FROM search_jobs "
                        "WHERE id=:id AND owner_id=:owner "
                        "AND expires_at>now()"
                    ),
                    {"id": identifier, "owner": owner},
                )
                .mappings()
                .one_or_none()
            )
            return dict(row) if row is not None else None

    def remove(self, owner: UUID, identifier: UUID) -> None:
        with self.engine.begin() as c:
            c.execute(
                text("DELETE FROM search_jobs WHERE id=:id AND owner_id=:owner"),
                {"id": identifier, "owner": owner},
            )

    def claim(self) -> Mapping[str, Any] | None:
        with self.engine.begin() as c:
            c.execute(text("SELECT pg_advisory_xact_lock(3719302)"))
            c.execute(text("DELETE FROM search_jobs WHERE expires_at<=now()"))
            row = (
                c.execute(
                    text(
                        "SELECT q.* FROM search_jobs q JOIN users u ON u.id=q.owner_id "
                        'JOIN auth_session s ON s.id=q.session_id AND s."userId"=u.auth_user_id '
                        "WHERE s.\"expiresAt\">now() AND (q.status='pending' OR "
                        "(q.status='running' AND q.lease_until<now())) "
                        "AND NOT EXISTS(SELECT 1 FROM search_jobs WHERE "
                        "status='running' AND lease_until>=now()) "
                        "AND NOT EXISTS(SELECT 1 FROM ingestion_jobs WHERE "
                        "status='running' AND lease_until>=now()) "
                        "ORDER BY q.created_at,q.id LIMIT 1 FOR UPDATE OF q SKIP LOCKED"
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                return None
            job = dict(row)
            job["lease_token"] = uuid4()
            c.execute(
                text(
                    "UPDATE search_jobs SET "
                    "status='running',lease_token=:lease_token,lease_until=now("
                    ")+interval '120 seconds' WHERE id=:id"
                ),
                job,
            )
            return job

    def finish(
        self, job: Mapping[str, Any], vector: list[float] | None = None, error: str | None = None
    ) -> bool:
        if vector is not None:
            validate_vectors([vector], 1)
        with self.engine.begin() as c:
            row = c.execute(
                text(
                    "UPDATE search_jobs q SET "
                    "status=:status,embedding=CAST(:vector AS "
                    "vector),error_code=:error,"
                    "question='',lease_until=NULL,lease_token=NULL "
                    "WHERE q.id=:id AND q.owner_id=:owner_id AND "
                    "q.status='running' AND q.lease_token=:lease_token "
                    "AND q.lease_until>now() AND q.expires_at>now() AND "
                    "EXISTS(SELECT 1 FROM users u "
                    'JOIN auth_session s ON s."userId"=u.auth_user_id WHERE '
                    "u.id=q.owner_id AND s.id=q.session_id "
                    'AND s."expiresAt">now()) RETURNING q.id'
                ),
                {
                    **job,
                    "status": "done" if vector is not None else "failed",
                    "vector": json.dumps(vector) if vector is not None else None,
                    "error": error,
                },
            ).one_or_none()
            return row is not None
