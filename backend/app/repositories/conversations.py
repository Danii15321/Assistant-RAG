import builtins
import hashlib
import json
from collections.abc import Callable
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Connection, Engine, text

from app.models.answer import AnswerResponse
from app.models.conversation import Conversation, Exchange, MessageRequest
from app.models.document import DocumentError
from app.models.search import HistoryMessage
from app.repositories.conversation_snapshots import load_exchange, save_answer
from app.repositories.search import SearchRepository


def request_fingerprint(body: MessageRequest) -> str:
    # Omitted/default Groq must replay requests saved before model selection existed.
    excluded = {"request_id", "model"} if body.model == "groq" else {"request_id"}
    return hashlib.sha256(
        json.dumps(body.model_dump(mode="json", exclude=excluded), sort_keys=True).encode()
    ).hexdigest()


class ConversationRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def create(self, owner: UUID) -> Conversation:
        with self.engine.begin() as c:
            c.execute(text("SELECT id FROM users WHERE id=:owner FOR UPDATE"), {"owner": owner})
            count = c.execute(
                text("SELECT count(*) FROM conversations WHERE owner_id=:owner"), {"owner": owner}
            ).scalar_one()
            if count >= 50:
                raise DocumentError(429, "conversation_quota")
            row = (
                c.execute(
                    text("INSERT INTO conversations(id,owner_id) VALUES (:id,:owner) RETURNING *"),
                    {"id": uuid4(), "owner": owner},
                )
                .mappings()
                .one()
            )
            return Conversation.model_validate(dict(row))

    def list(self, owner: UUID, offset: int, limit: int) -> builtins.list[Conversation]:
        with self.engine.connect() as c:
            rows = c.execute(
                text(
                    "SELECT * FROM conversations WHERE owner_id=:owner ORDER BY "
                    "updated_at DESC,id LIMIT :limit OFFSET :offset"
                ),
                {"owner": owner, "limit": limit, "offset": offset},
            ).mappings()
            return [Conversation.model_validate(dict(row)) for row in rows]

    def _lock(self, c: Connection, owner: UUID, conversation: UUID) -> dict[str, Any]:
        row = (
            c.execute(
                text("SELECT * FROM conversations WHERE id=:id AND owner_id=:owner FOR UPDATE"),
                {"id": conversation, "owner": owner},
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise DocumentError(404, "conversation_unavailable")
        c.execute(
            text(
                "UPDATE conversation_exchanges SET "
                "state='failed',error_code='generation_interrupted',completed_at=n"
                "ow() WHERE conversation_id=:id AND owner_id=:owner AND "
                "state='pending' AND EXISTS (SELECT 1 FROM conversations WHERE "
                "id=:id AND lease_until<=now())"
            ),
            {"id": conversation, "owner": owner},
        )
        return dict(row)

    def get(self, owner: UUID, conversation: UUID) -> Conversation:
        with self.engine.begin() as c:
            return Conversation.model_validate(self._lock(c, owner, conversation))

    def messages(
        self, owner: UUID, conversation: UUID, offset: int, limit: int
    ) -> builtins.list[Exchange]:
        with self.engine.begin() as c:
            self._lock(c, owner, conversation)
            rows = (
                c.execute(
                    text(
                        "SELECT * FROM conversation_exchanges WHERE conversation_id=:id "
                        "AND owner_id=:owner ORDER BY ordinal LIMIT :limit OFFSET :offset"
                    ),
                    {"id": conversation, "owner": owner, "limit": limit, "offset": offset},
                )
                .mappings()
                .all()
            )
            return [load_exchange(c, dict(row)) for row in rows]

    def begin(self, owner: UUID, conversation: UUID, body: MessageRequest) -> tuple[Exchange, bool]:
        fingerprint = request_fingerprint(body)
        with self.engine.begin() as c:
            parent = self._lock(c, owner, conversation)
            old = (
                c.execute(
                    text(
                        "SELECT * FROM conversation_exchanges WHERE conversation_id=:id "
                        "AND owner_id=:owner AND request_id=:request"
                    ),
                    {"id": conversation, "owner": owner, "request": body.request_id},
                )
                .mappings()
                .one_or_none()
            )
            if old is not None:
                if old["fingerprint"] != fingerprint:
                    raise DocumentError(409, "request_conflict")
                return load_exchange(c, dict(old)), False
            busy = c.execute(
                text("SELECT lease_until>now() FROM conversations WHERE id=:id"),
                {"id": conversation},
            ).scalar_one()
            if busy:
                raise DocumentError(409, "conversation_busy")
            if parent["next_ordinal"] > 100:
                raise DocumentError(429, "conversation_message_quota")
            exchange = uuid4()
            row = (
                c.execute(
                    text(
                        "INSERT INTO "
                        "conversation_exchanges(id,conversation_id,owner_id,request_id,fin"
                        "gerprint,ordinal,question,document_ids,model) VALUES "
                        "(:exchange,:id,:owner,:request,:fingerprint,:ordinal,:question,CA"
                        "ST(:selection AS jsonb),:model) RETURNING *"
                    ),
                    {
                        "exchange": exchange,
                        "id": conversation,
                        "owner": owner,
                        "request": body.request_id,
                        "fingerprint": fingerprint,
                        "ordinal": parent["next_ordinal"],
                        "question": body.question,
                        "model": body.model,
                        "selection": json.dumps([str(doc) for doc in body.document_ids])
                        if body.document_ids is not None
                        else None,
                    },
                )
                .mappings()
                .one()
            )
            c.execute(
                text(
                    "UPDATE conversations SET "
                    "lease_token=:exchange,lease_until=now()+interval '210 "
                    "seconds',next_ordinal=next_ordinal+1,updated_at=now(),title=CASE "
                    "WHEN next_ordinal=1 THEN :title ELSE title END WHERE id=:id AND "
                    "owner_id=:owner"
                ),
                {
                    "exchange": exchange,
                    "title": body.question[:80],
                    "id": conversation,
                    "owner": owner,
                },
            )
            return load_exchange(c, dict(row)), True

    def active(self, owner: UUID, conversation: UUID, exchange: UUID) -> bool:
        with self.engine.connect() as c:
            return bool(
                c.execute(
                    text(
                        "SELECT EXISTS (SELECT 1 FROM conversations WHERE id=:id AND "
                        "owner_id=:owner AND lease_token=:exchange AND lease_until>now())"
                    ),
                    {"id": conversation, "owner": owner, "exchange": exchange},
                ).scalar_one()
            )

    def history(self, owner: UUID, conversation: UUID) -> builtins.list[HistoryMessage]:
        with self.engine.begin() as c:
            self._lock(c, owner, conversation)
            rows = (
                c.execute(
                    text(
                        "SELECT question,response->>'answer' AS answer FROM "
                        "conversation_exchanges WHERE conversation_id=:id AND "
                        "owner_id=:owner AND state IN ('answered','insufficient_context') "
                        "ORDER BY ordinal DESC LIMIT 3"
                    ),
                    {"id": conversation, "owner": owner},
                )
                .mappings()
                .all()
            )
            history: builtins.list[HistoryMessage] = []
            for row in reversed(rows):
                history.append(HistoryMessage(role="user", content=str(row["question"])[:500]))
                history.append(HistoryMessage(role="assistant", content=str(row["answer"])[:500]))
            return history

    def complete(
        self,
        owner: UUID,
        conversation: UUID,
        exchange: UUID,
        answer: AnswerResponse,
        active_session: Callable[[], bool],
    ) -> Exchange:
        with self.engine.begin() as c:
            self._lock(c, owner, conversation)
            if not c.execute(
                text(
                    "SELECT lease_token=:exchange AND lease_until>now() FROM "
                    "conversations WHERE id=:id AND owner_id=:owner"
                ),
                {"id": conversation, "owner": owner, "exchange": exchange},
            ).scalar_one():
                raise DocumentError(409, "generation_interrupted")
            if not active_session():
                raise DocumentError(401, "session_expired")
            SearchRepository(self.engine).verify_hits_on(c, owner, answer.sources)
            response = save_answer(c, owner, exchange, answer)
            row = (
                c.execute(
                    text(
                        "UPDATE conversation_exchanges SET "
                        "state=:state,response=CAST(:response AS jsonb),completed_at=now() "
                        "WHERE id=:exchange AND owner_id=:owner AND state='pending' "
                        "RETURNING *"
                    ),
                    {
                        "state": answer.state,
                        "response": response,
                        "exchange": exchange,
                        "owner": owner,
                    },
                )
                .mappings()
                .one()
            )
            c.execute(
                text(
                    "UPDATE conversations SET "
                    "lease_token=NULL,lease_until=NULL,updated_at=now() WHERE id=:id "
                    "AND owner_id=:owner AND lease_token=:exchange"
                ),
                {"id": conversation, "owner": owner, "exchange": exchange},
            )
            return load_exchange(c, dict(row))

    def fail(self, owner: UUID, conversation: UUID, exchange: UUID, code: str) -> None:
        with self.engine.begin() as c:
            c.execute(
                text(
                    "UPDATE conversations SET "
                    "lease_token=NULL,lease_until=NULL,updated_at=now() WHERE id=:id "
                    "AND owner_id=:owner AND lease_token=:exchange"
                ),
                {"id": conversation, "owner": owner, "exchange": exchange},
            )
            c.execute(
                text(
                    "UPDATE conversation_exchanges SET "
                    "state='failed',error_code=:code,completed_at=now() WHERE "
                    "id=:exchange AND conversation_id=:id AND owner_id=:owner AND "
                    "state='pending'"
                ),
                {"id": conversation, "owner": owner, "exchange": exchange, "code": code},
            )

    def delete(self, owner: UUID, conversation: UUID) -> None:
        with self.engine.begin() as c:
            self._lock(c, owner, conversation)
            c.execute(
                text("DELETE FROM conversations WHERE id=:id AND owner_id=:owner"),
                {"id": conversation, "owner": owner},
            )
