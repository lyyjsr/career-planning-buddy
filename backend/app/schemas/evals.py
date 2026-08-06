"""Strict request/response schemas for the Eval V2 HTTP control plane."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.schemas.base import StrictModel


class EvalRunCreateRequest(StrictModel):
    """Body of POST /api/v1/eval/runs.

    The server loads the named dataset (mirroring the CLI) instead of asking
    the caller to ship a fully-validated ``DatasetBundle`` over the wire.
    """

    dataset: Literal["stage5", "runtime-smoke"] = "stage5"
    cases: list[str] | None = Field(
        default=None,
        description="Subset of case_ids to keep (default: all cases in the dataset).",
    )
    provider_mode: Literal["mock", "fixture", "live"] | None = None
    trial_count: int = Field(default=1, ge=1, le=100)
    grade: bool = True
    baseline_experiment_id: UUID | None = None


class EvalRunCreatedResponse(StrictModel):
    experiment_id: UUID
    status: Literal["draft"]
    status_url: str
    report_url: str


class TrialStatusSummary(StrictModel):
    trial_id: UUID
    case_id: str
    status: str
    run_status: str | None
    result_kind: str | None
    error_code: str | None


class EvalRunStatusResponse(StrictModel):
    experiment_id: UUID
    status: Literal["draft", "running", "completed", "failed", "cancelled"]
    dataset_id: str
    trial_count: int
    started_at: datetime | None
    finished_at: datetime | None
    trials: list[TrialStatusSummary]


class EvalRunReportResponse(StrictModel):
    """Strongly-typed envelope for ``ExperimentReport.to_dict()`` (PR-6)."""

    experiment_id: UUID
    experiment_status: str
    trial_count: int
    completed_trial_count: int
    scored_trial_count: int
    hard_gate_pass_fraction: float
    any_score_generated: bool
    trials: list[dict[str, object]]
    # PR-9a: per-case + per-experiment statistics. Both default-empty so
    # pre-PR-9a consumers continue to deserialise cleanly.
    case_stats: dict[str, dict[str, object]] = Field(default_factory=dict)
    experiment_stats: dict[str, object] | None = None
    # PR-9b: report revision (content-hash driven, not call-driven) plus
    # the fact-record of any implised cancel request.
    revision: int = 0
    cancel_requested_at: datetime | None = None


class EvalRunListItem(StrictModel):
    """One row in the paginated Experiment listing."""

    experiment_id: UUID
    status: str
    execution_mode: str
    dataset_id: str
    trial_count: int
    started_at: datetime | None
    finished_at: datetime | None
    cancel_requested_at: datetime | None


class EvalRunListResponse(StrictModel):
    """Paginated response for GET /api/v1/eval/runs."""

    items: list[EvalRunListItem]
    next_offset: int | None = None


class EvalRunProgressResponse(StrictModel):
    """Lightweight progress view distinct from the heavy report payload."""

    experiment_id: UUID
    status: str
    trial_count: int
    completed_count: int
    running_count: int
    pending_count: int
    failed_count: int
    cancelled_count: int
    timed_out_count: int
    in_flight_trial_ids: list[UUID]
    cancel_requested_at: datetime | None
    estimated_progress: float
    # Best-effort "last seen event"-style pointers. Optional: not surfaced
    # when no agent_step row has emitted yet.
    last_event_type: str | None = None
    last_event_at: datetime | None = None


class EvalRunCancelResponse(StrictModel):
    """Response body for POST /api/v1/eval/runs/{id}/cancel.

    ``status`` is the Experiment's current status at the time the request
    was processed; it is NOT promoted to ``cancelled`` synchronously.
    ``cancel_requested`` is False if the Experiment was already terminal
    (no fresh timestamp stamped, request is a no-op).
    """

    experiment_id: UUID
    status: str
    cancel_requested: bool
    cancel_requested_at: datetime | None = None
