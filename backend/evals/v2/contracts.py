"""Strict, versioned contracts for Eval Harness V2."""

import json
from datetime import date
from hashlib import sha256
from typing import Annotated, Literal, Self
from uuid import UUID, uuid4

from pydantic import Field, JsonValue, model_validator

from app.schemas.base import StrictModel

NonEmptyVersion = Annotated[str, Field(min_length=1, max_length=128)]
Sha256Hex = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


def canonical_sha256(value: object) -> str:
    """Hash a JSON-compatible value using a stable serialization."""

    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


class DatasetManifest(StrictModel):
    manifest_version: Literal["2"]
    dataset_id: Annotated[str, Field(min_length=1, max_length=64)]
    dataset_version: NonEmptyVersion
    case_schema_version: Literal["2"]
    source_path: Annotated[str, Field(min_length=1, max_length=500)]
    source_format: Literal["eval_case_v2_jsonl", "legacy_stage5_jsonl"]
    source_sha256: Sha256Hex
    case_count: Annotated[int, Field(ge=1)]


class EvalProfile(StrictModel):
    goal_type: Literal["job_search", "internship", "career_change", "skill_growth"]
    stage: Literal["exploring", "preparing", "applying", "interviewing"]
    time_budget_minutes: Annotated[int, Field(ge=15, le=480)]
    skill_level: Literal["beginner", "intermediate", "advanced"]


class EvalScenario(StrictModel):
    user_request: Annotated[str, Field(min_length=1, max_length=10_000)]
    profile: EvalProfile | None
    hint_intent: Literal["create_plan", "replan"] | None = None
    replan_mode: Literal["continue", "adjust"] | None = None
    initial_plan: dict[str, JsonValue] | None = None
    initial_tasks: list[dict[str, JsonValue]] = Field(default_factory=list)
    initial_reviews: list[dict[str, JsonValue]] = Field(default_factory=list)
    confirmed_memories: list[dict[str, JsonValue]] = Field(default_factory=list)
    unconfirmed_memory_candidates: list[dict[str, JsonValue]] = Field(default_factory=list)
    search_fixtures: dict[str, JsonValue] = Field(default_factory=dict)
    provider_fixtures: dict[str, JsonValue] = Field(default_factory=dict)
    planning_date: date


class ExpectedOutcome(StrictModel):
    result_kind: Literal["plan", "clarification", "safe_response"]
    allowed_run_statuses: list[Literal["completed", "degraded", "failed", "cancelled"]]


class TrajectoryPolicy(StrictModel):
    expected_tools: list[Literal["memory_lookup", "rag_retrieve", "web_search"]] = Field(
        default_factory=list, max_length=4
    )
    max_tool_calls: Annotated[int, Field(ge=0, le=20)] = 4
    require_terminal_event: bool = True


class RubricCriterion(StrictModel):
    criterion_id: Annotated[str, Field(min_length=1, max_length=100)]
    description: Annotated[str, Field(min_length=1, max_length=500)]
    hard_gate: bool = False


class EvalRubric(StrictModel):
    criteria: Annotated[list[RubricCriterion], Field(min_length=1)]


class EvalFaultPlan(StrictModel):
    fault_type: Annotated[str, Field(min_length=1, max_length=64)]
    target: Annotated[str, Field(min_length=1, max_length=128)]
    parameters: dict[str, JsonValue] = Field(default_factory=dict)


class EvalCase(StrictModel):
    case_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")]
    schema_version: Literal["2"]
    dataset_id: Annotated[str, Field(min_length=1, max_length=64)]
    dataset_version: NonEmptyVersion
    scenario: EvalScenario
    expected_outcome: ExpectedOutcome
    trajectory_policy: TrajectoryPolicy
    rubric: EvalRubric
    difficulty: Literal["regression", "capability", "adversarial"]
    tags: list[Annotated[str, Field(min_length=1, max_length=64)]]
    fixture_version: NonEmptyVersion
    fixture_hash: Sha256Hex
    counterfactual_group_id: Annotated[str, Field(min_length=1, max_length=128)] | None = None
    variant: Annotated[str, Field(min_length=1, max_length=64)] | None = None
    fault_plan: EvalFaultPlan | None = None

    def fixture_payload(self) -> dict[str, object]:
        """Return all versioned Case content covered by ``fixture_hash``."""

        return self.model_dump(mode="json", exclude={"fixture_hash"})

    @model_validator(mode="after")
    def validate_fixture_hash(self) -> Self:
        expected = canonical_sha256(self.fixture_payload())
        if self.fixture_hash != expected:
            raise ValueError(
                f"fixture_hash mismatch for {self.case_id}: expected {expected}"
            )
        return self


class ExperimentCreate(StrictModel):
    experiment_id: UUID = Field(default_factory=uuid4)
    dataset_id: Annotated[str, Field(min_length=1, max_length=64)]
    dataset_version: NonEmptyVersion
    dataset_hash: Sha256Hex
    git_commit: Annotated[str, Field(pattern=r"^[0-9a-f]{7,64}$")]
    graph_version: NonEmptyVersion
    prompt_version: NonEmptyVersion
    model_version: NonEmptyVersion
    tool_version: NonEmptyVersion
    context_version: NonEmptyVersion
    memory_version: NonEmptyVersion
    execution_mode: Literal["mock_provider", "fixture_provider", "live_provider"]
    variant_role: Literal["baseline", "candidate"]
    baseline_experiment_id: UUID | None = None
    trial_count: Annotated[int, Field(ge=1, le=100)] = 1
    agent_variant: Annotated[str | None, Field(min_length=1, max_length=64)] = None

    @model_validator(mode="after")
    def validate_baseline_role(self) -> Self:
        if self.baseline_experiment_id == self.experiment_id:
            raise ValueError("an experiment cannot use itself as baseline")
        if self.variant_role == "baseline" and self.baseline_experiment_id is not None:
            raise ValueError("a baseline experiment cannot reference another baseline")
        if self.variant_role == "candidate" and self.baseline_experiment_id is None:
            raise ValueError("a candidate experiment requires baseline_experiment_id")
        return self

    def frozen_config(self) -> dict[str, object]:
        return self.model_dump(
            mode="json", exclude={"experiment_id", "baseline_experiment_id", "trial_count"}
        )


class GradeResult(StrictModel):
    grader_name: Annotated[str, Field(min_length=1, max_length=128)]
    grader_version: NonEmptyVersion
    domain: Literal["task", "behavioral", "tool", "model", "system", "safety"]
    metric_type: Literal["boolean", "numeric", "categorical"]
    score: float | None = None
    passed: bool | None = None
    categorical_value: Annotated[str, Field(min_length=1, max_length=128)] | None = None
    hard_gate: bool
    threshold: float | None = None
    evidence_item_ids: list[UUID] = Field(default_factory=list)
    evidence: dict[str, JsonValue]
    rationale: Annotated[str, Field(min_length=1, max_length=4_000)] | None = None

    @model_validator(mode="after")
    def validate_metric_value(self) -> Self:
        if self.metric_type == "boolean":
            valid = (
                self.passed is not None
                and self.score is None
                and self.categorical_value is None
            )
        elif self.metric_type == "numeric":
            valid = self.score is not None and self.categorical_value is None
        else:
            valid = self.categorical_value is not None and self.score is None
        if not valid:
            raise ValueError(f"invalid value fields for {self.metric_type} metric")
        if self.hard_gate and self.passed is None:
            raise ValueError("hard-gate GradeResult requires passed")
        if self.metric_type != "numeric" and self.threshold is not None:
            raise ValueError("threshold is only valid for numeric metrics")
        return self
