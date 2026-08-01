"""Search Provider protocol and deterministic Stage 4 Mock implementation."""

import asyncio
from datetime import UTC, datetime
from typing import Literal, Protocol

from pydantic import Field

from app.agent.errors import ProviderUnavailableError
from app.schemas.base import StrictModel


class SearchResultItem(StrictModel):
    url: str
    title: str | None
    snippet: str
    source_type: Literal["official", "job_board", "blog", "community", "other"]
    reliability: float = Field(ge=0, le=1)
    retrieved_at: datetime


class SearchProvider(Protocol):
    provider_name: str

    async def search(
        self,
        *,
        query: str,
        limit: int,
        freshness_days: int | None,
    ) -> list[SearchResultItem]: ...


class MockSearchProvider:
    """Offline fixture Provider; results are explicit test data, never live search."""

    provider_name = "mock"

    async def search(
        self,
        *,
        query: str,
        limit: int,
        freshness_days: int | None,
    ) -> list[SearchResultItem]:
        del freshness_days
        if "[mock:search-timeout]" in query:
            await asyncio.sleep(60)
        if "[mock:search-error]" in query:
            raise ProviderUnavailableError("Mock Search Provider unavailable")
        now = datetime.now(UTC)
        fixtures = [
            SearchResultItem(
                url="https://example.test/career/agent-engineer",
                title="Agent Engineer Role Guide (Mock Fixture)",
                snippet="固定测试数据：岗位通常要求 Python、评测、可观测性与可靠性工程能力。",
                source_type="official",
                reliability=0.9,
                retrieved_at=now,
            ),
            SearchResultItem(
                url="https://example.test/jobs/agent-engineer?utm_source=fixture",
                title="Agent Engineer Job Signals (Mock Fixture)",
                snippet="固定测试数据：可展示项目、测试证据和系统设计说明有助于验证能力。",
                source_type="job_board",
                reliability=0.75,
                retrieved_at=now,
            ),
            SearchResultItem(
                url="https://example.test/career/agent-engineer#duplicate",
                title="Duplicate URL Fixture",
                snippet="该条用于验证 URL 规范化去重。",
                source_type="other",
                reliability=0.5,
                retrieved_at=now,
            ),
        ]
        return fixtures[:limit]


def build_search_provider() -> SearchProvider:
    return MockSearchProvider()
