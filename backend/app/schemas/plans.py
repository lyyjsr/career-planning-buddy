"""Plan and Task resource response contracts."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.schemas.agent_runs import WeeklyFocusCandidate
from app.schemas.base import StrictModel
from app.schemas.enums import AbandonedReason, PlanStatus, TaskStatus, TaskType


class TaskUpdateRequest(StrictModel):
    state: Literal[
        TaskStatus.IN_PROGRESS,
        TaskStatus.COMPLETED,
        TaskStatus.ABANDONED,
    ]
    version: int = Field(ge=1)
    actual_minutes: int | None = Field(default=None, ge=0, le=1440)
    abandoned_reason: AbandonedReason | None = None
    abandoned_reason_text: str | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def validate_state_fields(self) -> "TaskUpdateRequest":
        if self.state == TaskStatus.COMPLETED:
            if self.actual_minutes is None:
                raise ValueError("actual_minutes is required when completing a task")
            if self.abandoned_reason is not None or self.abandoned_reason_text is not None:
                raise ValueError("abandonment fields are not allowed for completed tasks")
        elif self.state == TaskStatus.ABANDONED:
            if self.abandoned_reason is None:
                raise ValueError("abandoned_reason is required when abandoning a task")
            if (
                self.abandoned_reason == AbandonedReason.OTHER
                and self.abandoned_reason_text is None
            ):
                raise ValueError("abandoned_reason_text is required for reason other")
            if (
                self.abandoned_reason != AbandonedReason.OTHER
                and self.abandoned_reason_text is not None
            ):
                raise ValueError("abandoned_reason_text is only allowed for reason other")
            if self.actual_minutes is not None:
                raise ValueError("actual_minutes is only allowed for completed tasks")
        elif (
            self.actual_minutes is not None
            or self.abandoned_reason is not None
            or self.abandoned_reason_text is not None
        ):
            raise ValueError("completion and abandonment fields do not apply to this state")
        return self


class TaskResponse(StrictModel):
    task_id: UUID
    plan_id: UUID
    title: str
    task_type: TaskType
    scheduled_date: date
    order_index: int = Field(ge=0)
    state: TaskStatus
    starter_action: str
    deliverable: str
    rationale: str | None
    estimated_minutes: int
    actual_minutes: int | None
    abandoned_reason: AbandonedReason | None
    abandoned_reason_text: str | None
    version: int
    started_at: datetime | None
    completed_at: datetime | None
    abandoned_at: datetime | None
    created_at: datetime


class TaskListResponse(StrictModel):
    items: list[TaskResponse]


class TaskUpdateResponse(StrictModel):
    task: TaskResponse
    plan_status: PlanStatus
    companion_message: str


class PlanSourceResponse(StrictModel):
    kind: Literal["memory", "experience_atom", "search_source"]
    id: UUID
    available: bool
    title: str | None = None
    url: str | None = None
    snippet: str | None = None
    reliability: float | None = Field(default=None, ge=0, le=1)


class PlanSourcesResponse(StrictModel):
    items: list[PlanSourceResponse]


class ActivePlanResponse(StrictModel):
    plan_id: UUID
    status: PlanStatus
    plan_date: date
    horizon_start: date
    horizon_end: date
    overall_direction: str
    weekly_focus: list[WeeklyFocusCandidate]
    summary: str
    rationale: str
    adjustment_reason: str | None
    sources: list[PlanSourceResponse] = Field(default_factory=list)
    tasks: list[TaskResponse]
    companion_message: str | None
    version: int
    adopted_at: datetime | None
    created_at: datetime


class PlanListResponse(StrictModel):
    items: list[ActivePlanResponse]
    next_cursor: UUID | None
