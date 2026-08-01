"""User profile request and response contracts."""

from datetime import UTC, date, datetime

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.schemas.base import StrictModel
from app.schemas.enums import CareerStage, GoalType, SkillLevel


class ProfilePreferences(StrictModel):
    """Strictly bounded first-version profile preferences."""

    target_companies: list[str] = Field(default_factory=list, max_length=20)
    preferred_time_slot: str | None = Field(default=None, min_length=1, max_length=32)
    weekly_available_days: list[int] = Field(default_factory=list, max_length=7)

    @field_validator("target_companies")
    @classmethod
    def validate_target_companies(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values]
        if any(not value or len(value) > 100 for value in normalized):
            raise ValueError("target company names must contain 1 to 100 characters")
        if len(set(normalized)) != len(normalized):
            raise ValueError("target companies must be unique")
        return normalized

    @field_validator("weekly_available_days")
    @classmethod
    def validate_weekly_days(cls, values: list[int]) -> list[int]:
        if any(value < 1 or value > 7 for value in values):
            raise ValueError("weekly available days must be between 1 and 7")
        if len(set(values)) != len(values):
            raise ValueError("weekly available days must be unique")
        return values


class ProfileFields(StrictModel):
    """Fields shared by complete profile writes and responses."""

    goal_type: GoalType
    stage: CareerStage
    time_budget_minutes: int = Field(ge=15, le=480)
    skill_level: SkillLevel
    skill_summary: str | None = Field(default=None, max_length=2000)
    deadline: date | None = None
    preferences: ProfilePreferences = Field(default_factory=ProfilePreferences)

    @field_validator("deadline")
    @classmethod
    def validate_deadline(cls, value: date | None) -> date | None:
        if value is not None and value < datetime.now(UTC).date():
            raise ValueError("deadline cannot be earlier than today")
        return value


class ProfilePutRequest(ProfileFields):
    """Complete profile creation or replacement."""


class ProfilePatchRequest(StrictModel):
    """Versioned partial profile update."""

    version: int = Field(ge=1)
    goal_type: GoalType | None = None
    stage: CareerStage | None = None
    time_budget_minutes: int | None = Field(default=None, ge=15, le=480)
    skill_level: SkillLevel | None = None
    skill_summary: str | None = Field(default=None, max_length=2000)
    deadline: date | None = None
    preferences: ProfilePreferences | None = None

    @field_validator("deadline")
    @classmethod
    def validate_deadline(cls, value: date | None) -> date | None:
        if value is not None and value < datetime.now(UTC).date():
            raise ValueError("deadline cannot be earlier than today")
        return value

    @model_validator(mode="after")
    def validate_updates(self) -> "ProfilePatchRequest":
        update_fields = self.model_fields_set - {"version"}
        if not update_fields:
            raise ValueError("at least one profile field must be supplied")
        required_fields = {
            "goal_type",
            "stage",
            "time_budget_minutes",
            "skill_level",
            "preferences",
        }
        if any(
            field in update_fields and getattr(self, field) is None for field in required_fields
        ):
            raise ValueError("required profile fields cannot be null")
        return self


class ProfileResponse(ProfileFields):
    """Complete persisted profile."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    version: int = Field(ge=1)
