from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from app.adapters.groq import GroqProvider
from app.api.documents import Owner
from app.api.identity import get_repository, require_identity
from app.models.answer import AnswerRequest, AnswerResponse
from app.models.document import DocumentError
from app.repositories.generation import GenerationRepository
from app.repositories.identity import IdentityRepository
from app.repositories.query_jobs import QueryJobRepository
from app.repositories.search import SearchRepository
from app.services.answers import AnswerService
from app.services.identity import IdentityUnavailable, InvalidIdentity, VerifiedIdentity
from app.services.search import SearchService

router = APIRouter(prefix="/api/v1", tags=["answers"])


def make_active_checker(
    request: Request, identity: VerifiedIdentity, identities: IdentityRepository
) -> Callable[[], bool]:
    def active() -> bool:
        try:
            request.app.state.token_verifier.verify(request.headers["authorization"][7:])
            return identities.session_is_active(identity)
        except InvalidIdentity:
            return False
        except IdentityUnavailable:
            raise DocumentError(503, "llm_unavailable") from None

    return active


def make_answer_service(request: Request) -> AnswerService:
    engine = request.app.state.engine
    if engine is None:
        raise HTTPException(503, "Service unavailable")
    repository = SearchRepository(engine)
    settings = request.app.state.settings
    return AnswerService(
        SearchService(
            repository,
            QueryJobRepository(engine),
            settings.search_threshold,
            progress=request.app.state.cloud_worker.query_step if settings.cloud_runtime else None,
        ),
        GenerationRepository(engine),
        GroqProvider(settings),
        repository.verify_hits,
    )


@router.post("/answers", response_model=AnswerResponse)
def answer(
    body: AnswerRequest,
    request: Request,
    owner: Owner,
    identity: Annotated[VerifiedIdentity, Depends(require_identity)],
    identities: Annotated[IdentityRepository, Depends(get_repository)],
) -> AnswerResponse:
    return make_answer_service(request).execute(
        owner, identity.session_id, body, make_active_checker(request, identity, identities)
    )
