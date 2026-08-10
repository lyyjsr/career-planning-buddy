"""Immutable config and input snapshot helpers."""

from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.agent_run import AgentRun
from app.runtime.versioning import build_runtime_identity
from app.schemas.agent_runs import RunInputSnapshot, RuntimeConfigSnapshot

NODE_TIMEOUTS: dict[str, float] = {
    "risk_gate": 6,
    "intent_router": 6,
    "navigation": 2,
    "clarification": 2,
    "safe_response": 2,
    "context_builder": 5,
    "career_planning_agent": 30,
    "rule_validator": 2,
    "revise_or_fallback": 12,
    "companion_response": 2,
    "persist": 8,
}


class SnapshotService:
    @staticmethod
    def build_config(settings: Settings) -> RuntimeConfigSnapshot:
        is_real = settings.llm_provider == "openai_compatible"
        identity = build_runtime_identity(settings)
        node_timeouts = dict(NODE_TIMEOUTS)
        if is_real:
            # LLM nodes may legitimately perform an initial generation plus
            # bounded format/business repair calls. Let the frozen Run budget
            # be the node ceiling; each physical provider call still has its
            # own HTTP timeout and BudgetGuard enforces the remaining total.
            llm_node_timeout = float(settings.agent_deadline_seconds)
            node_timeouts["career_planning_agent"] = llm_node_timeout
            node_timeouts["revise_or_fallback"] = llm_node_timeout
        return RuntimeConfigSnapshot(
            graph_version=identity.graph_version,
            feature_stage=identity.feature_stage,
            available_tools=["memory_lookup", "rag_retrieve", "web_search"],
            provider=settings.llm_provider,
            model_alias=(
                settings.llm_model
                if is_real and settings.llm_model is not None
                else "mock-career-planner-v1"
            ),
            prompt_versions=identity.prompt_versions,
            max_llm_calls=settings.agent_max_llm_calls,
            max_tool_rounds=settings.agent_max_tool_rounds,
            max_tool_calls=settings.agent_max_tool_calls,
            max_total_tokens=settings.agent_max_total_tokens,
            max_input_tokens_per_call=settings.agent_max_input_tokens_per_call,
            max_output_tokens_per_call=settings.agent_max_output_tokens_per_call,
            deadline_seconds=settings.agent_deadline_seconds,
            node_timeouts_seconds=node_timeouts,
            memory_semantic_retrieval_enabled=(settings.memory_semantic_retrieval_enabled),
            memory_retrieval_limit=settings.memory_retrieval_limit,
            memory_context_max_items=settings.memory_context_max_items,
            memory_context_max_chars=settings.memory_context_max_chars,
            memory_min_similarity=settings.memory_min_similarity,
            memory_recency_half_life_days=(settings.memory_recency_half_life_days),
        )

    @staticmethod
    async def write_input_once(
        session: AsyncSession, run_id: UUID, snapshot: RunInputSnapshot
    ) -> bool:
        result = await session.execute(
            update(AgentRun)
            .where(AgentRun.id == run_id, AgentRun.input_snapshot_json.is_(None))
            .values(input_snapshot_json=snapshot.model_dump(mode="json"))
            .returning(AgentRun.id)
        )
        return result.scalar_one_or_none() is not None
