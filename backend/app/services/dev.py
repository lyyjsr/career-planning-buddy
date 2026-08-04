"""Developer Trace inspection and isolated offline Replay use cases."""

from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from http import HTTPStatus
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import session_transaction
from app.core.exceptions import AppError
from app.harness.redaction import redact, redacted_snapshot
from app.models.agent_run import AgentEvent, AgentRun, AgentStep, ToolCall
from app.repositories.dev import DevTraceRepository
from app.schemas.dev import (
    DevEventTrace,
    DevRunDetail,
    DevRunListResponse,
    DevRunSummary,
    DevSnapshot,
    DevStepTrace,
    DevToolTrace,
    ReplayResponse,
    TerminalInvariant,
)

TERMINAL_EVENTS = {"run.completed", "run.degraded", "run.failed", "run.cancelled"}


class DevTraceService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = DevTraceRepository(session)

    async def list_runs(
        self,
        *,
        status: str | None,
        result_kind: str | None,
        error_code: str | None,
        cursor: UUID | None,
        limit: int,
    ) -> DevRunListResponse:
        async with session_transaction(self._session):
            rows = await self._repo.list_runs(
                status=status,
                result_kind=result_kind,
                error_code=error_code,
                cursor=cursor,
                limit=limit,
            )
        has_more = len(rows) > limit
        rows = rows[:limit]
        return DevRunListResponse(
            items=[self._summary(row) for row in rows],
            next_cursor=rows[-1].id if has_more and rows else None,
        )

    async def get_run(self, run_id: UUID) -> DevRunDetail:
        async with session_transaction(self._session):
            run = await self._repo.get_run(run_id)
            if run is None:
                raise self._not_found()
            steps, tools, events = await self._repo.get_trace(run_id)
        input_snapshot = None
        if run.input_snapshot_json is not None:
            data, digest = redacted_snapshot(run.input_snapshot_json)
            input_snapshot = DevSnapshot(data=data, sha256=digest)
        config_data, config_digest = redacted_snapshot(run.config_snapshot_json)
        terminal_count = sum(event.event_type in TERMINAL_EVENTS for event in events)
        terminal_is_last = bool(events) and events[-1].event_type in TERMINAL_EVENTS
        return DevRunDetail(
            run=self._summary(run),
            request_text=run.request_text,
            input_snapshot=input_snapshot,
            config_snapshot=DevSnapshot(data=config_data, sha256=config_digest),
            result=redact(run.result_payload_json),
            steps=[
                DevStepTrace(
                    sequence=row.sequence,
                    node_name=row.node_name,
                    attempt=row.attempt,
                    status=row.status,
                    prompt_version=row.prompt_version,
                    model_id=row.model_id,
                    tokens_in=row.tokens_in,
                    tokens_out=row.tokens_out,
                    latency_ms=row.latency_ms,
                    input_hash=row.input_hash,
                    output_hash=row.output_hash,
                    trace_data=redact(row.trace_data),
                    error_code=row.error_code,
                )
                for row in steps
            ],
            tools=[
                DevToolTrace(
                    tool_call_id=row.id,
                    step_id=row.step_id,
                    tool_name=row.tool_name,
                    contract_version=row.tool_contract_version,
                    round=row.round,
                    args=redact(row.args_json),
                    args_hash=row.args_hash,
                    result=redact(row.result_json),
                    result_hash=row.result_hash,
                    provider=row.provider,
                    latency_ms=row.latency_ms,
                    success=row.success,
                    error_code=row.error_code,
                )
                for row in tools
            ],
            events=[
                DevEventTrace(
                    sequence=row.sequence,
                    event_type=row.event_type,
                    payload=redact(row.payload_json),
                    created_at=row.created_at,
                )
                for row in events
            ],
            terminal_invariant=TerminalInvariant(
                terminal_count=terminal_count,
                terminal_is_last=terminal_is_last,
                valid=terminal_count == 1 and terminal_is_last,
            ),
        )

    async def replay(self, run_id: UUID, *, tool_mode: str) -> ReplayResponse:
        """Create an immutable shadow Run from captured snapshots and Tool fixtures.

        Stage 5 Replay deliberately does not invoke a network Provider. It reproduces
        the persisted outcome under the Mock model alias and copies only captured Tool
        results. The source Run and its user-facing Plan are never updated.
        """
        async with session_transaction(self._session):
            source = await self._repo.get_run(run_id)
            if source is None:
                raise self._not_found()
            if source.status not in {"completed", "degraded", "failed", "cancelled"}:
                raise AppError(
                    code="REPLAY_SOURCE_NOT_TERMINAL",
                    message="only terminal Runs can be replayed",
                    status_code=HTTPStatus.CONFLICT,
                )
            source_steps, source_tools, _source_events = await self._repo.get_trace(run_id)
            if tool_mode == "fixture" and any(row.result_json is None for row in source_tools):
                raise AppError(
                    code="REPLAY_FIXTURE_MISSING",
                    message="a captured Tool result required for Replay is missing",
                    status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                )

            now = datetime.now(UTC)
            config = dict(source.config_snapshot_json)
            config.update(
                {
                    "provider": "mock",
                    "model_alias": "mock-career-planner-v1",
                    "replay_tool_mode": tool_mode,
                    "replay_deterministic": tool_mode == "fixture",
                }
            )
            replay = AgentRun(
                user_id=source.user_id,
                idempotency_key=f"replay-{uuid4().hex}",
                request_text=source.request_text,
                hint_intent=source.hint_intent,
                resolved_intent=source.resolved_intent,
                replan_mode=source.replan_mode,
                requested_horizon_weeks=source.requested_horizon_weeks,
                goal_type_override=source.goal_type_override,
                source_plan_id=source.source_plan_id,
                source_review_id=source.source_review_id,
                replay_of_run_id=source.id,
                status=source.status,
                result_kind=source.result_kind,
                result_payload_json=source.result_payload_json,
                final_plan_id=source.final_plan_id,
                graph_version=source.graph_version,
                input_snapshot_json=source.input_snapshot_json,
                config_snapshot_json=config,
                model_id="mock-career-planner-v1",
                total_tokens_in=source.total_tokens_in,
                total_tokens_out=source.total_tokens_out,
                total_cost_cny=Decimal("0"),
                total_latency_ms=0,
                fallback_reason=source.fallback_reason,
                error_code=source.error_code,
                error_message=source.error_message,
                risk_category=source.risk_category,
                deadline_at=now,
                created_at=now,
                started_at=now,
                finished_at=now,
            )
            self._session.add(replay)
            await self._session.flush()

            step_ids: dict[UUID, UUID] = {}
            for source_step in source_steps:
                cloned = AgentStep(
                    run_id=replay.id,
                    sequence=source_step.sequence,
                    node_name=source_step.node_name,
                    attempt=source_step.attempt,
                    status=source_step.status,
                    prompt_version=source_step.prompt_version,
                    model_id=("mock-career-planner-v1" if source_step.model_id else None),
                    tokens_in=source_step.tokens_in,
                    tokens_out=source_step.tokens_out,
                    cost_cny=Decimal("0"),
                    latency_ms=0,
                    input_hash=source_step.input_hash,
                    output_hash=source_step.output_hash,
                    trace_data={**source_step.trace_data, "replayed": True},
                    error_code=source_step.error_code,
                    error_message=source_step.error_message,
                    created_at=now,
                    finished_at=now,
                )
                self._session.add(cloned)
                await self._session.flush()
                step_ids[source_step.id] = cloned.id
            for source_tool in source_tools:
                self._session.add(
                    ToolCall(
                        run_id=replay.id,
                        step_id=step_ids[source_tool.step_id],
                        tool_name=source_tool.tool_name,
                        tool_contract_version=source_tool.tool_contract_version,
                        round=source_tool.round,
                        args_json=source_tool.args_json,
                        args_hash=source_tool.args_hash,
                        result_json=source_tool.result_json,
                        result_preview=source_tool.result_preview,
                        result_hash=source_tool.result_hash,
                        provider="fixture" if tool_mode == "fixture" else source_tool.provider,
                        latency_ms=0,
                        success=source_tool.success,
                        error_code=source_tool.error_code,
                        created_at=now,
                    )
                )
            event_payloads: list[tuple[str, dict[str, object]]] = [
                ("run.created", {"status": "pending", "replay_of_run_id": str(source.id)}),
                (
                    "replay.started",
                    {"tool_mode": tool_mode, "provider": "mock", "source_run_id": str(source.id)},
                ),
            ]
            event_payloads.extend(
                (
                    "node.completed",
                    {
                        "node_name": step.node_name,
                        "step_sequence": step.sequence,
                        "status": step.status,
                        "latency_ms": 0,
                        "replayed": True,
                    },
                )
                for step in source_steps
            )
            terminal_type = f"run.{source.status}"
            terminal_payload: dict[str, object] = {"status": source.status, "replayed": True}
            if source.result_kind is not None:
                terminal_payload["result_kind"] = source.result_kind
            if source.final_plan_id is not None:
                terminal_payload["final_plan_id"] = str(source.final_plan_id)
            if source.error_code is not None:
                terminal_payload["error_code"] = source.error_code
            event_payloads.append((terminal_type, terminal_payload))
            for sequence, (event_type, payload) in enumerate(event_payloads, start=1):
                self._session.add(
                    AgentEvent(
                        run_id=replay.id,
                        sequence=sequence,
                        event_type=event_type,
                        payload_json=payload,
                        created_at=now,
                    )
                )
            replay.next_event_sequence = len(event_payloads) + 1
            replay.next_step_sequence = len(source_steps) + 1
            await self._session.flush()
            replay_id = replay.id
        return ReplayResponse(
            run_id=replay_id,
            replay_of_run_id=run_id,
            status=source.status,
            deterministic=tool_mode == "fixture",
        )

    @staticmethod
    def _summary(run: AgentRun) -> DevRunSummary:
        user_ref = sha256(str(run.user_id).encode("utf-8")).hexdigest()[:12]
        return DevRunSummary(
            run_id=run.id,
            replay_of_run_id=run.replay_of_run_id,
            user_ref=user_ref,
            status=run.status,
            result_kind=run.result_kind,
            resolved_intent=run.resolved_intent,
            graph_version=run.graph_version,
            model_id=run.model_id,
            total_tokens_in=run.total_tokens_in,
            total_tokens_out=run.total_tokens_out,
            total_cost_cny=run.total_cost_cny,
            total_latency_ms=run.total_latency_ms,
            fallback_reason=run.fallback_reason,
            error_code=run.error_code,
            created_at=run.created_at,
            finished_at=run.finished_at,
        )

    @staticmethod
    def _not_found() -> AppError:
        return AppError(
            code="NOT_FOUND_RUN",
            message="Agent Run was not found",
            status_code=HTTPStatus.NOT_FOUND,
        )
