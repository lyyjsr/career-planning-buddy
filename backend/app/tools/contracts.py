"""Serializable Stage 4 Tool contracts and handler registration metadata."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.base import StrictModel
from app.schemas.enums import GoalType, RunIntent


class ModelToolSpec(StrictModel):
    name: str
    description: str
    input_json_schema: dict[str, object]
    contract_version: str


class ToolContext(StrictModel):
    run_id: UUID
    user_id: UUID
    goal_type: GoalType
    intent: RunIntent = RunIntent.CREATE_PLAN
    requires_fresh_information: bool = False
    remaining_deadline_ms: int = Field(ge=0)


class ToolResult(StrictModel):
    tool_name: str
    data: dict[str, object]
    evidence: list["EvidenceItem"] = Field(default_factory=list)
    truncated: bool = False
    provider: str | None = None


ToolHandler = Callable[[BaseModel, ToolContext], Awaitable[BaseModel]]


class EvidenceItem(StrictModel):
    kind: Literal["memory", "experience_atom", "search_source"]
    id: UUID
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1, max_length=2000)
    reliability: float = Field(ge=0, le=1)


class MemoryLookupInput(StrictModel):
    query: str = Field(min_length=1, max_length=300)
    limit: int = Field(default=5, ge=1, le=5)


class MemoryLookupItem(StrictModel):
    memory_id: UUID
    content: str
    memory_type: str
    relevance: float = Field(ge=0, le=1)
    updated_at: datetime


class MemoryLookupOutput(StrictModel):
    items: list[MemoryLookupItem]
    evidence: list[EvidenceItem] = Field(default_factory=list)


class RagRetrieveInput(StrictModel):
    query: str = Field(min_length=1, max_length=300)
    goal_type: GoalType
    limit: int = Field(default=5, ge=1, le=5)


class RagEvidenceItem(StrictModel):
    atom_id: UUID
    title: str
    content: str
    evidence: str
    reliability: float = Field(ge=0, le=1)
    score: float = Field(ge=0, le=1)


class RagRetrieveOutput(StrictModel):
    items: list[RagEvidenceItem]
    evidence: list[EvidenceItem] = Field(default_factory=list)


class WebSearchInput(StrictModel):
    query: str = Field(min_length=1, max_length=300)
    limit: int = Field(default=5, ge=1, le=5)
    freshness_days: int | None = Field(default=None, ge=1, le=365)


class WebSearchItem(StrictModel):
    source_id: UUID
    url: str
    title: str | None
    snippet: str
    source_type: str
    reliability: float = Field(ge=0, le=1)
    retrieved_at: datetime


class WebSearchOutput(StrictModel):
    items: list[WebSearchItem]
    evidence: list[EvidenceItem] = Field(default_factory=list)


class ToolExecutionResult(StrictModel):
    success: bool
    result: ToolResult
    error_code: str | None = None
    reused: bool = False


@dataclass(frozen=True, slots=True)
class RegisteredTool:
    spec: ModelToolSpec
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    handler: ToolHandler
    timeout_seconds: float = 8
    max_result_chars: int = 6000
    stage: int = 4
    provider: str | None = None
