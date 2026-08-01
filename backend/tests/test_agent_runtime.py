"""PostgreSQL integration tests for the complete Stage 2 Mock Runtime."""

from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
)

from app.agent.executor import AgentRunExecutor
from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.core.security import TokenService
from app.models.agent_run import AgentEvent, AgentRun, AgentStep
from app.models.plan import Plan, Task
from app.providers.llm import MockPlanningProvider
from app.schemas.agent_runs import AgentRunCancelRequest
from app.schemas.enums import CareerStage, GoalType, SkillLevel
from app.schemas.profile import ProfilePatchRequest, ProfilePutRequest
from app.services.agent_runs import AgentRunService
from app.services.auth import AuthService
from app.services.plans import PlanQueryService
from app.services.profiles import ProfileService


class ManualExecutor(AgentRunExecutor):
    def __init__(self) -> None:
        self.submitted: list[UUID] = []

    def submit(self, run_id: UUID) -> None:
        self.submitted.append(run_id)

    async def request_cancel(self, run_id: UUID) -> None:
        del run_id


def runtime_factory(
    connection: AsyncConnection,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=connection,
        class_=AsyncSession,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )


async def create_user(session: AsyncSession, *, with_profile: bool = True) -> UUID:
    user = (await AuthService(session, TokenService(get_settings())).login_guest(None)).user
    if with_profile:
        await ProfileService(session).put(
            user_id=user.id,
            payload=ProfilePutRequest(
                goal_type=GoalType.AGENT_APP,
                stage=CareerStage.PREPARING,
                time_budget_minutes=90,
                skill_level=SkillLevel.INTERMEDIATE,
                skill_summary="FastAPI and PostgreSQL",
            ),
            idempotency_key=f"profile-{user.id}",
        )
    return user.id


async def create_run(
    session: AsyncSession,
    user_id: UUID,
    *,
    message: str = "帮我制定未来五周的求职计划",
    key: str = "run-1",
    settings: Settings | None = None,
    scheduler: AgentRunExecutor | None = None,
) -> AgentRun:
    service = AgentRunService(
        session,
        settings or get_settings(),
        scheduler or ManualExecutor(),
    )
    return await service.create(
        user_id=user_id,
        message=message,
        hint_intent="create_plan",
        goal_type_override=None,
        source_plan_id=None,
        idempotency_key=key,
    )


async def refresh_run(session: AsyncSession, run_id: UUID) -> AgentRun:
    session.expire_all()
    run = await session.get(AgentRun, run_id)
    assert run is not None
    await session.refresh(run)
    return run


@pytest.mark.asyncio
async def test_happy_run_persists_plan_tasks_snapshot_and_last_terminal_event(
    db_connection: AsyncConnection,
    db_session: AsyncSession,
) -> None:
    user_id = await create_user(db_session)
    run = await create_run(db_session, user_id)
    await AgentRunExecutor(runtime_factory(db_connection)).execute(run.id)
    run = await refresh_run(db_session, run.id)

    events = list(
        await db_session.scalars(
            select(AgentEvent).where(AgentEvent.run_id == run.id).order_by(AgentEvent.sequence)
        )
    )
    plan = await db_session.scalar(select(Plan).where(Plan.source_run_id == run.id))
    tasks = list(await db_session.scalars(select(Task).where(Task.user_id == user_id)))

    assert run.status == "completed"
    assert run.result_kind == "plan"
    assert run.final_plan_id is not None
    assert run.input_snapshot_json is not None
    assert plan is not None
    assert len(plan.weekly_focus_json) == 5
    assert 1 <= len(tasks) <= 3
    assert sum(task.estimated_minutes for task in tasks) <= 90
    assert [event.sequence for event in events] == list(range(1, len(events) + 1))
    assert [
        event.payload_json["node_name"] for event in events if event.event_type == "node.started"
    ] == [
        "risk_gate",
        "intent_router",
        "context_builder",
        "career_planning_agent",
        "rule_validator",
        "companion_response",
        "persist",
    ]
    assert events[-1].event_type == "run.completed"
    assert sum(event.event_type.startswith("run.") for event in events[-1:]) == 1
    assert (
        sum(
            event.event_type in {"run.completed", "run.degraded", "run.failed", "run.cancelled"}
            for event in events
        )
        == 1
    )
    input_snapshot = run.input_snapshot_json
    config_snapshot = run.config_snapshot_json
    await ProfileService(db_session).patch(
        user_id=user_id,
        payload=ProfilePatchRequest(version=1, time_budget_minutes=30),
    )
    run = await refresh_run(db_session, run.id)
    assert run.input_snapshot_json == input_snapshot
    assert run.config_snapshot_json == config_snapshot


