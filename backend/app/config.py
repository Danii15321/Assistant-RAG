import os
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import Engine, create_engine


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")
    database_url: str | None = Field(default=None, repr=False)
    database_url_unpooled: str | None = Field(default=None, repr=False)
    cloud_runtime: bool = False
    frontend_internal_url: str | None = None
    internal_worker_secret: SecretStr | None = Field(default=None, repr=False)
    blob_host: str | None = None
    app_public_url: str | None = None
    auth_issuer: str | None = None
    auth_jwks_url: str | None = None
    auth_audience: str = "assistant-rag-api"
    private_storage_path: Path = Path("/data/private")
    upload_public_url: str = "http://localhost:8000"
    max_file_bytes: int = Field(default=20 * 1024 * 1024, gt=0)
    user_storage_bytes: int = Field(default=100 * 1024 * 1024, gt=0)
    global_storage_bytes: int = Field(default=600 * 1024 * 1024, gt=0)
    embedding_path: Path = Path("/opt/models/e5")
    search_threshold: float = Field(default=0.81, ge=-1, le=1)
    groq_api_key: SecretStr | None = Field(default=None, repr=False)
    groq_api_key_file: Path = Path("/run/secrets/llm/groq_api_key")
    llm_free_plan_confirmed: bool = False
    llm_model: Literal["openai/gpt-oss-120b"] = "openai/gpt-oss-120b"
    llm_test_endpoint: str | None = None

    @model_validator(mode="after")
    def cloud_configuration(self) -> "Settings":
        if self.cloud_runtime:
            if not (self.internal_worker_secret and self.blob_host and self.database_url_unpooled):
                raise ValueError("Incomplete cloud configuration")
            if not self.blob_host.endswith(".private.blob.vercel-storage.com"):
                raise ValueError("A private Blob store is required")
            self.database_url = self.database_url_unpooled.replace(
                "postgresql://", "postgresql+psycopg://", 1
            ).replace("postgres://", "postgresql+psycopg://", 1)
            # Session advisory locks require a direct connection, never transaction pooling.
            if "-pooler." in self.database_url:
                raise ValueError("Worker requires a direct database endpoint")
            self.auth_issuer = self.app_public_url or "https://" + os.environ["VERCEL_URL"]
            # Vercel rejects circular bindings. Reach the frontend through this
            # deployment's own origin; requests carry the scoped runtime OIDC token.
            self.frontend_internal_url = self.auth_issuer
            self.auth_jwks_url = self.frontend_internal_url.rstrip("/") + "/api/auth/jwks"
            self.private_storage_path = Path("/tmp/assistant-rag-private")
        return self


def build_engine(settings: Settings) -> Engine | None:
    if settings.database_url is None:
        return None
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=3,
        max_overflow=2,
        pool_timeout=3,
        connect_args={
            "connect_timeout": 10 if settings.cloud_runtime else 3,
            "options": "-c statement_timeout=10000"
            if settings.cloud_runtime
            else "-c statement_timeout=3000",
        },
    )
