"""Application-scoped construction of runtime Provider dependencies."""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.providers.embedding import EmbeddingProvider, build_embedding_provider
from app.providers.evidence_distillation import (
    EvidenceDistillationProvider,
    build_evidence_distillation_provider,
)
from app.providers.goal_understanding import (
    GoalUnderstandingProvider,
    build_goal_understanding_provider,
)
from app.providers.llm import PlanningProvider, build_planning_provider
from app.providers.search import SearchProvider, build_search_provider
from app.tools.registry import ToolRegistry, build_tool_registry


@dataclass(frozen=True, slots=True)
class RuntimeProviderRegistry:
    """One coherent Provider graph shared by HTTP services and the Agent executor."""

    planning: PlanningProvider
    goal_understanding: GoalUnderstandingProvider
    embedding: EmbeddingProvider
    search: SearchProvider
    evidence_distillation: EvidenceDistillationProvider
    tools: ToolRegistry


def build_runtime_provider_registry(
    *,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> RuntimeProviderRegistry:
    """Build each runtime Provider exactly once for one application instance."""
    embedding = build_embedding_provider(settings)
    search = build_search_provider(settings)
    return RuntimeProviderRegistry(
        planning=build_planning_provider(settings),
        goal_understanding=build_goal_understanding_provider(settings),
        embedding=embedding,
        search=search,
        evidence_distillation=build_evidence_distillation_provider(settings),
        tools=build_tool_registry(
            settings=settings,
            session_factory=session_factory,
            embedding_provider=embedding,
            search_provider=search,
        ),
    )
