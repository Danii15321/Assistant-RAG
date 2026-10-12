from alembic import context
from sqlalchemy import create_engine, pool

from app.config import Settings

config = context.config
database_url = Settings().database_url
if not database_url:
    raise RuntimeError("DATABASE_URL is required for migrations")


def run_migrations_offline() -> None:
    context.configure(url=database_url, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    assert database_url is not None
    engine = create_engine(database_url, poolclass=pool.NullPool)
    try:
        with engine.connect() as connection:
            context.configure(connection=connection)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
