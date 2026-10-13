"""Request-bounded consumers; PostgreSQL remains the durable job outbox."""

import threading
import time

from sqlalchemy import Engine, text

from app.adapters.storage_factory import make_storage
from app.config import Settings
from app.models.document import DocumentError
from app.repositories.indexes import IndexRepository
from app.repositories.jobs import JobRepository
from app.repositories.query_jobs import QueryJobRepository
from app.worker.consumer import Consumer
from app.worker.cpu_guard import cpu_guard
from app.worker.indexer import Indexer
from app.worker.query import QueryWorker


class CloudWorker:
    def __init__(self, engine: Engine, settings: Settings) -> None:
        self.engine = engine
        self.lock = threading.Lock()
        self.indexer = Indexer(IndexRepository(engine), settings.embedding_path)
        self.jobs = JobRepository(engine)
        self.storage = make_storage(settings)
        self.consumer = Consumer(self.jobs, self.storage, self.indexer)
        self.queries = QueryWorker(QueryJobRepository(engine), self.indexer.encoder)

    def query_step(self) -> None:
        if not self.lock.acquire(blocking=False):
            return
        try:
            with cpu_guard(self.engine) as acquired:
                if acquired:
                    self.queries.run_once()
        finally:
            self.lock.release()

    def drain(self) -> bool:
        """Return True while durable work remains, including an unexpired lease."""
        if not self.lock.acquire(blocking=False):
            return True
        try:
            with cpu_guard(self.engine) as acquired:
                if not acquired:
                    return True
                self.jobs.reconcile()
                deadline = time.monotonic() + 120
                while time.monotonic() < deadline:
                    queried = self.queries.run_once()
                    ingested = self.consumer.run_once()
                    if not queried and not ingested:
                        break
                with self.engine.connect() as c:
                    return bool(
                        c.execute(
                            text("SELECT EXISTS(SELECT 1 FROM ingestion_jobs WHERE status<>'done')")
                        ).scalar_one()
                    )
        finally:
            self.lock.release()

    def reconcile(self) -> None:
        self.storage.collect_orphans(self.jobs.reconcile())

    def profile_embeddings(self) -> dict[str, object]:
        """Explicit internal probe with fixed synthetic input and normal CPU exclusion."""
        if not self.lock.acquire(blocking=False):
            raise DocumentError(429, "generation_busy")
        try:
            with cpu_guard(self.engine) as acquired:
                if not acquired:
                    raise DocumentError(429, "generation_busy")
                encoder = self.indexer.encoder
                loaded = encoder.process is not None and encoder.process.poll() is None
                durations = []
                for _ in range(2):
                    started = time.monotonic()
                    encoder.encode(["Qualification E5 sans document utilisateur."], "query")
                    durations.append(round((time.monotonic() - started) * 1000, 2))
                return {
                    "initially_loaded": loaded,
                    "first_ms": durations[0],
                    "warm_ms": durations[1],
                }
        finally:
            self.lock.release()
