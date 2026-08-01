"""Agent Run creation, idempotency, cancellation, lookup, and SSE replay."""

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.executor import AgentRunExecutor
from app.core.config import Settings
from app.core.database import session_transaction
from app.core.exceptions import AppError
from app.harness.events import EventRecorder
from app.harness.snapshots import SnapshotService
from app.models.agent_run import AgentRun
from app.repositories.agent_runs import AgentRunRepository
from app.repositories.plans import PlanRepository
from app.schemas.agent_runs import (
    AgentRunCancelRequest,
    AgentRunResponse,
    ClarificationRequest,
    PlanResultSummary,
    SafeResponse,
    TerminalResult,
)
from app.schemas.enums import ReplanMode, RunIntent, RunResultKind, RunStatus

TERMINAL_STATUSES = {"completed", "degraded", "failed", "cancelled"}


class AgentRunService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        executor: AgentRunExecutor,
    ) -> None:
        self._session = session
        self._settings = settings
        self._executor = executor
        self._runs = AgentRunRepository(session)
        self._plans = PlanRepository(session)

    async def create(
        self,
        *,
        user_id: UUID,
        message: str,
        hint_intent: str | None,
        goal_type_override: str | None,
        source_plan_id: UUID | None,
        idempotency_key: str,
    ) -> AgentRun:
        config = SnapshotService.build_config(self._settings)
        created = False
        try:
            async with session_transaction(self._session):
                existing = await self._runs.get_by_idempotency(user_id, idempotency_key)
                if existing is not None:
                    return existing
                source_plan_id = await self._resolve_source_plan(
                    user_id=user_id,
                    hint_intent=hint_intent,
                    source_plan_id=source_plan_id,
                )
                active = await self._runs.get_active_for_user(user_id)
                if active is not None:
                    raise AppError(
                        code="STATE_RUN_ALREADY_ACTIVE",
                        message="another Agent Run is already active",
                        status_code=HTTPStatus.CONFLICT,
                    )
                run = AgentRun(
                    user_id=user_id,
                    idempotency_key=idempotency_key,
                    request_text=message,
                    hint_intent=hint_intent,
                    goal_type_override=goal_type_override,
                    source_plan_id=source_plan_id,
                    status="pending",
                    graph_version=config.graph_version,
                    config_snapshot_json=config.model_dump(mode="json"),
                    deadline_at=datetime.now(UTC) + timedelta(seconds=config.deadline_seconds),
                )
                await self._runs.create(run)
                await EventRecorder(self._session).record(
                    run.id,
                    "run.created",
                    {"status": "pending", "graph_version": run.graph_version},
                )
                created = True
        except IntegrityError as exc:
            raise AppError(
                code="STATE_RUN_ALREADY_ACTIVE",
                message="another Agent Run is already active",
                status_code=HTTPStatus.CONFLICT,
            ) from exc
        if created:
            self._executor.submit(run.id)
        return run

    async def get(self, run_id: UUID, user_id: UUID) -> AgentRun:
        async with session_transaction(self._session):
            run = await self._runs.get_for_user(run_id, user_id)
            if run is None:
                raise AppError(
                    code="NOT_FOUND_RUN",
                    message="Agent Run was not found",
                    status_code=HTTPStatus.NOT_FOUND,
                )
            return run

    async def get_response(self, run_id: UUID, user_id: UUID) -> AgentRunResponse:
        return self.to_response(await self.get(run_id, user_id))

    async def cancel(
        self,
        *,
        run_id: UUID,
        user_id: UUID,
        payload: AgentRunCancelRequest,
        idempotency_key: str,
    ) -> AgentRun:
        del payload, idempotency_key
        async with session_transaction(self._session):
            run = await self._runs.get_for_user(run_id, user_id)
            if run is None:
                raise AppError(
                    code="NOT_FOUND_RUN",
                    message="Agent Run was not found",
                    status_code=HTTPStatus.NOT_FOUND,
                )
            if run.status == "cancelled":
                return run
            if run.status in TERMINAL_STATUSES:
                raise AppError(
                    code="STATE_RUN_ALREADY_FINISHED",
                    message="Agent Run is already finished",
                    status_code=HTTPStatus.CONFLICT,
                )
            requested = await self._runs.request_cancel(run_id, user_id)
            if requested is None:
                raise AppError(
                    code="STATE_RUN_ALREADY_FINISHED",
                    message="Agent Run is already finished",
                    status_code=HTTPStatus.CONFLICT,
                )
            run = requested
        await self._executor.request_cancel(run_id)
        return run

    async def stream_events(
        self,
        *,
        run_id: UUID,
        user_id: UUID,
        after_sequence: int,
    ) -> AsyncIterator[str]:
        await self.get(run_id, user_id)
        sequence = after_sequence
        heartbeat_elapsed = 0.0
        poll = self._settings.agent_poll_interval_seconds
        while True:
            async with session_transaction(self._session):
                events = await self._runs.list_events_after(run_id, user_id, sequence)
                run = await self._runs.get_for_user(run_id, user_id)
            for event in events:
                sequence = event.sequence
                yield self._format_sse(
                    event.event_type,
                    event.payload_json,
                    event_id=event.sequence,
                )
            if run is None or (run.status in TERMINAL_STATUSES and not events):
                return
            if events:
                heartbeat_elapsed = 0
            else:
                await asyncio.sleep(poll)
                heartbeat_elapsed += poll
                if heartbeat_elapsed >= self._settings.agent_heartbeat_seconds:
                    heartbeat_elapsed = 0
                    yield self._format_sse(
                        "heartbeat",
                        {"run_id": str(run_id), "timestamp": datetime.now(UTC).isoformat()},
                    )

    async def _resolve_source_plan(
        self,
        *,
        user_id: UUID,
        hint_intent: str | None,
        source_plan_id: UUID | None,
    ) -> UUID | None:
        if source_plan_id is not None:
            source = await self._plans.get_for_user(source_plan_id, user_id)
            if source is None:
                raise AppError(
                    code="NOT_FOUND_SOURCE_PLAN",
                    message="source Plan was not found",
                    status_code=HTTPStatus.NOT_FOUND,
                )
            return source.id
        if hint_intent != "replan":
            return None
        source = await self._plans.get_active_for_user(user_id)
        if source is None:
            source = await self._plans.get_latest_completed_for_user(user_id)
        if source is None:
            raise AppError(
                code="VALIDATION_REPLAN_SOURCE_UNAVAILABLE",
                message="no Plan is available for replanning",
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            )
        return source.id

    @staticmethod
    def to_response(run: AgentRun) -> AgentRunResponse:
        result: TerminalResult | None = None
        if run.result_payload_json is not None:
            if run.result_kind == "plan":
                result = PlanResultSummary.model_validate(run.result_payload_json)
            elif run.result_kind == "clarification":
                result = ClarificationRequest.model_validate(run.result_payload_json)
            elif run.result_kind == "safe_response":
                result = SafeResponse.model_validate(run.result_payload_json)
        return AgentRunResponse(
            run_id=run.id,
            status=RunStatus(run.status),
            resolved_intent=(
                RunIntent(run.resolved_intent) if run.resolved_intent is not None else None
            ),
            replan_mode=(ReplanMode(run.replan_mode) if run.replan_mode is not None else None),
            result_kind=(RunResultKind(run.result_kind) if run.result_kind is not None else None),
            result=result,
            final_plan_id=run.final_plan_id,
            fallback_reason=run.fallback_reason,
            error_code=run.error_code,
            risk_category=run.risk_category,
            total_tokens_in=run.total_tokens_in,
            total_tokens_out=run.total_tokens_out,
            total_cost_cny=run.total_cost_cny,
            total_latency_ms=run.total_latency_ms,
            created_at=run.created_at,
            finished_at=run.finished_at,
        )

    @staticmethod
    def _format_sse(
        event_type: str,
        data: dict[str, object],
        *,
        event_id: int | None = None,
    ) -> str:
        prefix = f"id: {event_id}\n" if event_id is not None else ""
        return (
            f"{prefix}event: {event_type}\n"
            f"data: {json.dumps(data, ensure_ascii=False, separators=(',', ':'))}\n\n"
        )
