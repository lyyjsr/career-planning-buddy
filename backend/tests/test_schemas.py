"""Stage 1 enum and profile contract tests."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.schemas.auth import GuestLoginRequest
from app.schemas.enums import (
    CareerStage,
    GoalType,
    PlanStatus,
    RunResultKind,
    RunStatus,
    SkillLevel,
    TaskStatus,
)
from app.schemas.profile import ProfilePatchRequest, ProfilePutRequest


def test_stage_one_enums_match_contract_values() -> None:
    assert [item.value for item in GoalType] == [
        "ai_backend",
        "agent_app",
        "backend_java",
        "data_engineer",
        "fullstack",
        "other",
    ]
    assert [item.value for item in CareerStage] == [
        "exploring",
        "preparing",
        "applying",
        "interviewing",
    ]
    assert [item.value for item in SkillLevel] == ["beginner", "intermediate", "advanced"]
    assert [item.value for item in RunStatus] == [
        "pending",
        "running",
        "completed",
        "degraded",
        "failed",
        "cancelled",
    ]
    assert [item.value for item in RunResultKind] == [
        "plan",
        "clarification",
        "safe_response",
    ]
    assert [item.value for item in PlanStatus] == [
        "generated",
        "active",
        "completed",
        "archived",
    ]
    assert [item.value for item in TaskStatus] == [
        "pending",
        "in_progress",
        "completed",
        "abandoned",
        "expired",
    ]


def test_guest_device_id_length_is_bounded() -> None:
    with pytest.raises(ValidationError):
        GuestLoginRequest(device_id="short")


def test_profile_rejects_unknown_user_id() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        ProfilePutRequest.model_validate(
            {
                "user_id": "3f42b5fa-16b8-45d4-a095-3c2d5dc1a35b",
                "goal_type": "agent_app",
                "stage": "preparing",
                "time_budget_minutes": 120,
                "skill_level": "intermediate",
            }
        )


@pytest.mark.parametrize("minutes", [14, 481])
def test_profile_time_budget_is_bounded(minutes: int) -> None:
    with pytest.raises(ValidationError):
        ProfilePutRequest(
            goal_type=GoalType.AGENT_APP,
            stage=CareerStage.PREPARING,
            time_budget_minutes=minutes,
            skill_level=SkillLevel.INTERMEDIATE,
        )


def test_profile_deadline_cannot_be_in_the_past() -> None:
    with pytest.raises(ValidationError, match="deadline cannot be earlier"):
        ProfilePutRequest(
            goal_type=GoalType.AGENT_APP,
            stage=CareerStage.PREPARING,
            time_budget_minutes=120,
            skill_level=SkillLevel.INTERMEDIATE,
            deadline=datetime.now(UTC).date() - timedelta(days=1),
        )


def test_profile_preferences_reject_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        ProfilePutRequest.model_validate(
            {
                "goal_type": "agent_app",
                "stage": "preparing",
                "time_budget_minutes": 120,
                "skill_level": "intermediate",
                "preferences": {"unknown": True},
            }
        )


def test_profile_patch_requires_an_update() -> None:
    with pytest.raises(ValidationError, match="at least one profile field"):
        ProfilePatchRequest(version=1)
