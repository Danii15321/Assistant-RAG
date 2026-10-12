from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.exc import SQLAlchemyError

from app.models.user import UserProfile
from app.repositories.identity import IdentityRepository
from app.services.identity import IdentityUnavailable, InvalidIdentity, VerifiedIdentity

router = APIRouter(prefix="/api/v1/users", tags=["identity"])
bearer = HTTPBearer(auto_error=False)


def get_repository(request: Request) -> IdentityRepository:
    if request.app.state.engine is None:
        raise HTTPException(503, "Service unavailable")
    return IdentityRepository(request.app.state.engine)


def require_identity(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    repository: Annotated[IdentityRepository, Depends(get_repository)],
) -> VerifiedIdentity:
    if credentials is None:
        raise HTTPException(401, "Authentication required", headers={"WWW-Authenticate": "Bearer"})
    verifier = request.app.state.token_verifier
    if verifier is None:
        raise HTTPException(503, "Service unavailable")
    try:
        identity: VerifiedIdentity = verifier.verify(credentials.credentials)
        if not repository.session_is_active(identity):
            raise InvalidIdentity
        return identity
    except InvalidIdentity as error:
        raise HTTPException(
            401, "Invalid session", headers={"WWW-Authenticate": "Bearer"}
        ) from error
    except (IdentityUnavailable, SQLAlchemyError) as error:
        raise HTTPException(503, "Service unavailable") from error


@router.get("/me", response_model=UserProfile)
def current_user(
    response: Response,
    identity: Annotated[VerifiedIdentity, Depends(require_identity)],
    repository: Annotated[IdentityRepository, Depends(get_repository)],
) -> UserProfile:
    response.headers["cache-control"] = "no-store"
    try:
        return repository.current_user(identity.subject)
    except SQLAlchemyError as error:
        raise HTTPException(503, "Service unavailable") from error


@router.get("/{user_id}", response_model=UserProfile)
def owned_user(
    user_id: UUID,
    response: Response,
    identity: Annotated[VerifiedIdentity, Depends(require_identity)],
    repository: Annotated[IdentityRepository, Depends(get_repository)],
) -> UserProfile:
    response.headers["cache-control"] = "no-store"
    try:
        user = repository.owned_user(identity.subject, user_id)
    except SQLAlchemyError as error:
        raise HTTPException(503, "Service unavailable") from error
    if user is None:
        raise HTTPException(404, "Resource not found")
    return user
