"""Single-worker in-process Agent Run scheduling and execution."""

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agent.errors import AgentDeadlineExceededError, AgentError
from app.agent.finalizer import AgentRunFinalizer
from app.agent.graph import GraphFactory, load_profile
from app.agent.node_runner import NodeRunner
from app.core.database import AsyncSessionFactory, session_transaction
from app.harness.budget import BudgetGuard, CancellationToken
from app.models.agent_run import AgentRun
from app.providers.embedding import EmbeddingProvider, MockEmbeddingProvider
from app.providers.evidence_distillation import (
    EvidenceDistillationProvider,
    MockEvidenceDistillationProvider,
)
from app.providers.llm import MockPlanningProvider, PlanningProvider
from app.schemas.agent_runs import (
    PlanningState,
    RunRequestSnapshot,
    RuntimeConfigSnapshot,
)
from app.schemas.enums import GoalType, ReplanMode
from app.services.experience_atoms import ExperienceAtomService
from app.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class AgentRunExecutor:
    """Executes one Run per asyncio Task; no multi-worker reliability is claimed."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] = AsyncSessionFactory,
        provider: PlanningProvider | None = None,
        tool_registry: ToolRegistry | None = None,
        embedding_provider: EmbeddingProvider | None = None,
        evidence_distillation_provider: EvidenceDistillationProvider | None = None,
        managed_resources: list[object] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._provider = provider or MockPlanningProvider()
        self._tool_registry = tool_registry or ToolRegistry()
        self._embedding_provider = embedding_provider or MockEmbeddingProvider()
        self._evidence_distillation_provider = (
            evidence_distillation_provider or MockEvidenceDistillationProvider()
        )
        self._tasks: dict[UUID, asyncio.Task[None]] = {}
        self._shutdown_run_ids: set[UUID] = set()
        self._managed_resources = list(managed_resources or [])

    def submit(self, run_id: UUID) -> None:
        current = self._tasks.get(run_id)
        if current is not None and not current.done():
            return
        task = asyncio.create_task(self.execute(run_id), name=f"agent-run-{run_id}")
        self._tasks[run_id] = task
        task.add_done_callback(self._done_callback(run_id))

    def set_provider(self, provider: PlanningProvider) -> None:
        """Configure the process-wide Provider before accepting new Runs."""
        if any(not task.done() for task in self._tasks.values()):
            raise RuntimeError("cannot replace Provider while Agent Runs are active")
        self._provider = provider

    def set_tool_registry(self, registry: ToolRegistry) -> None:
        if any(not task.done() for task in self._tasks.values()):
            raise RuntimeError("cannot replace Tool registry while Agent Runs are active")
        self._tool_registry = registry

    def set_embedding_provider(self, provider: EmbeddingProvider) -> None:
        if any(not task.done() for task in self._tasks.values()):
            raise RuntimeError("cannot replace Embedding Provider while Agent Runs are active")
        self._embedding_provider = provider

    def set_evidence_distillation_provider(self, provider: EvidenceDistillationProvider) -> None:
        if any(not task.done() for task in self._tasks.values()):
            raise RuntimeError("cannot replace Evidence Provider while Agent Runs are active")
        self._evidence_distillation_provider = provider

    async def execute(self, run_id: UUID) -> None:
        loaded = await self._start_and_load(run_id)
        if loaded is None:
            return
        run, config = loaded
        if config is None:
            await AgentRunFinalizer(self._session_factory, None).finalize_failed(
                run_id, error_code="CONFIG_SNAPSHOT_INVALID"
            )
            return
        cancellation = CancellationToken()
        budget = BudgetGuard(config, run.deadline_at, cancellation)
        finalizer = AgentRunFinalizer(self._session_factory, budget)
        if run.cancel_requested_at is not None:
            await finalizer.finalize_cancelled(run_id)
            return
        runner = NodeRunner(
            self._session_factory,
            budget,
            config.node_timeouts_seconds,
        )
        graph = GraphFactory(
            self._session_factory,
            self._provider,
            self._tool_registry,
            self._embedding_provider,
        ).build(
            node_runner=runner,
            finalizer=finalizer,
            budget=budget,
        )
        try:
            profile = await load_profile(self._session_factory, run.user_id)
            state: PlanningState = {
                "run_id": run.id,
                "user_id": run.user_id,
                "request": RunRequestSnapshot(
                    message=run.request_text,
                    hint_intent=(
                        "replan"
                        if run.hint_intent == "replan"
                        else "create_plan"
                        if run.hint_intent == "create_plan"
                        else None
                    ),
                    goal_type_override=(
                        GoalType(run.goal_type_override)
                        if run.goal_type_override is not None
                        else None
                    ),
                    source_plan_id=run.source_plan_id,
                    source_review_id=run.source_review_id,
                ),
                "runtime_config": config,
                "profile": profile,
                "server_replan_mode": (
                    ReplanMode(run.replan_mode)
                    if run.source_review_id is not None and run.replan_mode is not None
                    else None
                ),
                "repair_count": 0,
                "fallback_reason": None,
            }
            await graph.execute(state)
            if profile is not None:
                await self._distill_evidence_best_effort(run_id, profile.goal_type.value)
        except asyncio.CancelledError:
            cancellation.cancel()
            if run_id in self._shutdown_run_ids:
                await finalizer.finalize_failed(
                    run_id, error_code="PROCESS_INTERRUPTED"
                )
            else:
                await finalizer.finalize_cancelled(run_id)
        except AgentDeadlineExceededError:
            await finalizer.finalize_failed(run_id, error_code="AGENT_DEADLINE_EXCEEDED")
        except AgentError as exc:
            await finalizer.finalize_failed(run_id, error_code=exc.code)
        except Exception:
            logger.exception("agent run %s failed unexpectedly", run_id)
            await finalizer.finalize_failed(run_id, error_code="AGENT_EXECUTION_FAILED")
        finally:
            await self._ensure_terminal(run_id, finalizer)

    async def request_cancel(self, run_id: UUID) -> None:
        task = self._tasks.get(run_id)
        if task is not None and not task.done():
            task.cancel()

    async def recover_interrupted(self) -> int:
        now = datetime.now(UTC)
        async with self._session_factory() as session:
            async with session_transaction(session):
                run_ids = list(
                    await session.scalars(
                        select(AgentRun.id).where(
                            AgentRun.status.in_(("pending", "running")),
                        )
                    )
                )
        for run_id in run_ids:
            loaded = await self._load(run_id)
            if loaded is None:
                continue
            run, config = loaded
            guard = (
                BudgetGuard(config, now, CancellationToken())
                if config is not None
                else None
            )
            error_code = (
                "PROCESS_INTERRUPTED" if config is not None else "CONFIG_SNAPSHOT_INVALID"
            )
            await AgentRunFinalizer(self._session_factory, guard).finalize_failed(
                run.id, error_code=error_code
            )
        return len(run_ids)

    async def shutdown(self) -> None:
        active = [
            (run_id, task)
            for run_id, task in self._tasks.items()
            if not task.done()
        ]
        self._shutdown_run_ids.update(run_id for run_id, _ in active)
        tasks = [task for _, task in active]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._shutdown_run_ids.difference_update(run_id for run_id, _ in active)
        await self.close_resources()

    async def close_resources(self) -> None:
        resources = [
            self._provider,
            self._tool_registry,
            self._embedding_provider,
            self._evidence_distillation_provider,
            *self._managed_resources,
        ]
        closed: set[int] = set()
        for resource in resources:
            if id(resource) in closed:
                continue
            closed.add(id(resource))
            close = getattr(resource, "aclose", None)
            if callable(close):
                await close()
        self._managed_resources.clear()

    async def _start_and_load(
        self, run_id: UUID
    ) -> tuple[AgentRun, RuntimeConfigSnapshot | None] | None:
        async with self._session_factory() as session:
            async with session_transaction(session):
                run = await session.scalar(
                    select(AgentRun).where(AgentRun.id == run_id).with_for_update()
                )
                if run is None or run.status != "pending":
                    return None
                try:
                    config = RuntimeConfigSnapshot.model_validate(run.config_snapshot_json)
                except ValidationError:
                    return run, None
                run.status = "running"
                run.started_at = datetime.now(UTC)
                await session.flush()
                return run, config

    async def _load(
        self, run_id: UUID
    ) -> tuple[AgentRun, RuntimeConfigSnapshot | None] | None:
        async with self._session_factory() as session:
            async with session_transaction(session):
                run = await session.get(AgentRun, run_id)
                if run is None:
                    return None
                try:
                    config = RuntimeConfigSnapshot.model_validate(run.config_snapshot_json)
                except ValidationError:
                    config = None
                return run, config

    async def _ensure_terminal(self, run_id: UUID, finalizer: AgentRunFinalizer) -> None:
        async with self._session_factory() as session:
            async with session_transaction(session):
                status = await session.scalar(select(AgentRun.status).where(AgentRun.id == run_id))
        if status in {"pending", "running"}:
            await finalizer.finalize_failed(run_id, error_code="AGENT_TERMINAL_MISSING")

    async def _distill_evidence_best_effort(self, run_id: UUID, goal_type: str) -> None:
        try:
            async with self._session_factory() as session:
                await ExperienceAtomService(
                    session,
                    self._embedding_provider,
                    self._evidence_distillation_provider,
                ).distill_run(run_id=run_id, goal_type=goal_type)
        except Exception:
            logger.exception("evidence distillation failed for run %s", run_id)
            # Post-success enrichment must never alter the Run's terminal contract.
            return

    def _discard(self, run_id: UUID, task: asyncio.Task[None]) -> None:
        if self._tasks.get(run_id) is task:
            self._tasks.pop(run_id, None)

    def _done_callback(self, run_id: UUID) -> Callable[[asyncio.Task[None]], None]:
        def discard(task: asyncio.Task[None]) -> None:
            self._discard(run_id, task)

        return discard


agent_run_executor = AgentRunExecutor()
