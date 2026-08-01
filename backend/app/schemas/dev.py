"""Strict developer Trace, Replay, and Eval API contracts."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.schemas.base import StrictModel


class DevRunSummary(StrictModel):
    run_id: UUID
    replay_of_run_id: UUID | None
    user_ref: str
    status: str
    result_kind: str | None
    resolved_intent: str | None
    graph_version: str
    model_id: str | None
    total_tokens_in: int
    total_tokens_out: int
    total_cost_cny: Decimal
    total_latency_ms: int
    fallback_reason: str | None
    error_code: str | None
    created_at: datetime
    finished_at: datetime | None


class DevRunListResponse(StrictModel):
    items: list[DevRunSummary]
    next_cursor: UUID | None


class DevStepTrace(StrictModel):
    sequence: int
    node_name: str
    attempt: int
    status: str
    prompt_version: str | None
    model_id: str | None
    tokens_in: int
    tokens_out: int
    latency_ms: int
    input_hash: str | None
    output_hash: str | None
    trace_data: object
    error_code: str | None


class DevToolTrace(StrictModel):
    tool_call_id: UUID
    step_id: UUID
    tool_name: str
    contract_version: str
    round: int
    args: object
    args_hash: str
    result: object | None
    result_hash: str | None
    provider: str | None
    latency_ms: int
    success: bool
    error_code: str | None


class DevEventTrace(StrictModel):
    sequence: int
    event_type: str
    payload: object
    created_at: datetime


class DevSnapshot(StrictModel):
    data: object
    sha256: str


class TerminalInvariant(StrictModel):
    terminal_count: int
    terminal_is_last: bool
    valid: bool


class DevRunDetail(StrictModel):
    run: DevRunSummary
    request_text: str
    input_snapshot: DevSnapshot | None
    config_snapshot: DevSnapshot
    result: object | None
    steps: list[DevStepTrace]
    tools: list[DevToolTrace]
    events: list[DevEventTrace]
    terminal_invariant: TerminalInvariant


class ReplayRequest(StrictModel):
    tool_mode: Literal["fixture", "live"] = "fixture"


class ReplayResponse(StrictModel):
    run_id: UUID
    replay_of_run_id: UUID
    status: str
    deterministic: bool


class EvalDatasetSummary(StrictModel):
    dataset_id: str
    case_count: int = Field(ge=1)
    description: str


class EvalDatasetListResponse(StrictModel):
    items: list[EvalDatasetSummary]


class EvalStartRequest(StrictModel):
    dataset_id: str = "stage5-v1"
    case_limit: int | None = Field(default=None, ge=1, le=30)


class EvalStartResponse(StrictModel):
    experiment_id: str
    status: Literal["completed"]


class EvalExperimentResponse(StrictModel):
    experiment_id: str
    status: Literal["completed", "not_found"]
    report: object | None
