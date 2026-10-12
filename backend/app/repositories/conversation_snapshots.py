"""Citation text lives only in removable source snapshots, never response JSON."""

import json
from typing import Any
from uuid import UUID

from sqlalchemy import Connection, text

from app.models.answer import AnswerResponse
from app.models.conversation import Exchange


def save_answer(connection: Connection, owner: UUID, exchange: UUID, answer: AnswerResponse) -> str:
    response = answer.model_dump(mode="json")
    quotes: dict[str, list[str]] = {source.source_id: [] for source in answer.sources}
    for claim in response["claims"]:
        for evidence in claim["evidence"]:
            quote = evidence.pop("quote")
            values = quotes[evidence["source_id"]]
            if quote not in values:
                values.append(quote)
            evidence["quote_index"] = values.index(quote)
    response.pop("sources")
    for source in answer.sources:
        payload = source.model_dump(mode="json", exclude={"document_id", "source_id"})
        payload["quotes"] = quotes[source.source_id]
        connection.execute(
            text(
                "INSERT INTO "
                "conversation_sources(exchange_id,owner_id,source_id,document_id,p"
                "ayload) VALUES (:exchange,:owner,:source,:doc,CAST(:payload AS "
                "jsonb))"
            ),
            {
                "exchange": exchange,
                "owner": owner,
                "source": source.source_id,
                "doc": source.document_id,
                "payload": json.dumps(payload),
            },
        )
    return json.dumps(response)


def load_exchange(connection: Connection, row: dict[str, Any]) -> Exchange:
    response = row.pop("response")
    if response is not None:
        response = dict(response)
        sources = (
            connection.execute(
                text(
                    "SELECT source_id,document_id,status,payload FROM "
                    "conversation_sources WHERE exchange_id=:id AND owner_id=:owner "
                    "ORDER BY source_id"
                ),
                {"id": row["id"], "owner": row["owner_id"]},
            )
            .mappings()
            .all()
        )
        by_id = {source["source_id"]: source for source in sources}
        for claim in response["claims"]:
            for evidence in claim["evidence"]:
                source = by_id[evidence["source_id"]]
                index = evidence.pop("quote_index")
                evidence["quote"] = (
                    source["payload"]["quotes"][index] if source["status"] == "available" else ""
                )
        response["sources"] = [
            {
                **source["payload"],
                "document_id": str(source["document_id"]) if source["document_id"] else None,
                "source_id": source["source_id"],
                "status": source["status"],
                "text": source["payload"].get("text", ""),
            }
            for source in sources
        ]
        for source in response["sources"]:
            source.pop("quotes", None)
    row["answer"] = response
    return Exchange.model_validate(row)
