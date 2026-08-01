"""FastAPI application and health-check tests."""

from http import HTTPStatus

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.main import app, create_app
from app.schemas.health import HealthResponse


@pytest.mark.asyncio
async def test_health_returns_ok() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"status": "ok", "service": "Career Planning Buddy"}


@pytest.mark.asyncio
async def test_health_response_matches_schema() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    parsed = HealthResponse.model_validate(response.json())
    assert parsed.status == "ok"


@pytest.mark.asyncio
async def test_health_allows_configured_local_frontend_origin() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.options(
            "/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == HTTPStatus.OK
    assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"


@pytest.mark.asyncio
async def test_profile_cors_preflight_allows_stage_one_headers() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.options(
            "/api/v1/profile",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "PUT",
                "Access-Control-Request-Headers": ("authorization,content-type,idempotency-key"),
            },
        )

    assert response.status_code == HTTPStatus.OK
    assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"
    assert "PUT" in response.headers["Access-Control-Allow-Methods"]
    allowed_headers = response.headers["Access-Control-Allow-Headers"].lower()
    assert "authorization" in allowed_headers
    assert "idempotency-key" in allowed_headers


def test_health_response_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        HealthResponse.model_validate(
            {
                "status": "ok",
                "service": "Career Planning Buddy",
                "unexpected": True,
            }
        )


def test_application_initializes() -> None:
    application = create_app()

    assert application.title == "Career Planning Buddy"
    assert str(application.url_path_for("health_check")) == "/health"
