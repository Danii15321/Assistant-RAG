import subprocess

from app.adapters.embeddings import E5Tokenizer
from app.adapters.resident_embeddings import ResidentE5Encoder
from app.repositories.query_jobs import QueryJobRepository
from app.services.embeddings import QUERY_PREFIX


class QueryWorker:
    def __init__(self, repository: QueryJobRepository, encoder: ResidentE5Encoder) -> None:
        self.repository, self.encoder = repository, encoder
        self.tokenizer: E5Tokenizer | None = None

    def run_once(self) -> bool:
        job = self.repository.claim()
        if job is None:
            return False
        try:
            if self.tokenizer is None:
                self.tokenizer = E5Tokenizer(self.encoder.model_path)
            if len(self.tokenizer.offsets(QUERY_PREFIX + job["question"])) + 2 > 512:
                self.repository.finish(job, error="query_too_long")
            else:
                vector = self.encoder.encode([job["question"]], "query")[0]
                self.repository.finish(job, vector)
        except (ValueError, OSError, RuntimeError, subprocess.TimeoutExpired):
            self.repository.finish(job, error="search_unavailable")
        return True
