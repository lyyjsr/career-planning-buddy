"""Single authority for Run terminal state and terminal event convergence."""

from datetime import UTC, datetime
from time import monotonic
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agent.errors import PersistTransactionError
from app.core.database import session_transaction
from app.harness.budget import BudgetGuard
from app.harness.events import EventRecorder
from app.harness.trace import TraceRecorder
from app.models.agent_run import AgentRun, AgentStep
from app.repositories.plans import PlanRepository
from app.schemas.agent_runs import (
    ClarificationRequest,
    CompanionMessageCandidate,
    PlanCandidate,
    PlanResultSummary,
    SafeResponse,
)

TERMINAL_STATUSES = {"completed", "degraded", "failed", "cancelled"}


class AgentRunFinalizer:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        budget: BudgetGuard,
    ) -> None:
        self._session_factory = session_factory
        self._budget = budget

    async def finalize_plan(
        self,
        *,
        run_id: UUID,
        user_id: UUID,
        candidate: PlanCandidate,
        companion: CompanionMessageCandidate,
        persist_step_id: UUID,
        fallback_reason: str | None,
        simulate_failure: bool = False,
    ) -> None:
        started = monotonic()
        try:
            async with self._session_factory() as session:
                async with session_transaction(session):
                    run = await self._lock_active_run(session, run_id)
                    self._ensure_can_persist(run)
                    plans = PlanRepository(session)
                    source_plan = None
                    if run.source_plan_id is not None:
                        source_plan = await plans.get_for_user(
                            run.source_plan_id, user_id, for_update=True
                        )
                    active_plan = await plans.get_active_for_user(user_id, for_update=True)
                    if source_plan is not None:
                        await plans.archive(source_plan)
                    if active_plan is not None and (
                        source_plan is None or active_plan.id != source_plan.id
                    ):
                        await plans.archive(active_plan)
                    if simulate_failure:
                        raise PersistTransactionError
                    provider = run.config_snapshot_json.get("provider")
                    provider_name = provider if isinstance(provider, str) else "unknown"
                    model_id = await session.scalar(
                        select(AgentStep.model_id)
                        .where(
                            AgentStep.run_id == run_id,
                            AgentStep.model_id.is_not(None),
                        )
                        .order_by(AgentStep.sequence.desc())
                        .limit(1)
                    )
                    plan = await plans.create_plan(
                        {
                            "user_id": user_id,
                            "source_run_id": run_id,
                            "parent_plan_id": source_plan.id if source_plan else None,
                            "status": "generated",
                            "plan_date": candidate.plan_date,
                            "horizon_start": candidate.horizon_start,
                            "horizon_end": candidate.horizon_end,
                            "overall_direction": candidate.overall_direction,
                            "weekly_focus_json": [
                                item.model_dump(mode="json") for item in candidate.weekly_focus
                            ],
                            "summary": candidate.summary,
                            "rationale": candidate.rationale,
                            "adjustment_reason": candidate.adjustment_reason,
                            "assumptions_json": candidate.assumptions,
                            "evidence_refs_json": [
                                item.model_dump(mode="json") for item in candidate.evidence_refs
                            ],
                            "metadata_json": {
                                "graph_version": run.graph_version,
                                "replan_mode": run.replan_mode,
                                "provider": provider_name,
                                "model_id": model_id,
                            },
                        }
                    )
                    tasks = await plans.create_tasks(
                        plan_id=plan.id,
                        user_id=user_id,
                        candidates=[
                            {
                                **task.model_dump(mode="python"),
                                "task_type": task.task_type.value,
                                "state": "pending",
                            }
                            for task in candidate.tasks
                        ],
                    )
                    await plans.create_companion(
                        user_id=user_id,
                        run_id=run_id,
                        plan_id=plan.id,
                        trigger_tag=companion.trigger_tag,
                        message=companion.message,
                        template_version=companion.template_version,
                    )
                    persist_step = await session.get(AgentStep, persist_step_id)
                    if persist_step is None:
                        raise PersistTransactionError("persist step is missing")
                    latency_ms = int((monotonic() - started) * 1000)
                    await TraceRecorder(session).complete_step(
                        persist_step,
                        status="completed",
                        latency_ms=latency_ms,
                        trace_data={"plan_id": str(plan.id), "task_count": len(tasks)},
                    )
                    recorder = EventRecorder(session)
                    await recorder.record(
                        run_id,
                        "node.completed",
                        {
                            "node_name": "persist",
                            "step_sequence": persist_step.sequence,
                            "status": "completed",
                            "latency_ms": latency_ms,
                        },
                    )
                    await recorder.record(
                        run_id,
                        "companion.message",
                        {
                            "trigger_tag": companion.trigger_tag,
                            "message": companion.message,
                        },
                    )
                    degraded = fallback_reason is not None
                    await recorder.record(
                        run_id,
                        "plan.ready",
                        {
                            "plan_id": str(plan.id),
                            "task_count": len(tasks),
                            "degraded": degraded,
                        },
                    )
                    result = PlanResultSummary(
                        plan_id=plan.id,
                        status="generated",
                        plan_date=plan.plan_date,
                        horizon_end=plan.horizon_end,
                        summary=plan.summary,
                        task_count=len(tasks),
                    )
                    status = "degraded" if degraded else "completed"
                    run.status = status
                    run.result_kind = "plan"
                    run.result_payload_json = result.model_dump(mode="json")
                    run.final_plan_id = plan.id
                    run.fallback_reason = fallback_reason
                    run.error_code = None
                    run.error_message = None
                    run.total_tokens_in = self._budget.tokens_in
                    run.total_tokens_out = self._budget.tokens_out
                    run.model_id = model_id
                    run.total_latency_ms = max(
                        0,
                        int((datetime.now(UTC) - run.created_at).total_seconds() * 1000),
                    )
                    run.finished_at = datetime.now(UTC)
                    event_type = "run.degraded" if degraded else "run.completed"
                    terminal_payload: dict[str, object] = {
                        "status": status,
                        "result_kind": "plan",
                        "final_plan_id": str(plan.id),
                    }
                    if fallback_reason is not None:
                        terminal_payload["fallback_reason"] = fallback_reason
                    await recorder.record(
                        run_id,
                        event_type,
                        terminal_payload,
                        allow_terminal_run=True,
                    )
        except Exception:
            await self.finalize_failed(
                run_id,
                error_code="PERSIST_TRANSACTION_FAILED",
                persist_step_id=persist_step_id,
            )
            raise

    async def finalize_degraded(
        self,
        *,
        run_id: UUID,
        result_kind: str,
        result: ClarificationRequest | SafeResponse,
        fallback_reason: str,
    ) -> None:
        async with self._session_factory() as session:
            async with session_transaction(session):
                run = await self._lock_active_run(session, run_id)
                recorder = EventRecorder(session)
                if isinstance(result, ClarificationRequest):
                    await recorder.record(
                        run_id,
                        "clarification.requested",
                        result.model_dump(mode="json"),
                    )
                run.status = "degraded"
                run.result_kind = result_kind
                run.result_payload_json = result.model_dump(mode="json")
                run.final_plan_id = None
                run.fallback_reason = fallback_reason
                run.error_code = None
                run.finished_at = datetime.now(UTC)
                run.total_latency_ms = max(
                    0,
                    int((run.finished_at - run.created_at).total_seconds() * 1000),
                )
                await recorder.record(
                    run_id,
                    "run.degraded",
                    {
                        "status": "degraded",
                        "result_kind": result_kind,
                        "fallback_reason": fallback_reason,
                        "final_plan_id": None,
                    },
                    allow_terminal_run=True,
                )

    async def finalize_failed(
        self,
        run_id: UUID,
        *,
        error_code: str,
        persist_step_id: UUID | None = None,
    ) -> bool:
        return await self._finalize_without_result(
            run_id,
            status="failed",
            event_type="run.failed",
            error_code=error_code,
            persist_step_id=persist_step_id,
        )

    async def finalize_cancelled(self, run_id: UUID) -> bool:
        return await self._finalize_without_result(
            run_id,
            status="cancelled",
            event_type="run.cancelled",
            error_code="RUN_CANCELLED",
        )

    async def _finalize_without_result(
        self,
        run_id: UUID,
        *,
        status: str,
        event_type: str,
        error_code: str,
        persist_step_id: UUID | None = None,
    ) -> bool:
        async with self._session_factory() as session:
            async with session_transaction(session):
                run = await session.scalar(
                    select(AgentRun).where(AgentRun.id == run_id).with_for_update()
                )
                if run is None or run.status in TERMINAL_STATUSES:
                    return False
                recorder = EventRecorder(session)
                if persist_step_id is not None:
                    step = await session.get(AgentStep, persist_step_id)
                    if step is not None and step.status == "running":
                        await TraceRecorder(session).complete_step(
                            step,
                            status="failed",
                            latency_ms=0,
                            trace_data={},
                            error_code=error_code,
                            error_message=error_code,
                        )
                        await recorder.record(
                            run_id,
                            "node.completed",
                            {
                                "node_name": step.node_name,
                                "step_sequence": step.sequence,
                                "status": "failed",
                                "latency_ms": 0,
                            },
                        )
                run.status = status
                run.result_kind = None
                run.result_payload_json = None
                run.final_plan_id = None
                run.fallback_reason = None
                run.error_code = error_code
                run.error_message = error_code
                run.finished_at = datetime.now(UTC)
                run.total_latency_ms = max(
                    0,
                    int((run.finished_at - run.created_at).total_seconds() * 1000),
                )
                await recorder.record(
                    run_id,
                    event_type,
                    {"status": status, "error_code": error_code},
                    allow_terminal_run=True,
                )
                return True

    @staticmethod
    async def _lock_active_run(session: AsyncSession, run_id: UUID) -> AgentRun:
        run = await session.scalar(select(AgentRun).where(AgentRun.id == run_id).with_for_update())
        if run is None or run.status in TERMINAL_STATUSES:
            raise RuntimeError("Run is already terminal")
        return run

    @staticmethod
    def _ensure_can_persist(run: AgentRun) -> None:
        if run.status != "running":
            raise PersistTransactionError("Run must be running")
        if run.cancel_requested_at is not None:
            raise PersistTransactionError("Run cancellation was requested")
        if datetime.now(UTC) >= run.deadline_at:
            raise PersistTransactionError("Run deadline was exceeded")