@pytest.mark.asyncio
async def test_run_latency_never_becomes_negative_when_database_clock_is_ahead(
    db_connection: AsyncConnection,
    db_session: AsyncSession,
) -> None:
    user_id = await create_user(db_session)
    run = await create_run(db_session, user_id, key="clock-skew")
    run.created_at = datetime.now(UTC) + timedelta(seconds=1)
    await db_session.flush()

    await AgentRunExecutor(runtime_factory(db_connection)).execute(run.id)
    run = await refresh_run(db_session, run.id)

    assert run.status == "completed"
    assert run.total_latency_ms == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("message", "with_profile", "kind", "reason"),
    [
        ("帮我制定计划", False, "clarification", "profile_incomplete"),
        ("我想自杀", True, "safe_response", "high_risk_routed"),
    ],
)
async def test_terminal_branches_are_recoverable_without_plan(
    db_connection: AsyncConnection,
    db_session: AsyncSession,
    message: str,
    with_profile: bool,
    kind: str,
    reason: str,
) -> None:
    user_id = await create_user(db_session, with_profile=with_profile)
    run = await create_run(db_session, user_id, message=message)
    await AgentRunExecutor(runtime_factory(db_connection)).execute(run.id)
    run = await refresh_run(db_session, run.id)

    assert run.status == "degraded"
    assert run.result_kind == kind
    assert run.fallback_reason == reason
    assert run.result_payload_json
    assert (
        await db_session.scalar(
            select(func.count()).select_from(Plan).where(Plan.source_run_id == run.id)
        )
        == 0
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("marker", "expected_status", "expected_revise_steps"),
    [
        ("[mock:invalid-schema]", "completed", 0),
        ("[mock:invalid-schema-twice]", "degraded", 0),
        ("[mock:rule-repair]", "completed", 1),
        ("[mock:rule-fallback]", "degraded", 2),
    ],
)
async def test_repairs_are_bounded_and_fallback_is_deterministic(
    db_connection: AsyncConnection,
    db_session: AsyncSession,
    marker: str,
    expected_status: str,
    expected_revise_steps: int,
) -> None:
    user_id = await create_user(db_session)
    run = await create_run(
        db_session,
        user_id,
        message=f"帮我制定未来五周计划 {marker}",
    )
    provider = MockPlanningProvider()
    await AgentRunExecutor(runtime_factory(db_connection), provider).execute(run.id)
    run = await refresh_run(db_session, run.id)
    revise_count = await db_session.scalar(
        select(func.count())
        .select_from(AgentStep)
        .where(
            AgentStep.run_id == run.id,
            AgentStep.node_name == "revise_or_fallback",
        )
    )

    assert run.status == expected_status
    assert revise_count == expected_revise_steps
    assert run.result_kind == "plan"
    assert provider.plan_calls == 1
    assert provider.format_repair_calls == (1 if marker.startswith("[mock:invalid-schema") else 0)
    assert provider.business_repair_calls == (1 if marker.startswith("[mock:rule-") else 0)


@pytest.mark.asyncio
async def test_timeout_and_persist_failure_converge_without_plan(
    db_connection: AsyncConnection,
    db_session: AsyncSession,
) -> None:
    user_id = await create_user(db_session)
    timeout_settings = get_settings().model_copy(update={"agent_deadline_seconds": 1})
    timeout_run = await create_run(
        db_session,
        user_id,
        message="制定计划 [mock:timeout]",
        key="timeout",
        settings=timeout_settings,
    )
    await AgentRunExecutor(runtime_factory(db_connection)).execute(timeout_run.id)
    timeout_run = await refresh_run(db_session, timeout_run.id)
    assert timeout_run.status == "failed"
    assert timeout_run.error_code == "AGENT_DEADLINE_EXCEEDED"
    timeout_events = list(
        await db_session.scalars(
            select(AgentEvent)
            .where(AgentEvent.run_id == timeout_run.id)
            .order_by(AgentEvent.sequence)
        )
    )
    assert timeout_events[-1].event_type == "run.failed"

    failure_run = await create_run(
        db_session,
        user_id,
        message="制定计划 [mock:persist-failure]",
        key="persist-failure",
    )
    await AgentRunExecutor(runtime_factory(db_connection)).execute(failure_run.id)
    failure_run = await refresh_run(db_session, failure_run.id)
    assert failure_run.status == "failed"
    assert failure_run.error_code == "PERSIST_TRANSACTION_FAILED"
    assert (
        await db_session.scalar(
            select(func.count()).select_from(Plan).where(Plan.source_run_id == failure_run.id)
        )
        == 0
    )
    failure_events = list(
        await db_session.scalars(
            select(AgentEvent)
            .where(AgentEvent.run_id == failure_run.id)
            .order_by(AgentEvent.sequence)
        )
    )
    assert failure_events[-1].event_type == "run.failed"


