import time
from collections.abc import Callable
from uuid import UUID

from app.adapters.groq import Provider, ProviderError
from app.models.answer import AnswerRequest, AnswerResponse, AnswerSource
from app.models.document import DocumentError
from app.repositories.generation import GenerationRepository
from app.services.generation import PROMPT_VERSION, build_context, validate_answer
from app.services.search import SearchService


class AnswerService:
    def __init__(
        self,
        search: SearchService,
        repository: GenerationRepository,
        provider: Provider,
        verify_sources: Callable[[UUID, list[AnswerSource]], None],
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.search, self.repository, self.provider = search, repository, provider
        self.verify_sources, self.sleep, self.clock = verify_sources, sleep, clock

    def execute(
        self, owner: UUID, session: str, body: AnswerRequest, active_session: Callable[[], bool]
    ) -> AnswerResponse:
        token_reservation = 3100 if body.model == "groq" else 24576
        prompt_version = PROMPT_VERSION
        if body.model != "groq":
            output_limit = 1200 if body.model == "gpt-6-luna" else 4096
            prompt_version += f"|openai-bytes16000|completion-override{output_limit}"
        started = self.clock()
        result = self.search.execute(owner, session, body, active_session)
        if not result.hits:
            return AnswerResponse(
                state="insufficient_context",
                answer="Je ne trouve pas de passage pertinent dans les documents consultés.",
                claims=[],
                sources=[],
                model=body.model,
                provider_called=False,
                prompt_version=prompt_version,
                elapsed_ms=round((self.clock() - started) * 1000, 2),
            )
        if not body.allow_external_processing:
            raise DocumentError(403, "external_processing_required")
        if not self.provider.ready():
            raise DocumentError(503, "llm_not_configured")
        context = build_context(body, result.hits)
        deadline = self.clock() + 55
        if not active_session():
            raise DocumentError(401, "session_expired")
        self.verify_sources(owner, context.sources)
        lease, attempt = self.repository.acquire(owner, session, token_reservation)
        try:
            for number in range(3):
                outcome = "failed"
                completion = None
                try:
                    if not active_session():
                        outcome = "revoked"
                        raise DocumentError(401, "session_expired")
                    if not self.repository.active(lease) or self.clock() >= deadline:
                        raise DocumentError(503, "generation_timeout")
                    self.verify_sources(owner, context.sources)
                    completion = self.provider.generate(context.messages, deadline)
                    if not active_session():
                        outcome = "revoked"
                        raise DocumentError(401, "session_expired")
                    if not self.repository.active(lease) or self.clock() >= deadline:
                        raise DocumentError(503, "generation_timeout")
                    self.verify_sources(owner, context.sources)
                    answer = validate_answer(completion.content, context.sources)
                    outcome = answer.state
                    cited = {e.source_id for c in answer.claims for e in c.evidence}
                    return AnswerResponse(
                        state=answer.state,
                        answer="\n\n".join(
                            c.text
                            + " "
                            + " ".join(
                                f"[{ref}]" for ref in dict.fromkeys(e.source_id for e in c.evidence)
                            )
                            for c in answer.claims
                        )
                        if answer.claims
                        else (
                            "Les passages consultés ne contiennent pas la réponse à cette question."
                        ),
                        claims=answer.claims,
                        sources=[s for s in context.sources if s.source_id in cited],
                        model=body.model,
                        provider_called=True,
                        prompt_version=prompt_version,
                        elapsed_ms=round((self.clock() - started) * 1000, 2),
                    )
                except ProviderError as error:
                    if error.code == "openai_provider_quota":
                        raise DocumentError(429, error.code) from None
                    if error.code == "provider_quota":
                        self.repository.block(error.retry_after)
                        raise DocumentError(429, "provider_quota") from None
                    if (
                        not error.transient
                        or number == 2
                        or self.clock() + error.retry_after >= deadline
                    ):
                        raise DocumentError(
                            503
                            if error.code
                            in {"generation_timeout", "llm_unavailable", "llm_not_configured"}
                            else 502,
                            error.code,
                        ) from None
                    self.sleep(error.retry_after)
                finally:
                    self.repository.finish_attempt(
                        attempt,
                        outcome,
                        completion.prompt_tokens if completion else None,
                        completion.completion_tokens if completion else None,
                    )
                if not active_session():
                    raise DocumentError(401, "session_expired")
                attempt = self.repository.reserve(owner, session, lease, token_reservation)
            raise DocumentError(503, "llm_unavailable")
        finally:
            self.repository.release(lease)
