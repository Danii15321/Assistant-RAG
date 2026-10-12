from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

Question = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class HistoryMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant"]
    content: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: Question
    document_ids: list[UUID] | None = Field(default=None, min_length=1, max_length=50)
    top_k: int = Field(default=5, ge=1, le=10)
    history: list[HistoryMessage] = Field(default_factory=list, max_length=4)

    @field_validator("document_ids")
    @classmethod
    def unique_documents(cls, value: list[UUID] | None) -> list[UUID] | None:
        return list(dict.fromkeys(value)) if value is not None else None


class SearchHit(BaseModel):
    document_id: UUID
    generation: int
    ordinal: int
    filename: str
    text: str
    token_count: int
    kind: str
    start_number: int
    end_number: int
    start_offset: int
    end_offset: int
    score: float


class SearchResponse(BaseModel):
    status: Literal["matches", "no_match", "empty_corpus"]
    hits: list[SearchHit]
    threshold: float
    top_k: int
    context_tokens: int
    search_version: str
    index_version: str
    elapsed_ms: float
