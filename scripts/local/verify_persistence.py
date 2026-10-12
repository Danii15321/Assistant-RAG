"""Recreate only this project's database container and verify a synthetic vector persists."""

import hashlib
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run(*arguments: str) -> str:
    result = subprocess.run(
        ["docker", "compose", *arguments],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def query(statement: str) -> str:
    return run(
        "exec",
        "-T",
        "db",
        "psql",
        "-U",
        "assistant_rag",
        "-d",
        "assistant_rag_test",
        "-v",
        "ON_ERROR_STOP=1",
        "-At",
        "-c",
        statement,
    )


def main() -> None:
    vector = str([1, 0] + [0] * 382)
    query(
        "CREATE TABLE IF NOT EXISTS foundation_persistence "
        "(id text PRIMARY KEY, embedding vector(384)); "
        f"INSERT INTO foundation_persistence VALUES ('step1', '{vector}') "
        "ON CONFLICT (id) DO UPDATE SET embedding = excluded.embedding;"
    )
    select = "SELECT id, embedding::text FROM foundation_persistence ORDER BY id"
    before = hashlib.sha256(query(select).encode()).hexdigest()
    old_id = run("ps", "-q", "db")
    run("up", "-d", "--no-deps", "--force-recreate", "--wait", "db")
    new_id = run("ps", "-q", "db")
    after = hashlib.sha256(query(select).encode()).hexdigest()
    if not old_id or old_id == new_id or before != after:
        raise RuntimeError("Database recreation or vector persistence verification failed")
    query("DROP TABLE foundation_persistence")
    print("Conteneur PostgreSQL recréé ; vecteur de 384 dimensions conservé ; fixture nettoyée.")


if __name__ == "__main__":
    main()
