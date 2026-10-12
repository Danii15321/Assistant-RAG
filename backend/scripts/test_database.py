"""Run migrations/vector tests only on a dedicated database in the local Compose stack."""

import os
import subprocess
import sys

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url


def main() -> int:
    raw_url = os.environ["DATABASE_URL"]
    url = make_url(raw_url)
    if url.host != "db" or url.database != "assistant_rag":
        raise RuntimeError("This helper requires the local Compose assistant_rag database")
    test_name = "assistant_rag_test"
    with psycopg.connect(
        host=url.host,
        user=url.username,
        password=url.password,
        dbname=url.database,
        autocommit=True,
    ) as connection:
        exists = connection.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (test_name,)
        ).fetchone()
        if not exists:
            connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(test_name)))
    test_url = url.set(database=test_name).render_as_string(hide_password=False)
    environment = {**os.environ, "TEST_DATABASE_URL": test_url}
    return subprocess.call(
        [sys.executable, "-m", "pytest", "-q", "-m", "integration"], env=environment
    )


if __name__ == "__main__":
    raise SystemExit(main())
