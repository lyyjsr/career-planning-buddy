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


# ============================================================================
# Commit 3.1 — Review Surface endpoint + review_token tamper protection (#4)
# ============================================================================


@pytest.mark.asyncio
async def test_review_surface_404_when_pair_missing(
    api_application: FastAPI, db_session: AsyncSession,
) -> None:
    """GET /pairs/{pair_id}/review-surface returns 404 when no Pair row
    exists so the reviewer cannot probe arbitrary ids."""

    transport = ASGITransport(app=api_application)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _dev_login(client, db_session)
        response = await client.get(
            "/api/v1/eval/runs/pairwise/pairs/"
            "00000000-0000-0000-0000-0000000000aa/review-surface",
            params={
                "sweep_id": "00000000-0000-0000-0000-0000000000bb",
            },
            headers=bearer(token),
        )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "EVAL_PAIR_NOT_FOUND"


@pytest.mark.asyncio
async def test_review_surface_404_when_sweep_missing(
    api_application: FastAPI, db_session: AsyncSession,
) -> None:
    """If the pair exists but the queried sweep does not, return 404
    rather than leaking the pair's existence via a 200."""

    from tests.evals_v2.test_pairwise_calibration_repository import _seed_pair

    pair = await _seed_pair(db_session, 1)
    transport = ASGITransport(app=api_application)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _dev_login(client, db_session)
        response = await client.get(
            f"/api/v1/eval/runs/pairwise/pairs/{pair.id}/review-surface",
            params={
                "sweep_id": "00000000-0000-0000-0000-0000000000bb",
            },
            headers=bearer(token),
        )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "EVAL_SWEEP_NOT_FOUND"


@pytest.mark.asyncio
async def test_review_surface_endpoint_excludes_trial_ids_and_pair_hash(
    api_application: FastAPI, db_session: AsyncSession,
) -> None:
    """Happy-path response payload must NOT contain any baseline/candidate
    trial ids, the underlying pair_hash, or any model/score hints — issue #4
    blinding contract."""

    from app.core.database import session_transaction
    from app.repositories.evals import EvalRepository
    from tests.evals_v2.test_pairwise_calibration_repository import (
        _make_sweep,
        _seed_pair,
    )

    pair = await _seed_pair(db_session, 1)
    sweep_row = await _make_sweep(
        db_session,
        requested_pair_count=1,
    )
    async with session_transaction(db_session):
        await EvalRepository(db_session).create_sweep(sweep_row)

    transport = ASGITransport(app=api_application)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _dev_login(client, db_session)
        response = await client.get(
            f"/api/v1/eval/runs/pairwise/pairs/{pair.id}/review-surface",
            params={"sweep_id": str(sweep_row.id)},
            headers=bearer(token),
        )
    assert response.status_code == 200, response.text
    body = response.json()
    # Forbidden fields per the blinding contract.
    flat = str(body)
    assert "pair_hash" not in body
    assert "display_a_trial_id" not in body
    assert "display_b_trial_id" not in body
    assert "baseline_trial_id" not in body
    assert "candidate_trial_id" not in body
    assert "suggested_label" not in body
    # No literal trial UUID should appear anywhere in the payload.
    assert str(pair.baseline_trial_id) not in flat
    assert str(pair.candidate_trial_id) not in flat
    assert pair.pair_hash not in flat
    # Required surface fields ARE present.
    assert set(("display_a", "display_b", "position_variant", "review_token",
                "frozen_review_surface_sha256", "rubric", "case_id")).issubset(
        body.keys()
    )
    assert body["position_variant"] in ("baseline", "swapped")
    assert len(body["review_token"]) == 16


@pytest.mark.asyncio
async def test_annotation_submit_with_tampered_review_token_returns_422(
    api_application: FastAPI, db_session: AsyncSession,
) -> None:
    """If a caller POSTs a review_token that does not match the
    server-derived token for THIS (pair, reviewer, frozen surface), the
    server rejects with 422 EVAL_REVIEW_TOKEN_MISMATCH. This catches the
    case where a reviewer fetches surface A and submits against surface B,
    or attempts to forge a token."""

    from app.core.database import session_transaction
    from app.repositories.evals import EvalRepository
    from tests.evals_v2.test_pairwise_calibration_repository import (
        _make_sweep,
        _seed_pair,
    )

    pair = await _seed_pair(db_session, 1)
    sweep_row = await _make_sweep(
        db_session,
        requested_pair_count=1,
    )
    async with session_transaction(db_session):
        await EvalRepository(db_session).create_sweep(sweep_row)

    transport = ASGITransport(app=api_application)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _dev_login(client, db_session)
        response = await client.post(
            "/api/v1/eval/runs/pairwise/annotations",
            headers=bearer(token),
            json={
                "pair_id": str(pair.id),
                "sweep_id": str(sweep_row.id),
                "raw_winner": "a",
                "raw_dimension_verdicts": {
                    "actionability": "a",
                    "alignment": "b",
                    "personalization": "tie",
                    "clarity": "a",
                    "consistency": "b",
                },
                "review_token": "deadbeefdeadbeef",  # not a valid token
            },
        )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "EVAL_REVIEW_TOKEN_MISMATCH"

