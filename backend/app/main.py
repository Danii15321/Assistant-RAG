from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.answers import router as answers_router
from app.api.conversations import router as conversations_router
from app.api.documents import router as documents_router
from app.api.health import router
from app.api.identity import router as identity_router
from app.api.search import router as search_router
from app.config import Settings, build_engine
from app.models.document import DocumentError
from app.services.identity import TokenVerifier, TrustedKeySource


def create_app(settings: Settings | None = None) -> FastAPI:
    configuration = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = build_engine(configuration)
        app.state.engine = engine
        app.state.token_verifier = (
            TokenVerifier(
                configuration.auth_issuer,
                configuration.auth_audience,
                TrustedKeySource(configuration.auth_jwks_url),
            )
            if configuration.auth_issuer and configuration.auth_jwks_url
            else None
        )
        try:
            yield
        finally:
            if engine is not None:
                engine.dispose()

    app = FastAPI(title="Assistant RAG", version="0.1.0", lifespan=lifespan)

    app.state.settings = configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[configuration.auth_issuer] if configuration.auth_issuer else [],
        allow_methods=["PUT"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.exception_handler(DocumentError)
    async def document_error(request: Request, error: DocumentError) -> JSONResponse:
        return JSONResponse(
            {"code": error.code}, status_code=error.status, headers={"cache-control": "no-store"}
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, error: SQLAlchemyError) -> JSONResponse:
        return JSONResponse(
            {"code": "service_unavailable"}, status_code=503, headers={"cache-control": "no-store"}
        )

    @app.middleware("http")
    async def private_cache_control(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        if request.url.path.startswith("/api/v1/"):
            response.headers["cache-control"] = "no-store"
        return response

    app.include_router(router)
    app.include_router(identity_router)
    app.include_router(documents_router)
    app.include_router(search_router)
    app.include_router(answers_router)
    app.include_router(conversations_router)
    return app


app = create_app()
