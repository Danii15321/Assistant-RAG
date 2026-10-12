from sqlalchemy import Engine, text

SCHEMA_REVISION = "0008_cloud_wakeups"


class DatabaseHealthRepository:
    def __init__(self, engine: Engine | None) -> None:
        self.engine = engine

    def is_ready(self) -> bool:
        if self.engine is None:
            return False
        with self.engine.connect() as connection:
            extension = connection.execute(
                text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")
            ).scalar_one()
            version_table = connection.execute(
                text("SELECT to_regclass('public.alembic_version') IS NOT NULL")
            ).scalar_one()
            if not extension or not version_table:
                return False
            revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one_or_none()
            return bool(revision == SCHEMA_REVISION)
