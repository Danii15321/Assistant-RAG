from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from app.api.answers import make_active_checker, make_answer_service
from app.api.documents import Owner
from app.api.identity import get_repository, require_identity
from app.models.conversation import Conversation, Exchange, MessageRequest
from app.repositories.conversations import ConversationRepository
from app.repositories.identity import IdentityRepository
from app.services.conversations import ConversationService
from app.services.identity import VerifiedIdentity

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])


def get_conversations(request: Request) -> ConversationRepository:
    if request.app.state.engine is None:
        raise HTTPException(503, "Service unavailable")
    return ConversationRepository(request.app.state.engine)


Repository = Annotated[ConversationRepository, Depends(get_conversations)]


@router.post("", response_model=Conversation, status_code=201)
def create(owner: Owner, repository: Repository) -> Conversation:
    return repository.create(owner)


@router.get("", response_model=list[Conversation])
def conversations(
    owner: Owner,
    repository: Repository,
    offset: int = Query(0, ge=0, le=10000),
    limit: int = Query(20, ge=1, le=50),
) -> list[Conversation]:
    return repository.list(owner, offset, limit)


@router.get("/{conversation_id}", response_model=Conversation)
def details(conversation_id: UUID, owner: Owner, repository: Repository) -> Conversation:
    return repository.get(owner, conversation_id)


@router.get("/{conversation_id}/messages", response_model=list[Exchange])
def messages(
    conversation_id: UUID,
    owner: Owner,
    repository: Repository,
    offset: int = Query(0, ge=0, le=100),
    limit: int = Query(20, ge=1, le=100),
) -> list[Exchange]:
    return repository.messages(owner, conversation_id, offset, limit)


@router.post("/{conversation_id}/messages", response_model=Exchange)
def send(
    conversation_id: UUID,
    body: MessageRequest,
    request: Request,
    response: Response,
    owner: Owner,
    repository: Repository,
    identity: Annotated[VerifiedIdentity, Depends(require_identity)],
    identities: Annotated[IdentityRepository, Depends(get_repository)],
) -> Exchange:
    exchange = ConversationService(repository, make_answer_service(request)).execute(
        owner,
        identity.session_id,
        conversation_id,
        body,
        make_active_checker(request, identity, identities),
    )
    if exchange.state == "pending":
        response.status_code = 202
    return exchange


@router.delete("/{conversation_id}", status_code=204)
def delete(conversation_id: UUID, owner: Owner, repository: Repository) -> Response:
    repository.delete(owner, conversation_id)
    return Response(status_code=204)
