"""Authenticated Stage 3 daily Review endpoints."""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, status

from app.api.dependencies import get_current_user, get_review_service
from app.core.security import AuthenticatedUser
from app.schemas.errors import ErrorResponse
from app.schemas.reviews import (
    ReviewCreateRequest,
    ReviewListResponse,
    ReviewResponse,
    StartNextPlanResponse,
)
from app.services.reviews import ReviewService

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.post(
    "",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
async def create_review(
    payload: ReviewCreateRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[ReviewService, Depends(get_review_service)],
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=64),
    ],
) -> ReviewResponse:
    return await service.create(
        user_id=current_user.id,
        payload=payload,
        idempotency_key=idempotency_key,
    )


@router.get(
    "",
    response_model=ReviewListResponse,
    responses={401: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
async def list_reviews(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[ReviewService, Depends(get_review_service)],
    plan_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    cursor: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ReviewListResponse:
    return await service.list_reviews(
        user_id=current_user.id,
        plan_id=plan_id,
        date_from=date_from,
        date_to=date_to,
        cursor=cursor,
        limit=limit,
    )


@router.post(
    "/{review_id}/start-next-plan",
    response_model=StartNextPlanResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
async def start_next_plan(
    review_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[ReviewService, Depends(get_review_service)],
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=64),
    ],
) -> StartNextPlanResponse:
    return await service.start_next_plan(
        review_id=review_id,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
    )
