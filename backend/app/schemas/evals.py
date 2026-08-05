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
