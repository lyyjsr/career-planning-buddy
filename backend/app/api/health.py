"""Infrastructure health-check endpoint."""

from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Report that the HTTP application is available."""
    return HealthResponse(status="ok", service=get_settings().app_name)
