import json
import subprocess
import sys
from pathlib import Path

from app.adapters.storage import PrivateStorage
from app.repositories.jobs import JobRepository
from app.services.extraction import ExtractedUnit, ExtractionError
from app.worker.indexer import Indexer


def bounded_extract(path: Path, extension: str) -> list[ExtractedUnit]:
    try:
        result = subprocess.run(
            [sys.executable, "-m", "app.worker.parser_process", str(path), extension],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=30,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise ExtractionError("extraction_timeout") from error
    if result.returncode or len(result.stdout) > 16 * 1024 * 1024:
        raise ExtractionError("extraction_limit")
    payload = json.loads(result.stdout)
    if "error" in payload:
        raise ExtractionError(payload["error"])
    return [ExtractedUnit(**unit) for unit in payload["units"]]


class Consumer:
    def __init__(
        self, repository: JobRepository, storage: PrivateStorage, indexer: Indexer | None = None
    ) -> None:
        self.repository = repository
        self.storage = storage
        self.indexer = indexer

    def run_once(self) -> bool:
        job = self.repository.claim(include_index=self.indexer is not None)
        if job is None:
            return False
        if job["kind"] == "delete":
            self.storage.delete(job["document_id"])
            self.repository.delete(job)
            return True
        if job["kind"] == "index" and self.indexer is not None:
            self.indexer.run(job)
            return True
        if job["attempts"] > 3:
            self.repository.finish(job, error="attempts_exhausted")
            return True
        try:
            with self.storage.open_file(job["document_id"]) as path:
                units = bounded_extract(path, job["extension"])
            self.repository.finish(job, units)
        except ExtractionError as error:
            self.repository.finish(job, error=error.code)
        except OSError:
            self.repository.finish(job, error="storage_unavailable", transient=True)
        return True
