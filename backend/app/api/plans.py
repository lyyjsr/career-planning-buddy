"""Authenticated Stage 2 Plan and Task query endpoints."""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_current_user, get_plan_query_service
from app.core.security import AuthenticatedUser
from app.schemas.enums import PlanStatus, TaskStatus
from app.schemas.errors import ErrorResponse
from app.schemas.plans import (
    ActivePlanResponse,
    PlanListResponse,
    PlanSourcesResponse,
    TaskListResponse,
    TaskUpdateRequest,
    TaskUpdateResponse,
)
from app.services.plans import PlanQueryService

plans_router = APIRouter(prefix="/plans", tags=["plans"])
tasks_router = APIRouter(prefix="/tasks", tags=["tasks"])


@plans_router.get(
    "/active",
    response_model=ActivePlanResponse,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def get_active_plan(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[PlanQueryService, Depends(get_plan_query_service)],
) -> ActivePlanResponse:
    return await service.get_active(current_user.id)


@plans_router.get(
    "",
    response_model=PlanListResponse,
    responses={401: {"model": ErrorResponse}},
)
async def list_plans(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[PlanQueryService, Depends(get_plan_query_service)],
    status: PlanStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    cursor: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> PlanListResponse:
    return await service.list_plans(
        user_id=current_user.id,
        status=status.value if status else None,
        date_from=date_from,
        date_to=date_to,
        cursor=cursor,
        limit=limit,
    )


@plans_router.get(
    "/{plan_id}/sources",
    response_model=PlanSourcesResponse,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def get_plan_sources(
    plan_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[PlanQueryService, Depends(get_plan_query_service)],
) -> PlanSourcesResponse:
    return await service.get_sources(plan_id, current_user.id)


@plans_router.get(
    "/{plan_id}",
    response_model=ActivePlanResponse,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def get_plan(
    plan_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[PlanQueryService, Depends(get_plan_query_service)],
) -> ActivePlanResponse:
    return await service.get_plan(plan_id, current_user.id)


@tasks_router.get(
    "",
    response_model=TaskListResponse,
    responses={401: {"model": ErrorResponse}},
)
async def list_tasks(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[PlanQueryService, Depends(get_plan_query_service)],
    scheduled_date: Annotated[date | None, Query(alias="date")] = None,
    state: TaskStatus | None = None,
    plan_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> TaskListResponse:
    return await service.list_tasks(
        user_id=current_user.id,
        scheduled_date=scheduled_date,
        state=state.value if state else None,
        plan_id=plan_id,
        limit=limit,
    )


@tasks_router.patch(
    "/{task_id}",
    response_model=TaskUpdateResponse,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
async def update_task(
    task_id: UUID,
    payload: TaskUpdateRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[PlanQueryService, Depends(get_plan_query_service)],
) -> TaskUpdateResponse:
    return await service.update_task(
        task_id=task_id,
        user_id=current_user.id,
        payload=payload,
    )
