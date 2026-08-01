"""Run rollback-only create-plan and review/replan real-Provider smoke checks."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings

if TYPE_CHECKING:
    from app.providers.llm import PlanningProvider


class SmokeRunError(RuntimeError):
    """Safe smoke failure carrying only a stable, non-sensitive error code."""

    def __init__(self, error_code: str, *, stage: str) -> None:
        super().__init__(error_code)
        self.error_code = error_code
        self.stage = stage


async def run_smoke(settings: Settings) -> dict[str, object]:
    from app.providers.llm import (
        OpenAICompatiblePlanningProvider,
        build_planning_provider,
    )

    provider = build_planning_provider(settings)
    if not isinstance(provider, OpenAICompatiblePlanningProvider):
        raise RuntimeError("real smoke requires LLM_PROVIDER=openai_compatible")

    engine = create_async_engine(settings.database_url)
    try:
        async with engine.connect() as connection:
            outer_transaction = await connection.begin()
            try:
                return await _run_in_transaction(connection, settings, provider)
            finally:
                await outer_transaction.rollback()
    finally:
        await engine.dispose()


async def _run_in_transaction(
    connection: AsyncConnection,
    settings: Settings,
    provider: PlanningProvider,
) -> dict[str, object]:
    from app.agent.executor import AgentRunExecutor
    from app.core.security import TokenService
    from app.models.plan import Plan
    from app.schemas.enums import CareerStage, GoalType, SkillLevel
    from app.schemas.profile import ProfilePutRequest
    from app.schemas.reviews import ReviewCreateRequest
    from app.services.agent_runs import AgentRunService
    from app.services.auth import AuthService
    from app.services.profiles import ProfileService
    from app.services.reviews import ReviewService

    class DeferredExecutor(AgentRunExecutor):
        """Record submissions for deterministic smoke execution."""

        def __init__(self) -> None:
            self.submitted: list[UUID] = []

        def submit(self, run_id: UUID) -> None:
            self.submitted.append(run_id)

        async def request_cancel(self, run_id: UUID) -> None:
            del run_id

    session_factory = async_sessionmaker(
        bind=connection,
        class_=AsyncSession,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    deferred = DeferredExecutor()
    runtime = AgentRunExecutor(session_factory, provider)
    async with session_factory() as session:
        user = (await AuthService(session, TokenService(settings)).login_guest(None)).user
        user_id = user.id
        await ProfileService(session).put(
            user_id=user_id,
            payload=ProfilePutRequest(
                goal_type=GoalType.AGENT_APP,
                stage=CareerStage.PREPARING,
                time_budget_minutes=60,
                skill_level=SkillLevel.INTERMEDIATE,
                skill_summary="FastAPI, PostgreSQL, and deterministic Agent Runtime",
            ),
            idempotency_key="real-provider-smoke-profile",
        )
        create_run = await AgentRunService(session, settings, deferred).create(
            user_id=user_id,
            message="为 AI Agent 应用求职方向生成未来四周规划和今天的可执行任务",
            hint_intent="create_plan",
            goal_type_override=None,
            source_plan_id=None,
            idempotency_key="real-provider-smoke-create",
        )
        create_run_id = create_run.id
        await runtime.execute(create_run_id)
        create_result = await _load_successful_run(
            session,
            create_run_id,
            stage="create_plan",
        )
        source_plan = await session.scalar(
            select(Plan).where(Plan.source_run_id == create_run_id)
        )
        if source_plan is None:
            raise SmokeRunError("SMOKE_PLAN_NOT_PERSISTED", stage="create_plan")

        review_service = ReviewService(session, settings, deferred)
        review = await review_service.create(
            user_id=user_id,
            payload=ReviewCreateRequest(
                plan_id=source_plan.id,
                review_date=source_plan.plan_date,
                mood=3,
                blockers="今天可用时间减少",
                adjustment_request="下一版任务控制在一小时内并拆得更小",
                free_text="保留当前 AI Agent 求职方向",
            ),
            idempotency_key="real-provider-smoke-review",
        )
        replan_created = await review_service.start_next_plan(
            review_id=review.review_id,
            user_id=user_id,
            idempotency_key="real-provider-smoke-replan",
        )
        await runtime.execute(replan_created.run_id)
        replan_result = await _load_successful_run(
            session,
            replan_created.run_id,
            stage="review_replan",
        )

        return {
            "provider": "openai_compatible",
            "transaction": "rolled_back",
            "create_plan": create_result,
            "review_replan": {
                **replan_result,
                "mode": replan_created.replan_mode.value,
                "suggested_replan": review.suggested_replan,
            },
        }


async def _load_successful_run(
    session: AsyncSession,
    run_id: UUID,
    *,
    stage: str,
) -> dict[str, object]:
    from app.models.agent_run import AgentEvent, AgentRun, AgentStep

    session.expire_all()
    run = await session.get(AgentRun, run_id)
    if run is None:
        raise SmokeRunError("SMOKE_RUN_NOT_FOUND", stage=stage)
    terminal_count = await session.scalar(
        select(func.count())
        .select_from(AgentEvent)
        .where(
            AgentEvent.run_id == run_id,
            AgentEvent.event_type.in_(
                ("run.completed", "run.degraded", "run.failed", "run.cancelled")
            ),
        )
    )
    provider_calls = await session.scalar(
        select(func.count())
        .select_from(AgentStep)
        .where(AgentStep.run_id == run_id, AgentStep.model_id.is_not(None))
    )
    if run.status not in {"completed", "degraded"} or run.final_plan_id is None:
        raise SmokeRunError(run.error_code or "SMOKE_RUN_FAILED", stage=stage)
    if terminal_count != 1 or not provider_calls:
        raise SmokeRunError("SMOKE_TRACE_INVARIANT_FAILED", stage=stage)
    return {
        "status": run.status,
        "model_id": run.model_id,
        "provider_calls": provider_calls,
        "tokens_in": run.total_tokens_in,
        "tokens_out": run.total_tokens_out,
        "latency_ms": run.total_latency_ms,
        "fallback_reason": run.fallback_reason,
        "terminal_events": terminal_count,
        "schema_validated": True,
    }


def main() -> int:
    try:
        settings = Settings()
    except ValidationError:
        print(
            json.dumps(
                {
                    "status": "configuration_error",
                    "required": [
                        "LLM_PROVIDER=openai_compatible",
                        "LLM_API_KEY",
                        "LLM_BASE_URL",
                        "LLM_MODEL",
                    ],
                }
            )
        )
        return 2
    if settings.llm_provider != "openai_compatible":
        print(
            json.dumps(
                {
                    "status": "configuration_error",
                    "required": ["LLM_PROVIDER=openai_compatible"],
                }
            )
        )
        return 2
    try:
        result = asyncio.run(run_smoke(settings))
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error_code": getattr(exc, "error_code", "SMOKE_EXECUTION_FAILED"),
                    "stage": getattr(exc, "stage", "smoke_setup"),
                    "error_type": type(exc).__name__,
                }
            )
        )
        return 1
    result["checked_at"] = datetime.now(UTC).isoformat()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
