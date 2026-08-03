"""Guest authentication and current-user HTTP endpoints."""

from typing import Annotated
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_auth_service,
    get_current_user,
    get_db_session,
    get_profile_service,
)
from app.core.exceptions import AppError
from app.core.security import AuthenticatedUser
from app.repositories.agent_runs import AgentRunRepository
from app.repositories.reviews import ReviewRepository
from app.schemas.agent_runs import AgentRunResponse
from app.schemas.auth import (
    GuestLoginRequest,
    GuestLoginResponse,
    MeResponse,
    UserSummary,
)
from app.schemas.errors import ErrorResponse
from app.schemas.plans import ActivePlanResponse, TaskResponse
from app.schemas.profile import ProfileResponse
from app.schemas.reviews import ReviewResponse
from app.services.agent_runs import AgentRunService
from app.services.auth import AuthService
from app.services.plans import PlanQueryService
from app.services.profiles import ProfileService

router = APIRouter(tags=["auth"])


@router.post(
    "/auth/guest",
    response_model=GuestLoginResponse,
    status_code=201,
    responses={
        200: {"model": GuestLoginResponse, "description": "Existing Guest reused"},
        422: {"model": ErrorResponse, "description": "Invalid request"},
    },
)
async def guest_login(
    payload: GuestLoginRequest,
    response: Response,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> GuestLoginResponse:
    result = await service.login_guest(payload.device_id)
    response.status_code = 201 if result.created else 200
    return GuestLoginResponse(
        access_token=result.access_token,
        expires_in=result.expires_in,
        user=UserSummary.model_validate(result.user, from_attributes=True),
    )


@router.get(
    "/me",
    response_model=MeResponse,
    responses={401: {"model": ErrorResponse, "description": "Invalid token"}},
)
async def get_me(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    profile_service: Annotated[ProfileService, Depends(get_profile_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MeResponse:
    user_id = current_user.id
    profile = await profile_service.get_optional(user_id)

    plan_query = PlanQueryService(session)
    active_plan: ActivePlanResponse | None = None
    today_tasks: list[TaskResponse] = []
    try:
        active_plan = await plan_query.get_active(user_id)
    except AppError as exc:
        if exc.code != "NOT_FOUND_PLAN":
            raise
    if active_plan is not None:
        task_list = await plan_query.list_tasks(
            user_id=user_id,
            scheduled_date=date.today(),
            state=None,
            plan_id=active_plan.plan_id,
            limit=20,
        )
        today_tasks = list(task_list.items)

    active_run: AgentRunResponse | None = None
    run_repo = AgentRunRepository(session)
    active_run_row = await run_repo.get_active_for_user(user_id)
    if active_run_row is not None:
        active_run = AgentRunService.to_response(active_run_row)

    latest_review: ReviewResponse | None = None
    review_repo = ReviewRepository(session)
    latest_rows = await review_repo.list_for_user(
        user_id, plan_id=None, date_from=None, date_to=None, cursor=None, limit=1
    )
    if latest_rows:
        latest_review = ReviewResponse.model_validate(latest_rows[0], from_attributes=True)

    return MeResponse(
        user=UserSummary(
            id=current_user.id,
            display_name=current_user.display_name,
            role="dev" if current_user.role == "dev" else "user",
        ),
        profile_complete=profile is not None,
        profile=(
            ProfileResponse.model_validate(profile, from_attributes=True)
            if profile is not None
            else None
        ),
        active_plan=active_plan,
        today_tasks=today_tasks,
        active_run=active_run,
        latest_review=latest_review,
    )
