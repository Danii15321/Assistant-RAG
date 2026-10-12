import os
from collections.abc import Iterator

import pytest
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url


@pytest.fixture
def database(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[Engine, Config]]:
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL required; use scripts/test_database.py")
    parsed = make_url(url)
    if parsed.database != "assistant_rag_test" or parsed.host not in {
        "db",
        "localhost",
        "127.0.0.1",
    }:
        pytest.fail("Integration tests require the dedicated local assistant_rag_test database")
    monkeypatch.setenv("DATABASE_URL", url)
    engine = create_engine(url)
    config = Config("alembic.ini")
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    try:
        yield engine, config
    finally:
        engine.dispose()
