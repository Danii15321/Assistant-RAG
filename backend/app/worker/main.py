import time

from sqlalchemy.exc import SQLAlchemyError

from app.adapters.storage import PrivateStorage
from app.config import Settings, build_engine
from app.repositories.indexes import IndexRepository
from app.repositories.jobs import JobRepository
from app.repositories.query_jobs import QueryJobRepository
from app.worker.consumer import Consumer
from app.worker.cpu_guard import cpu_guard
from app.worker.indexer import Indexer
from app.worker.query import QueryWorker


def main() -> None:
    settings = Settings()
    engine = build_engine(settings)
    if engine is None:
        raise RuntimeError("Worker database unavailable")
    storage = PrivateStorage(settings.private_storage_path)
    repository = JobRepository(engine)
    indexer = Indexer(IndexRepository(engine), settings.embedding_path)
    worker = Consumer(repository, storage, indexer)
    queries = QueryWorker(QueryJobRepository(engine), indexer.encoder)
    try:
        while True:
            try:
                queried = ingested = False
                with cpu_guard(engine) as acquired:
                    if acquired:
                        storage.collect_orphans(repository.reconcile())
                        queried = queries.run_once()
                        ingested = worker.run_once()
                if not queried and not ingested:
                    time.sleep(0.5)
            except (SQLAlchemyError, OSError):
                # No SQL, filenames, tokens or document text in operational logs.
                print("Ingestion temporarily unavailable", flush=True)
                time.sleep(3)
    finally:
        if worker.indexer is not None:
            worker.indexer.close()
        engine.dispose()


if __name__ == "__main__":
    main()
