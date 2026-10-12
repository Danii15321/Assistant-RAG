from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError


@contextmanager
def cpu_guard(engine: Engine) -> Iterator[bool]:
    """Hold the worker CPU lock even when a cancelled job/session is deleted."""
    with engine.connect() as connection:
        acquired = bool(
            connection.execute(text("SELECT pg_try_advisory_lock(3719306)")).scalar_one()
        )
        try:
            yield acquired
        finally:
            if acquired:
                try:
                    connection.execute(text("SELECT pg_advisory_unlock(3719306)"))
                except SQLAlchemyError:
                    # Never return a connection with a session lock to the pool.
                    connection.invalidate()
                    raise
