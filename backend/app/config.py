from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import Engine, create_engine


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")
    database_url: str | None = Field(default=None, repr=False)
    auth_issuer: str | None = None
    auth_jwks_url: str | None = None
    auth_audience: str = "assistant-rag-api"
    private_storage_path: Path = Path("/data/private")
    upload_public_url: str = "http://localhost:8000"
    max_file_bytes: int = Field(default=20 * 1024 * 1024, gt=0)
    user_storage_bytes: int = Field(default=100 * 1024 * 1024, gt=0)
    global_storage_bytes: int = Field(default=600 * 1024 * 1024, gt=0)
    embedding_path: Path = Path("/opt/models/e5")
    search_threshold: float = Field(default=0.84, ge=-1, le=1)
    groq_api_key: SecretStr | None = Field(default=None, repr=False)
    groq_api_key_file: Path = Path("/run/secrets/llm/groq_api_key")
    llm_free_plan_confirmed: bool = False
    llm_model: Literal["openai/gpt-oss-120b"] = "openai/gpt-oss-120b"
    llm_test_endpoint: str | None = None


def build_engine(settings: Settings) -> Engine | None:
    if settings.database_url is None:
        return None
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=3,
        max_overflow=2,
        pool_timeout=3,
        connect_args={"connect_timeout": 3, "options": "-c statement_timeout=3000"},
    )
