import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class DatabaseProbe(Protocol):
    def is_ready(self) -> bool: ...


class ReadinessService:
    def __init__(self, database: DatabaseProbe) -> None:
        self.database = database

    def is_ready(self) -> bool:
        try:
            return self.database.is_ready()
        except Exception:
            # Driver exception messages may contain credentials or SQL parameters.
            logger.warning("Database readiness check failed")
            return False
