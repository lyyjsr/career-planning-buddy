"""Strict Stage 3 daily review API contracts."""

from datetime import date, datetime
from uuid import UUID

from pydantic import Field

from app.schemas.base import StrictModel
from app.schemas.enums import NextPlanAction, ReplanMode, RunStatus


class ReviewCreateRequest(StrictModel):
    plan_id: UUID
    review_date: date
    mood: int = Field(ge=1, le=5)
    blockers: str | None = Field(default=None, min_length=1, max_length=500)
    adjustment_request: str | None = Field(default=None, min_length=1, max_length=300)
    free_text: str | None = Field(default=None, min_length=1, max_length=1000)


class ReviewResponse(StrictModel):
    review_id: UUID
    plan_id: UUID
    review_date: date
    mood: int
    blockers: str | None
    adjustment_request: str | None
    free_text: str | None
    completed_count: int = Field(ge=0)
    abandoned_count: int = Field(ge=0)
    suggested_replan: bool
    replan_reason: str | None
    next_plan_action: NextPlanAction
    companion_message: str
    next_plan_run_id: UUID | None
    created_at: datetime


class ReviewListResponse(StrictModel):
    items: list[ReviewResponse]
    next_cursor: UUID | None


class StartNextPlanResponse(StrictModel):
    run_id: UUID
    status: RunStatus
    replan_mode: ReplanMode
    events_url: str
