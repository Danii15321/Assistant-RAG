from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.documents import Owner
from app.api.identity import get_repository, require_identity
from app.models.document import DocumentError
from app.models.search import SearchRequest, SearchResponse
from app.repositories.identity import IdentityRepository
from app.repositories.query_jobs import QueryJobRepository
from app.repositories.search import SearchRepository
from app.services.identity import IdentityUnavailable, InvalidIdentity, VerifiedIdentity
from app.services.search import SearchService

router = APIRouter(prefix="/api/v1", tags=["search"])


@router.post("/search", response_model=SearchResponse)
def search(
    body: SearchRequest,
    request: Request,
    owner_id: Owner,
    identity: Annotated[VerifiedIdentity, Depends(require_identity)],
    identities: Annotated[IdentityRepository, Depends(get_repository)],
) -> SearchResponse:
    if request.app.state.engine is None:
        raise HTTPException(503, "Service unavailable")

    def active() -> bool:
        try:
            request.app.state.token_verifier.verify(request.headers["authorization"][7:])
            return identities.session_is_active(identity)
        except InvalidIdentity:
            return False
        except IdentityUnavailable as error:
            raise DocumentError(503, "search_unavailable") from error

    engine = request.app.state.engine
    return SearchService(
        SearchRepository(engine),
        QueryJobRepository(engine),
        request.app.state.settings.search_threshold,
        progress=request.app.state.cloud_worker.query_step
        if request.app.state.settings.cloud_runtime
        else None,
    ).execute(owner_id, identity.session_id, body, active)
