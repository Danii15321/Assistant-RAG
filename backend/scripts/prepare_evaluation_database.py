"""Create only the dedicated local evaluation database, without credentials in logs."""

import psycopg
from sqlalchemy.engine import make_url

from app.config import Settings


def main() -> None:
    url = make_url(Settings().database_url or "")
    if url.host != "db" or url.database != "assistant_rag":
        raise RuntimeError("Local Compose database required")
    with psycopg.connect(
        host=url.host,
        user=url.username,
        password=url.password,
        dbname=url.database,
        autocommit=True,
    ) as connection:
        if not connection.execute(
            "SELECT 1 FROM pg_database WHERE datname='assistant_rag_evaluation'"
        ).fetchone():
            connection.execute("CREATE DATABASE assistant_rag_evaluation")


if __name__ == "__main__":
    main()
