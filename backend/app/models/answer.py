from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models.search import SearchHit, SearchRequest


class AnswerRequest(SearchRequest):
    allow_external_processing: bool = False


ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=600)]


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str
    quote: ShortText


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: ShortText
    evidence: list[Evidence] = Field(min_length=1, max_length=3)


class GeneratedAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    state: Literal["answered", "insufficient_context"]
    claims: list[Claim] = Field(max_length=4)


class AnswerSource(SearchHit):
    source_id: str


class AnswerResponse(BaseModel):
    state: Literal["answered", "insufficient_context"]
    answer: str
    claims: list[Claim]
    sources: list[AnswerSource]
    provider_called: bool
    prompt_version: str
    elapsed_ms: float
