from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.llm import ModelChoice
from app.models.search import Question


class MessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: ModelChoice = "groq"
    request_id: UUID
    question: Question
    document_ids: list[UUID] | None = Field(default=None, min_length=1, max_length=50)
    allow_external_processing: bool = False

    @field_validator("document_ids")
    @classmethod
    def unique_documents(cls, value: list[UUID] | None) -> list[UUID] | None:
        return list(dict.fromkeys(value)) if value is not None else None


class Conversation(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime


class Exchange(BaseModel):
    id: UUID
    model: ModelChoice = "groq"
    request_id: UUID
    ordinal: int
    question: str
    document_ids: list[UUID] | None
    state: Literal["pending", "answered", "insufficient_context", "failed"]
    answer: dict[str, Any] | None
    error_code: str | None
    created_at: datetime
    completed_at: datetime | None
