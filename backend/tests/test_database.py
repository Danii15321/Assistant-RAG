import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, text

from app.repositories.health import DatabaseHealthRepository

pytestmark = pytest.mark.integration


def test_migrations_vector_search_and_reapplication(database: tuple[Engine, Config]) -> None:
    engine, config = database
    repository = DatabaseHealthRepository(engine)
    assert not repository.is_ready()
    command.upgrade(config, "head")
    assert repository.is_ready()
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE fixture (id int PRIMARY KEY, embedding vector(384))"))
        for identifier, coordinates in [(1, [1, 0]), (2, [0, 1])]:
            vector = str(coordinates + [0] * 382)
            connection.execute(
                text("INSERT INTO fixture VALUES (:id, CAST(:vector AS vector))"),
                {"id": identifier, "vector": vector},
            )
    command.upgrade(config, "head")
    query = str([1, 0] + [0] * 382)
    with engine.connect() as connection:
        nearest = connection.execute(
            text("SELECT id FROM fixture ORDER BY embedding <=> CAST(:query AS vector) LIMIT 1"),
            {"query": query},
        ).scalar_one()
        assert nearest == 1
        assert connection.execute(text("SELECT count(*) FROM fixture")).scalar_one() == 2


def test_extension_migration_can_be_reversed_on_empty_database(
    database: tuple[Engine, Config],
) -> None:
    engine, config = database
    command.upgrade(config, "head")
    command.downgrade(config, "base")
    assert not DatabaseHealthRepository(engine).is_ready()
    command.upgrade(config, "head")
    assert DatabaseHealthRepository(engine).is_ready()


def test_private_profiles_and_foreign_key(database: tuple[Engine, Config]) -> None:
    from datetime import datetime, timedelta, timezone
    from uuid import uuid4

    from sqlalchemy.exc import IntegrityError

    from app.repositories.identity import IdentityRepository
    from app.services.identity import VerifiedIdentity

    engine, config = database
    command.upgrade(config, "head")
    now = datetime.now(timezone.utc)
    with engine.begin() as connection:
        for subject in ["alice", "bob"]:
            connection.execute(
                text(
                    'INSERT INTO auth_user (id, name, email, "emailVerified", username) '
                    "VALUES (:id, :id, :email, false, :username)"
                ),
                {
                    "id": subject,
                    "email": f"{subject}@accounts.invalid",
                    "username": f"{subject}.test",
                },
            )
            connection.execute(
                text(
                    'INSERT INTO auth_session (id, "userId", token, "expiresAt", "updatedAt") '
                    "VALUES (:id, :subject, :id, :expires, :now)"
                ),
                {
                    "id": f"session-{subject}",
                    "subject": subject,
                    "expires": now + timedelta(days=1),
                    "now": now,
                },
            )
    repository = IdentityRepository(engine)
    alice = repository.current_user("alice")
    bob = repository.current_user("bob")
    assert alice.id != bob.id
    assert repository.current_user("alice").id == alice.id
    assert repository.owned_user("alice", alice.id) == alice
    assert repository.owned_user("alice", bob.id) is None
    identity = VerifiedIdentity("alice", "session-alice")
    assert repository.session_is_active(identity)
    assert not repository.session_is_active(VerifiedIdentity("bob", "session-alice"))
    with engine.begin() as connection:
        connection.execute(
            text("DELETE FROM auth_session WHERE id = :id"), {"id": identity.session_id}
        )
    assert not repository.session_is_active(identity)
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text("INSERT INTO users (id, auth_user_id) VALUES (:id, 'missing')"), {"id": uuid4()}
        )
