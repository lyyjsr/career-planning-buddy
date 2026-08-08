"""Uniform persisted execution wrapper for every controlled graph node."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from decimal import Decimal
from time import monotonic
from typing import TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agent.errors import AgentDeadlineExceededError, AgentError
from app.core.database import session_transaction
from app.harness.budget import BudgetGuard
from app.harness.events import EventRecorder
from app.harness.trace import TraceRecorder
from app.models.agent_run import AgentRun, AgentStep

T = TypeVar("T")


@dataclass(slots=True)
class NodeTelemetry:
    trace_data: dict[str, object] = field(default_factory=dict)
    tokens_in: int = 0
    tokens_out: int = 0
    cost_cny: Decimal = Decimal("0")
    model_id: str | None = None
    prompt_version: str | None = None


@dataclass(slots=True)
class NodeOutput[T]:
    value: T
    telemetry: NodeTelemetry = field(default_factory=NodeTelemetry)


class NodeRunner:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        budget: BudgetGuard,
        node_timeouts: dict[str, float],
    ) -> None:
        self._session_factory = session_factory
        self._budget = budget
        self._node_timeouts = node_timeouts

    async def run(
        self,
        run_id: UUID,
        node_name: str,
        operation: Callable[[], Awaitable[NodeOutput[T]]],
        *,
        attempt: int = 1,
    ) -> T:
        self._budget.check()
        step = await self.start_step(run_id, node_name, attempt)
        started = monotonic()
        try:
            timeout = min(
                self._node_timeouts[node_name],
                self._budget.remaining_seconds(),
            )
            output = await asyncio.wait_for(operation(), timeout=timeout)
            self._budget.check()
        except TimeoutError as exc:
            await self.fail_step(
                run_id,
                step.id,
                latency_ms=int((monotonic() - started) * 1000),
                error_code="NODE_TIMEOUT",
                error_message=f"{node_name} exceeded its timeout",
            )
            raise AgentDeadlineExceededError from exc
        except BaseException as exc:
            code = exc.code if isinstance(exc, AgentError) else "NODE_EXECUTION_FAILED"
            error_message = str(exc) if isinstance(exc, AgentError) else type(exc).__name__
            await self.fail_step(
                run_id,
                step.id,
                latency_ms=int((monotonic() - started) * 1000),
                error_code=code,
                error_message=error_message,
            )
            raise
        traced_latency = output.telemetry.trace_data.get("latency_ms")
        latency_ms = max(
            int((monotonic() - started) * 1000),
            traced_latency if isinstance(traced_latency, int) else 0,
        )
        await self._complete_step(
            run_id,
            step.id,
            latency_ms=latency_ms,
            telemetry=output.telemetry,
        )
        return output.value

    async def run_with_step(
        self,
        run_id: UUID,
        node_name: str,
        operation: Callable[[UUID], Awaitable[NodeOutput[T]]],
        *,
        attempt: int = 1,
    ) -> T:
        """Run a node whose bounded operation needs its persisted step id for Tool traces."""
        self._budget.check()
        step = await self.start_step(run_id, node_name, attempt)
        started = monotonic()
        try:
            timeout = min(self._node_timeouts[node_name], self._budget.remaining_seconds())
            output = await asyncio.wait_for(operation(step.id), timeout=timeout)
            self._budget.check()
        except TimeoutError as exc:
            await self.fail_step(
                run_id,
                step.id,
                latency_ms=int((monotonic() - started) * 1000),
                error_code="NODE_TIMEOUT",
                error_message=f"{node_name} exceeded its timeout",
            )
            raise AgentDeadlineExceededError from exc
        except BaseException as exc:
            code = exc.code if isinstance(exc, AgentError) else "NODE_EXECUTION_FAILED"
            error_message = str(exc) if isinstance(exc, AgentError) else type(exc).__name__
            await self.fail_step(
                run_id,
                step.id,
                latency_ms=int((monotonic() - started) * 1000),
                error_code=code,
                error_message=error_message,
            )
            raise
        traced_latency = output.telemetry.trace_data.get("latency_ms")
        latency_ms = max(
            int((monotonic() - started) * 1000),
            traced_latency if isinstance(traced_latency, int) else 0,
        )
        await self._complete_step(
            run_id,
            step.id,
            latency_ms=latency_ms,
            telemetry=output.telemetry,
        )
        return output.value

    async def start_step(self, run_id: UUID, node_name: str, attempt: int = 1) -> AgentStep:
        async with self._session_factory() as session:
            async with session_transaction(session):
                run = await session.scalar(
                    select(AgentRun).where(AgentRun.id == run_id).with_for_update()
                )
                if run is None or run.status not in {"pending", "running"}:
                    raise RuntimeError("Run is not active")
                step = await TraceRecorder(session).start_step(run_id, node_name, attempt)
                await EventRecorder(session).record(
                    run_id,
                    "node.started",
                    {
                        "node_name": node_name,
                        "step_sequence": step.sequence,
                        "attempt": attempt,
                    },
                )
                return step

    async def _complete_step(
        self,
        run_id: UUID,
        step_id: UUID,
        *,
        latency_ms: int,
        telemetry: NodeTelemetry,
    ) -> None:
        async with self._session_factory() as session:
            async with session_transaction(session):
                step = await session.get(AgentStep, step_id)
                if step is None:
                    raise RuntimeError("step disappeared")
                await TraceRecorder(session).complete_step(
                    step,
                    status="completed",
                    latency_ms=latency_ms,
                    trace_data=telemetry.trace_data,
                    tokens_in=telemetry.tokens_in,
                    tokens_out=telemetry.tokens_out,
                    cost_cny=telemetry.cost_cny,
                    model_id=telemetry.model_id,
                    prompt_version=telemetry.prompt_version,
                )
                await EventRecorder(session).record(
                    run_id,
                    "node.completed",
                    {
                        "node_name": step.node_name,
                        "step_sequence": step.sequence,
                        "status": "completed",
                        "latency_ms": latency_ms,
                    },
                )

    async def fail_step(
        self,
        run_id: UUID,
        step_id: UUID,
        *,
        latency_ms: int,
        error_code: str,
        error_message: str,
    ) -> None:
        async with self._session_factory() as session:
            async with session_transaction(session):
                step = await session.get(AgentStep, step_id)
                if step is None or step.status != "running":
                    return
                await TraceRecorder(session).complete_step(
                    step,
                    status="failed",
                    latency_ms=latency_ms,
                    trace_data={},
                    error_code=error_code,
                    error_message=error_message,
                )
                await EventRecorder(session).record(
                    run_id,
                    "node.completed",
                    {
                        "node_name": step.node_name,
                        "step_sequence": step.sequence,
                        "status": "failed",
                        "latency_ms": latency_ms,
                    },
                )
