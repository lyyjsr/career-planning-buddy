"""Guest authentication and current-user HTTP endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.api.dependencies import (
    get_auth_service,
    get_current_user,
    get_profile_service,
)
from app.core.security import AuthenticatedUser
from app.schemas.auth import (
    GuestLoginRequest,
    GuestLoginResponse,
    MeResponse,
    UserSummary,
)
from app.schemas.errors import ErrorResponse
from app.schemas.profile import ProfileResponse
from app.services.auth import AuthService
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
) -> MeResponse:
    profile = await profile_service.get_optional(current_user.id)
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
    )
