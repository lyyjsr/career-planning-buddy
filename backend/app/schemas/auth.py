"""Authentication and current-user API contracts."""

from typing import Literal
from uuid import UUID

from pydantic import Field, JsonValue

from app.schemas.base import StrictModel
from app.schemas.profile import ProfileResponse


class GuestLoginRequest(StrictModel):
    """Optional stable browser device identifier for Guest reuse."""

    device_id: str | None = Field(default=None, min_length=16, max_length=128)


class UserSummary(StrictModel):
    """Public user fields safe for client identity restoration."""

    id: UUID
    display_name: str | None
    role: Literal["user", "dev"]


class GuestLoginResponse(StrictModel):
    """Bearer token returned by Guest authentication."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(ge=1)
    user: UserSummary


class MeResponse(StrictModel):
    """Stage 1 home restoration aggregate."""

    user: UserSummary
    profile_complete: bool
    profile: ProfileResponse | None
    active_plan: None = None
    today_tasks: list[JsonValue] = Field(default_factory=list)
    latest_review: None = None
    active_run: None = None
