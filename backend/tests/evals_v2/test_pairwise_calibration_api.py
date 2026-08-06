"""PR-9c.2 Commit 3 smoke tests for the Pairwise Calibration HTTP API."""

from __future__ import annotations

from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import TokenService
from app.models.user import User
from tests.test_profile_api import bearer, guest_login


async def _dev_login(client: AsyncClient, db_session: AsyncSession) -> str:
    _guest_token, user_id_raw, _ = await guest_login(client)
    user = await db_session.get(User, UUID(user_id_raw))
    assert user is not None
    user.role = "dev"
    await db_session.flush()
    return TokenService(get_settings()).issue(user_id=user.id, role="dev")


@pytest.mark.asyncio
async def test_calibration_latest_404_when_no_report(
    api_application: FastAPI, db_session: AsyncSession,
) -> None:
    transport = ASGITransport(app=api_application)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _dev_login(client, db_session)
        response = await client.get(
            "/api/v1/eval/pairwise/calibration/no-such/v9/latest",
            headers=bearer(token),
        )
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "EVAL_CALIBRATION_NOT_COMPUTED"


@pytest.mark.asyncio
async def test_calibration_history_returns_empty_list(
    api_application: FastAPI, db_session: AsyncSession,
) -> None:
    transport = ASGITransport(app=api_application)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _dev_login(client, db_session)
        response = await client.get(
            "/api/v1/eval/pairwise/calibration/no-such/v9/history",
            headers=bearer(token),
        )
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_annotation_submit_invalid_payload_returns_422(
    api_application: FastAPI, db_session: AsyncSession,
) -> None:
    transport = ASGITransport(app=api_application)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _dev_login(client, db_session)
        response = await client.post(
            "/api/v1/eval/runs/pairwise/annotations",
            headers=bearer(token),
            json={
                "pair_id": "00000000-0000-0000-0000-000000000001",
                "sweep_id": "00000000-0000-0000-0000-000000000002",
                "raw_winner": "INVALID",
                "raw_dimension_verdicts": {
                    "actionability": "a",
                    "alignment": "b",
                    "personalization": "tie",
                    "clarity": "a",
                    "consistency": "b",
                },
            },
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_calibration_report_requires_explicit_sweep_ids(
    api_application: FastAPI, db_session: AsyncSession,
) -> None:
    transport = ASGITransport(app=api_application)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _dev_login(client, db_session)
        response = await client.post(
            "/api/v1/eval/pairwise/calibration",
            headers=bearer(token),
            json={
                "dataset_id": "x",
                "dataset_version": "v1",
                "sweep_ids": [],
            },
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_pairwise_run_status_404_for_unknown_sweep(
    api_application: FastAPI, db_session: AsyncSession,
) -> None:
    transport = ASGITransport(app=api_application)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _dev_login(client, db_session)
        response = await client.get(
            "/api/v1/eval/runs/00000000-0000-0000-0000-000000000001"
            "/pairwise/run/00000000-0000-0000-0000-000000000002",
            headers=bearer(token),
        )
    assert response.status_code == 404
