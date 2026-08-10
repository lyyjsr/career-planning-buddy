"""Goal Brief clarification and human-confirmation contract tests."""

from http import HTTPStatus

import pytest
from httpx import AsyncClient

from tests.test_profile_api import bearer, guest_login, profile_body


@pytest.mark.asyncio
async def test_goal_brief_requires_confirmation_before_agent_run(
    api_client: AsyncClient,
) -> None:
    token, _, _ = await guest_login(api_client)
    await api_client.put(
        "/api/v1/profile",
        json=profile_body(),
        headers={**bearer(token), "Idempotency-Key": "goal-brief-profile"},
    )
    headers = {**bearer(token), "Idempotency-Key": "goal-brief-create"}
    created = await api_client.post(
        "/api/v1/goal-briefs",
        json={
            "message": "设计一个面向岗位的项目",
            "hint_intent": "create_plan",
        },
        headers=headers,
    )
    repeated = await api_client.post(
        "/api/v1/goal-briefs",
        json={
            "message": "设计一个面向岗位的项目",
            "hint_intent": "create_plan",
        },
        headers=headers,
    )

    assert created.status_code == HTTPStatus.CREATED
    body = created.json()
    assert body["status"] == "awaiting_confirmation"
    assert body["duration_weeks"] == 4
    assert body["project_goal"] == "设计一个面向岗位的项目"
    assert repeated.json()["goal_brief_id"] == body["goal_brief_id"]

    me_before = await api_client.get("/api/v1/me", headers=bearer(token))
    assert me_before.json()["active_run"] is None
    assert me_before.json()["active_goal_brief"]["goal_brief_id"] == body["goal_brief_id"]

    confirmed = await api_client.post(
        f"/api/v1/goal-briefs/{body['goal_brief_id']}/confirm",
        json={"version": body["version"]},
        headers=bearer(token),
    )
    assert confirmed.status_code == HTTPStatus.ACCEPTED
    assert confirmed.json()["goal_brief"]["status"] == "confirmed"
    assert confirmed.json()["run"]["status"] == "pending"

    me_after = await api_client.get("/api/v1/me", headers=bearer(token))
    assert me_after.json()["active_goal_brief"] is None
    assert me_after.json()["active_run"]["run_id"] == confirmed.json()["run"]["run_id"]
