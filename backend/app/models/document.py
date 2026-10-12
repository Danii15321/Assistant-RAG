from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UploadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filename: str = Field(min_length=1, max_length=200)
    size_bytes: int = Field(gt=0)
    content_type: str = Field(max_length=120)


class FinalizeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    upload_id: UUID


class Document(BaseModel):
    id: UUID
    filename: str
    size_bytes: int
    extension: str
    state: Literal["uploading", "queued", "processing", "ready", "failed", "deleting"]
    stage: str
    error_code: str | None
    created_at: datetime
    unit_count: int
    parser_version: str | None
    chunk_count: int = 0
    embedded_count: int = 0
    index_version: str | None = None


class Unit(BaseModel):
    ordinal: int
    kind: str
    number: int
    text: str


class Passage(BaseModel):
    ordinal: int
    text: str
    token_count: int
    start_offset: int
    end_offset: int
    kind: str
    start_number: int
    end_number: int
    start_unit: int
    end_unit: int


class DocumentError(Exception):
    def __init__(self, status: int, code: str) -> None:
        self.status = status
        self.code = code
        super().__init__(code)
