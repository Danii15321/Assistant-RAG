from uuid import UUID, uuid4

from sqlalchemy import Connection, Engine, text

from app.models.document import DocumentError


class GenerationRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def _reserve(self, c: Connection, owner: UUID, session: str, tokens: int) -> UUID:
        active = c.execute(
            text(
                'SELECT EXISTS(SELECT 1 FROM users u JOIN auth_session s ON s."userId"='
                'u.auth_user_id WHERE u.id=:owner AND s.id=:session AND s."expiresAt">now())'
            ),
            {"owner": owner, "session": session},
        ).scalar_one()
        if not active:
            raise DocumentError(401, "session_expired")
        # UTC day boundaries; reservations include failed requests and every retry.
        counts = (
            c.execute(
                text(
                    "SELECT count(*) AS daily,count(*) FILTER(WHERE owner_id=:owner) AS owned,"
                    "count(*) FILTER(WHERE created_at>now()-interval '1 minute') AS minute,"
                    "coalesce(sum(reserved_tokens),0) AS tokens FROM generation_attempts WHERE "
                    "created_at >= (date_trunc('day',now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC')"
                ),
                {"owner": owner},
            )
            .mappings()
            .one()
        )
        if (
            counts["daily"] >= 50
            or counts["owned"] >= 10
            or counts["minute"] >= 2
            or counts["tokens"] + tokens > 155000
        ):
            raise DocumentError(429, "generation_quota")
        identifier = uuid4()
        c.execute(
            text(
                "INSERT INTO generation_attempts(id,owner_id,reserved_tokens) VALUES "
                "(:id,:owner,:tokens)"
            ),
            {"id": identifier, "owner": owner, "tokens": tokens},
        )
        return identifier

    def acquire(self, owner: UUID, session: str, tokens: int) -> tuple[UUID, UUID]:
        lease = uuid4()
        with self.engine.begin() as c:
            row = (
                c.execute(
                    text(
                        "SELECT *,blocked_until>now() AS blocked,lease_until>now() "
                        "AS busy FROM generation_limits FOR UPDATE"
                    )
                )
                .mappings()
                .one()
            )
            if row["blocked"]:
                raise DocumentError(429, "provider_quota")
            if row["busy"]:
                raise DocumentError(429, "generation_busy")
            # Retain counters for seven days; no text/filenames/sessions are stored.
            c.execute(
                text("DELETE FROM generation_attempts WHERE created_at<now()-interval '7 days'")
            )
            attempt = self._reserve(c, owner, session, tokens)
            c.execute(
                text(
                    "UPDATE generation_limits SET lease_token=:lease,lease_until="
                    "now()+interval '70 seconds'"
                ),
                {"lease": lease},
            )
        return lease, attempt

    def reserve(self, owner: UUID, session: str, lease: UUID, tokens: int) -> UUID:
        with self.engine.begin() as c:
            row = (
                c.execute(
                    text(
                        "SELECT lease_token,lease_until>now() AS active,"
                        "blocked_until>now() AS blocked FROM generation_limits FOR UPDATE"
                    )
                )
                .mappings()
                .one()
            )
            if row["blocked"]:
                raise DocumentError(429, "provider_quota")
            if row["lease_token"] != lease or not row["active"]:
                raise DocumentError(503, "generation_timeout")
            return self._reserve(c, owner, session, tokens)

    def active(self, lease: UUID) -> bool:
        with self.engine.connect() as c:
            return bool(
                c.execute(
                    text(
                        "SELECT EXISTS(SELECT 1 FROM generation_limits WHERE "
                        "lease_token=:lease AND lease_until>now())"
                    ),
                    {"lease": lease},
                ).scalar_one()
            )

    def release(self, lease: UUID) -> None:
        with self.engine.begin() as c:
            c.execute(
                text(
                    "UPDATE generation_limits SET lease_token=NULL,lease_until=NULL "
                    "WHERE lease_token=:lease"
                ),
                {"lease": lease},
            )

    def block(self, seconds: int) -> None:
        with self.engine.begin() as c:
            c.execute(
                text(
                    "UPDATE generation_limits SET blocked_until=greatest(blocked_until,"
                    "now()+make_interval(secs=>:seconds))"
                ),
                {"seconds": seconds},
            )

    def finish_attempt(
        self,
        identifier: UUID,
        outcome: str,
        prompt: int | None = None,
        completion: int | None = None,
    ) -> None:
        with self.engine.begin() as c:
            c.execute(
                text(
                    "UPDATE generation_attempts SET outcome=:outcome,prompt_tokens=:p,"
                    "completion_tokens=:c WHERE id=:id AND outcome='pending'"
                ),
                {"id": identifier, "outcome": outcome, "p": prompt, "c": completion},
            )
