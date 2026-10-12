import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from app.adapters.embeddings import E5Tokenizer
from app.adapters.resident_embeddings import ResidentE5Encoder
from app.models.document import DocumentError
from app.repositories.indexes import IndexRepository
from app.services.chunking import split_units


class Indexer:
    def __init__(self, repository: IndexRepository, model_path: Path) -> None:
        self.repository = repository
        self.model_path = model_path
        self.tokenizer: E5Tokenizer | None = None
        self.encoder = ResidentE5Encoder(model_path)

    def close(self) -> None:
        self.encoder.close()

    def run(self, job: Mapping[str, Any]) -> None:
        if job["attempts"] > 3:
            self.repository.fail(job, "attempts_exhausted")
            return
        try:
            if not self.repository.exists(job):
                if self.tokenizer is None:
                    self.tokenizer = E5Tokenizer(self.model_path)
                units = self.repository.units(job)
                if not units:
                    self.repository.fail(job, "no_text")
                    return
                chunks = split_units(units, self.tokenizer)
                if not self.repository.prepare(job, chunks):
                    return
            batch = self.repository.batch(job)
            if not batch:
                return
            vectors = self.encoder.encode([row["text"] for row in batch])
            self.repository.save(job, [row["ordinal"] for row in batch], vectors)
        except DocumentError as error:
            self.repository.fail(job, error.code)
        except ValueError as error:
            code = (
                str(error)
                if str(error) in {"passage_quota", "index_incompatible"}
                else "index_invalid"
            )
            self.repository.fail(job, code)
        except (OSError, RuntimeError, subprocess.TimeoutExpired):
            self.repository.fail(job, "embedding_unavailable", transient=True)
