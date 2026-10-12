import json
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import Connection, Engine, bindparam, text

from app.models.document import DocumentError
from app.models.search import SearchHit
from app.services.embeddings import INDEX_VERSION, validate_vectors


class SearchRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def validate_selection(self, owner: UUID, selection: list[UUID] | None) -> bool:
        with self.engine.connect() as connection:
            return self.check_selection(connection, owner, selection)

    def verify_hits(self, owner: UUID, hits: Sequence[SearchHit]) -> None:
        with self.engine.begin() as connection:
            self.verify_hits_on(connection, owner, hits)

    def verify_hits_on(
        self, connection: Connection, owner: UUID, hits: Sequence[SearchHit]
    ) -> None:
        for hit in hits:
            row = connection.execute(
                text(
                    "SELECT c.text FROM index_chunks c JOIN documents d ON d.id=c.document_id "
                    "AND d.owner_id=c.owner_id WHERE c.owner_id=:owner AND d.id=:id "
                    "AND d.state='ready' AND d.generation=:generation "
                    "AND c.generation=:generation "
                    "AND c.ordinal=:ordinal AND d.index_version=:version FOR SHARE OF d"
                ),
                {
                    "owner": owner,
                    "id": hit.document_id,
                    "generation": hit.generation,
                    "ordinal": hit.ordinal,
                    "version": INDEX_VERSION,
                },
            ).one_or_none()
            if row is None or row[0] != hit.text:
                raise DocumentError(409, "source_unavailable")

    def check_selection(
        self, connection: Connection, owner: UUID, selection: list[UUID] | None, lock: bool = False
    ) -> bool:
        if selection == []:
            raise DocumentError(422, "selection_unavailable")
        statement = text(
            "SELECT id,state,index_version FROM documents WHERE owner_id=:owner "
            "AND state<>'deleting'"
            + (" AND id IN :selection" if selection is not None else "")
            + (" FOR SHARE" if lock else "")
        )
        if selection is not None:
            statement = statement.bindparams(bindparam("selection", expanding=True))
        rows = (
            connection.execute(statement, {"owner": owner, "selection": selection}).mappings().all()
        )
        if selection is not None:
            if len(rows) != len(set(selection)):
                raise DocumentError(404, "selection_unavailable")
            if any(
                row["state"] != "ready" or row["index_version"] != INDEX_VERSION for row in rows
            ):
                raise DocumentError(409, "selection_unavailable")
        return any(
            row["state"] == "ready" and row["index_version"] == INDEX_VERSION for row in rows
        )

    def candidates(
        self, owner: UUID, selection: list[UUID] | None, vector: list[float]
    ) -> list[SearchHit]:
        validate_vectors([vector], 1)
        # MATERIALIZED makes the authorization boundary precede vector ranking explicitly.
        statement = text(
            "WITH eligible AS MATERIALIZED (SELECT c.*,d.filename FROM index_chunks c "
            "JOIN documents d ON d.id=c.document_id AND d.owner_id=c.owner_id "
            "JOIN index_runs r ON r.document_id=c.document_id AND r.owner_id=c.owner_id "
            "AND r.generation=c.generation WHERE c.owner_id=:owner AND d.state='ready' "
            "AND d.generation=c.generation AND "
            "d.index_version=:version AND r.index_version=:version "
            "AND c.embedding IS NOT NULL "
            + ("AND d.id IN :selection " if selection is not None else "")
            + ") SELECT document_id,generation,ordinal,filename,text,token_count,kind,start_number,"
            "end_number,start_offset,end_offset,1-(embedding <=> CAST(:vector AS vector)) AS score "
            "FROM eligible ORDER BY embedding <=> CAST(:vector AS "
            "vector),document_id,ordinal LIMIT 50"
        )
        if selection is not None:
            statement = statement.bindparams(bindparam("selection", expanding=True))
        with self.engine.begin() as connection:
            if selection is not None:
                self.check_selection(connection, owner, selection, lock=True)
            rows = connection.execute(
                statement,
                {
                    "owner": owner,
                    "selection": selection,
                    "version": INDEX_VERSION,
                    "vector": json.dumps(vector),
                },
            ).mappings()
            return [SearchHit.model_validate(dict(row)) for row in rows]
