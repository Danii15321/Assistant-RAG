from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.exc import SQLAlchemyError

from app.adapters.storage_factory import make_storage
from app.api.identity import get_repository, require_identity
from app.models.document import (
    Document,
    DocumentError,
    FinalizeRequest,
    Passage,
    Unit,
    UploadRequest,
)
from app.repositories.documents import DocumentRepository
from app.repositories.identity import IdentityRepository
from app.services.documents import DocumentService
from app.services.identity import VerifiedIdentity

router = APIRouter(prefix="/api/v1", tags=["documents"])


def get_service(request: Request) -> DocumentService:
    if request.app.state.engine is None:
        raise HTTPException(503, "Service unavailable")
    try:
        return DocumentService(
            DocumentRepository(request.app.state.engine),
            make_storage(request.app.state.settings),
            request.app.state.settings,
        )
    except OSError as error:
        raise HTTPException(503, "Service unavailable") from error


def owner(
    identity: Annotated[VerifiedIdentity, Depends(require_identity)],
    repository: Annotated[IdentityRepository, Depends(get_repository)],
) -> UUID:
    try:
        return repository.current_user(identity.subject).id
    except SQLAlchemyError as error:
        raise HTTPException(503, "Service unavailable") from error


Owner = Annotated[UUID, Depends(owner)]
Service = Annotated[DocumentService, Depends(get_service)]


@router.post("/documents/uploads", status_code=201)
def reserve_upload(
    body: UploadRequest,
    request: Request,
    owner_id: Owner,
    service: Service,
    identity: Annotated[VerifiedIdentity, Depends(require_identity)],
) -> dict[str, object]:
    document, token = service.reserve(owner_id, identity.session_id, body)
    public_url = request.app.state.settings.upload_public_url.rstrip("/")
    return {
        "document": document.model_dump(mode="json"),
        "upload_url": f"{public_url}/api/v1/uploads/{document.id}/content",
        "upload_token": token,
        "expires_in": 600,
    }


@router.put("/uploads/{document_id}/content", status_code=204)
async def upload_content(document_id: UUID, request: Request, service: Service) -> Response:
    if request.app.state.settings.cloud_runtime:
        raise DocumentError(404, "not_found")
    if request.headers.get("origin") != request.app.state.settings.auth_issuer:
        raise HTTPException(403, "Invalid origin")
    header = request.headers.get("authorization", "")
    if not header.startswith("Bearer ") or len(header) > 100:
        raise DocumentError(404, "not_found")
    await service.upload(document_id, header[7:], request)
    return Response(status_code=204)


@router.post("/documents", response_model=Document, status_code=202)
def finalize(
    body: FinalizeRequest, response: Response, owner_id: Owner, service: Service
) -> Document:
    document, duplicate = service.finalize(owner_id, body.upload_id)
    if duplicate:
        response.status_code = 200
    return document


@router.get("/documents", response_model=list[Document])
def list_documents(
    owner_id: Owner,
    service: Service,
    offset: int = Query(0, ge=0, le=10000),
    limit: int = Query(50, ge=1, le=50),
) -> list[Document]:
    return service.repository.list_documents(owner_id, offset, limit)


@router.get("/documents/{document_id}", response_model=Document)
def details(document_id: UUID, owner_id: Owner, service: Service) -> Document:
    return service.repository.get(owner_id, document_id)


@router.get("/documents/{document_id}/extraction", response_model=list[Unit])
def extraction(
    document_id: UUID,
    owner_id: Owner,
    service: Service,
    offset: int = Query(0, ge=0, le=10000),
    limit: int = Query(20, ge=1, le=50),
) -> list[Unit]:
    return service.repository.units(owner_id, document_id, offset, limit)


@router.post("/documents/{document_id}/retry", response_model=Document, status_code=202)
def retry(document_id: UUID, owner_id: Owner, service: Service) -> Document:
    return service.repository.retry(owner_id, document_id)


@router.get("/documents/{document_id}/passages", response_model=list[Passage])
def passages(
    document_id: UUID,
    owner_id: Owner,
    service: Service,
    offset: int = Query(0, ge=0, le=20000),
    limit: int = Query(10, ge=1, le=20),
) -> list[Passage]:
    return service.repository.passages(owner_id, document_id, offset, limit)


@router.delete("/documents/{document_id}", status_code=202)
def delete(document_id: UUID, owner_id: Owner, service: Service) -> dict[str, str]:
    service.repository.delete(owner_id, document_id)
    return {"state": "deleting"}
