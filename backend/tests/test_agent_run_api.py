"""Stage 2 Agent Run HTTP contract and identity-isolation tests."""

from http import HTTPStatus

import pytest
from httpx import AsyncClient

from tests.test_profile_api import bearer, guest_login, profile_body


@pytest.mark.asyncio
async def test_create_get_cancel_and_idempotency_contract(api_client: AsyncClient) -> None:
    token, _, _ = await guest_login(api_client)
    await api_client.put(
        "/api/v1/profile",
        json=profile_body(),
        headers={**bearer(token), "Idempotency-Key": "stage2-profile"},
    )
    headers = {**bearer(token), "Idempotency-Key": "stage2-run"}
    first = await api_client.post(
        "/api/v1/agent-runs",
        json={"message": "帮我制定未来五周计划", "hint_intent": "create_plan"},
        headers=headers,
    )
    repeated = await api_client.post(
        "/api/v1/agent-runs",
        json={"message": "不同内容仍返回同一幂等 Run"},
        headers=headers,
    )
    run_id = first.json()["run_id"]
    fetched = await api_client.get(f"/api/v1/agent-runs/{run_id}", headers=bearer(token))
    query_token_attempt = await api_client.get(
        f"/api/v1/agent-runs/{run_id}/events",
        params={"access_token": token},
    )
    conflict = await api_client.post(
        "/api/v1/agent-runs",
        json={"message": "并发第二个 Run"},
        headers={**bearer(token), "Idempotency-Key": "stage2-other-run"},
    )
    cancelled = await api_client.post(
        f"/api/v1/agent-runs/{run_id}/cancel",
        json={"reason": "user_abort"},
        headers={**bearer(token), "Idempotency-Key": "stage2-cancel"},
    )

    assert first.status_code == HTTPStatus.ACCEPTED
    assert repeated.json()["run_id"] == run_id
    assert fetched.status_code == HTTPStatus.OK
    assert fetched.json()["status"] == "pending"
    assert query_token_attempt.status_code == HTTPStatus.UNAUTHORIZED
    assert conflict.status_code == HTTPStatus.CONFLICT
    assert conflict.json()["error"]["code"] == "STATE_RUN_ALREADY_ACTIVE"
    assert cancelled.status_code == HTTPStatus.ACCEPTED
    assert cancelled.json()["cancel_requested"] is True


@pytest.mark.asyncio
async def test_agent_run_api_rejects_user_id_and_hides_other_users(
    api_client: AsyncClient,
) -> None:
    token_a, user_a, _ = await guest_login(api_client)
    token_b, _, _ = await guest_login(api_client)
    invalid = await api_client.post(
        "/api/v1/agent-runs",
        json={"message": "制定计划", "user_id": user_a},
        headers={**bearer(token_a), "Idempotency-Key": "invalid-user-id"},
    )
    created = await api_client.post(
        "/api/v1/agent-runs",
        json={"message": "制定计划"},
        headers={**bearer(token_a), "Idempotency-Key": "isolated-run"},
    )
    hidden = await api_client.get(
        f"/api/v1/agent-runs/{created.json()['run_id']}",
        headers=bearer(token_b),
    )
    hidden_events = await api_client.get(
        f"/api/v1/agent-runs/{created.json()['run_id']}/events",
        headers=bearer(token_b),
    )
    no_plan = await api_client.get("/api/v1/plans/active", headers=bearer(token_b))
    no_tasks = await api_client.get("/api/v1/tasks", headers=bearer(token_b))

    assert invalid.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert invalid.json()["error"]["code"] == "VALIDATION_RUN_INVALID"
    assert hidden.status_code == HTTPStatus.NOT_FOUND
    assert hidden_events.status_code == HTTPStatus.NOT_FOUND
    assert no_plan.status_code == HTTPStatus.NOT_FOUND
    assert no_tasks.status_code == HTTPStatus.OK
    assert no_tasks.json()["items"] == []