@pytest.mark.asyncio
async def test_user_cancel_stops_graph_and_writes_one_terminal(
    db_connection: AsyncConnection,
    db_session: AsyncSession,
) -> None:
    user_id = await create_user(db_session)
    settings = get_settings().model_copy(update={"agent_deadline_seconds": 5})
    factory = runtime_factory(db_connection)
    scheduler = ManualExecutor()
    run = await create_run(
        db_session,
        user_id,
        message="制定计划 [mock:timeout]",
        key="cancel",
        settings=settings,
        scheduler=scheduler,
    )
    service = AgentRunService(db_session, settings, scheduler)
    await service.cancel(
        run_id=run.id,
        user_id=user_id,
        payload=AgentRunCancelRequest(),
        idempotency_key="cancel-1",
    )
    await AgentRunExecutor(factory).execute(run.id)
    run = await refresh_run(db_session, run.id)
    terminal_count = await db_session.scalar(
        select(func.count())
        .select_from(AgentEvent)
        .where(
            AgentEvent.run_id == run.id,
            AgentEvent.event_type.in_(
                ("run.completed", "run.degraded", "run.failed", "run.cancelled")
            ),
        )
    )
    assert run.status == "cancelled"
    assert run.error_code == "RUN_CANCELLED"
    assert terminal_count == 1


@pytest.mark.asyncio
async def test_idempotency_active_conflict_sse_resume_and_user_isolation(
    db_connection: AsyncConnection,
    db_session: AsyncSession,
) -> None:
    user_a = await create_user(db_session)
    user_b = await create_user(db_session)
    scheduler = ManualExecutor()
    service_a = AgentRunService(db_session, get_settings(), scheduler)
    first = await create_run(db_session, user_a, key="same-key", scheduler=scheduler)
    first_id = first.id
    repeated = await create_run(db_session, user_a, key="same-key", scheduler=scheduler)
    assert repeated.id == first.id
    with pytest.raises(AppError) as conflict:
        await create_run(db_session, user_a, key="other-key", scheduler=scheduler)
    assert conflict.value.code == "STATE_RUN_ALREADY_ACTIVE"

    await AgentRunExecutor(runtime_factory(db_connection)).execute(first_id)
    first = await refresh_run(db_session, first_id)
    all_events = [
        chunk
        async for chunk in service_a.stream_events(
            run_id=first.id, user_id=user_a, after_sequence=0
        )
    ]
    resumed = [
        chunk
        async for chunk in service_a.stream_events(
            run_id=first.id, user_id=user_a, after_sequence=2
        )
    ]
    assert all_events[0].startswith("id: 1\n")
    assert resumed[0].startswith("id: 3\n")
    assert "event: run.completed" in all_events[-1]

    with pytest.raises(AppError) as hidden_run:
        await service_a.get(first.id, user_b)
    with pytest.raises(AppError) as hidden_plan:
        await PlanQueryService(db_session).get_active(user_b)
    other_tasks = await PlanQueryService(db_session).list_tasks(
        user_id=user_b,
        scheduled_date=datetime.now(UTC).date(),
        state=None,
        plan_id=None,
        limit=50,
    )
    assert hidden_run.value.status_code == HTTPStatus.NOT_FOUND
    assert hidden_plan.value.status_code == HTTPStatus.NOT_FOUND
    assert other_tasks.items == []


@pytest.mark.asyncio
async def test_startup_recovery_fails_expired_active_run_once(
    db_connection: AsyncConnection,
    db_session: AsyncSession,
) -> None:
    user_id = await create_user(db_session)
    run = await create_run(db_session, user_id, key="interrupted")
    run_id = run.id
    run.deadline_at = datetime.now(UTC) - timedelta(seconds=1)
    await db_session.flush()
    executor = AgentRunExecutor(runtime_factory(db_connection))

    assert await executor.recover_interrupted() == 1
    recovered = await refresh_run(db_session, run_id)
    terminal_count = await db_session.scalar(
        select(func.count())
        .select_from(AgentEvent)
        .where(
            AgentEvent.run_id == run_id,
            AgentEvent.event_type == "run.failed",
        )
    )
    assert recovered.status == "failed"
    assert recovered.error_code == "PROCESS_INTERRUPTED"
    assert terminal_count == 1
