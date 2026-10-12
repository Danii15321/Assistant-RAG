import json
import time
from collections.abc import Callable, Sequence
from uuid import UUID

from app.models.document import DocumentError
from app.models.search import SearchHit, SearchRequest, SearchResponse
from app.repositories.query_jobs import QueryJobRepository
from app.repositories.search import SearchRepository
from app.services.embeddings import INDEX_VERSION

SEARCH_VERSION = "cosine-exact-v1|candidates50|overlap0.8|budget1500|user-history-v1"


def query_text(request: SearchRequest) -> str:
    previous = [m.content for m in request.history if m.role == "user"][-2:]
    return (
        (
            "Questions précédentes : "
            + " / ".join(previous)
            + "\nQuestion actuelle : "
            + request.question
        )
        if previous
        else request.question
    )


def select_hits(
    hits: Sequence[SearchHit], top_k: int, threshold: float, budget: int = 1500
) -> list[SearchHit]:
    selected: list[SearchHit] = []
    seen: set[str] = set()
    tokens = 0
    for hit in hits:
        normalized = " ".join(hit.text.split())
        redundant = any(
            old.document_id == hit.document_id
            and old.generation == hit.generation
            and max(
                0, min(old.end_offset, hit.end_offset) - max(old.start_offset, hit.start_offset)
            )
            >= 0.8 * min(old.end_offset - old.start_offset, hit.end_offset - hit.start_offset)
            for old in selected
        )
        if (
            hit.score < threshold
            or normalized in seen
            or redundant
            or tokens + hit.token_count > budget
        ):
            continue
        selected.append(hit)
        seen.add(normalized)
        tokens += hit.token_count
        if len(selected) == top_k:
            break
    return selected


class SearchService:
    def __init__(
        self,
        repository: SearchRepository,
        jobs: QueryJobRepository,
        threshold: float,
        timeout: float = 105,
        progress: Callable[[], None] | None = None,
    ) -> None:
        self.repository, self.jobs = repository, jobs
        self.threshold, self.timeout = threshold, timeout
        self.progress = progress

    def execute(
        self, owner: UUID, session: str, body: SearchRequest, active_session: Callable[[], bool]
    ) -> SearchResponse:
        started = time.monotonic()
        hits: list[SearchHit] = []
        available = self.repository.validate_selection(owner, body.document_ids)
        if available:
            identifier = self.jobs.submit(owner, session, query_text(body))
            try:
                while True:
                    if not active_session():
                        raise DocumentError(401, "session_expired")
                    if self.progress is not None:
                        self.progress()
                    row = self.jobs.result(owner, identifier)
                    if row is None:
                        raise DocumentError(503, "search_unavailable")
                    if row["status"] == "failed":
                        code = row["error_code"]
                        raise DocumentError(422 if code == "query_too_long" else 503, code)
                    if row["status"] == "done":
                        vector = json.loads(row["embedding"])
                        break
                    if time.monotonic() - started >= self.timeout:
                        raise DocumentError(503, "search_timeout")
                    time.sleep(0.2)
            finally:
                self.jobs.remove(owner, identifier)
            # A selection deleted/reindexed while encoding is an error, never widened.
            self.repository.validate_selection(owner, body.document_ids)
            hits = select_hits(
                self.repository.candidates(owner, body.document_ids, vector),
                body.top_k,
                self.threshold,
            )
        if not active_session():
            raise DocumentError(401, "session_expired")
        return SearchResponse(
            status="matches" if hits else "no_match" if available else "empty_corpus",
            hits=hits,
            threshold=self.threshold,
            top_k=body.top_k,
            context_tokens=sum(h.token_count for h in hits),
            search_version=SEARCH_VERSION,
            index_version=INDEX_VERSION,
            elapsed_ms=round((time.monotonic() - started) * 1000, 2),
        )
