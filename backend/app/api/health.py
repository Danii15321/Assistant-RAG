from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from app.repositories.health import DatabaseHealthRepository
from app.services.readiness import ReadinessService

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok", "unavailable"]


def get_readiness(request: Request) -> ReadinessService:
    return ReadinessService(DatabaseHealthRepository(request.app.state.engine))


@router.get("/health", response_model=HealthResponse)
def liveness(response: Response) -> HealthResponse:
    response.headers["Cache-Control"] = "no-store"
    return HealthResponse(status="ok")


@router.get(
    "/api/v1/health", response_model=HealthResponse, responses={503: {"model": HealthResponse}}
)
def readiness(
    response: Response, service: Annotated[ReadinessService, Depends(get_readiness)]
) -> HealthResponse:
    response.headers["Cache-Control"] = "no-store"
    if not service.is_ready():
        response.status_code = 503
        return HealthResponse(status="unavailable")
    return HealthResponse(status="ok")
