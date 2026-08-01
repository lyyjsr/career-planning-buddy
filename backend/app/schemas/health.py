"""Health-check response contract."""

from typing import Literal

from app.schemas.base import StrictModel


class HealthResponse(StrictModel):
    """Stable response returned by the infrastructure health probe."""

    status: Literal["ok"]
    service: str
