"""Deterministic Stage 2 schema, node, budget, and Tool registry tests."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.agent.errors import BudgetExceededError
from app.agent.graph import FixedPlanningGraph
from app.agent.nodes import (
    build_planning_context,
    fallback_candidate,
    risk_gate,
    route_intent,
    validate_candidate,
)
from app.core.config import get_settings
from app.harness.budget import BudgetGuard, CancellationToken
from app.harness.snapshots import SnapshotService
from app.schemas.agent_runs import (
    AgentRunCreateRequest,
    PlanCandidate,
    PlanningContext,
    PlanningState,
    ProfileContext,
    TaskCandidate,
    WeeklyFocusCandidate,
)
from app.schemas.enums import CareerStage, GoalType, ReplanMode, SkillLevel, TaskType
from app.tools.registry import ToolRegistry


def test_fallback_reason_ends_the_bounded_repair_loop() -> None:
    plan, context = candidate()
    invalid = plan.model_copy(
        update={
            "tasks": [
                task.model_copy(update={"estimated_minutes": context.time_budget_minutes + 1})
                for task in plan.tasks
            ]
        }
    )
    report = validate_candidate(invalid, context)
    state: PlanningState = {
        "validation_report": report,
        "fallback_reason": "business_repair_exhausted",
    }

    assert report.passed is False
    assert FixedPlanningGraph._after_validation(state) == "passed"


def profile() -> ProfileContext:
    return ProfileContext(
        user_id=uuid4(),
        version=1,
        goal_type=GoalType.AGENT_APP,
        stage=CareerStage.PREPARING,
        time_budget_minutes=60,
        skill_level=SkillLevel.INTERMEDIATE,
    )


def candidate() -> tuple[PlanCandidate, PlanningContext]:
    context = build_planning_context(
        profile=profile(),
        requested_horizon_weeks=5,
        source_plan_id=None,
        source_plan_version=None,
        completed_facts=[],
    )
    window = context.planning_window
    plan = PlanCandidate(
        plan_date=window.planning_date,
        horizon_start=window.horizon_start,
        horizon_end=window.horizon_end,
        overall_direction="完成可演示的 Agent 项目",
        weekly_focus=[
            WeeklyFocusCandidate(
                week_index=index,
                focus=f"第 {index} 周重点",
                success_signal=f"第 {index} 周产物",
            )
            for index in range(1, 6)
        ],
        summary="今天完成最小闭环",
        rationale="先形成可验证证据",
        tasks=[
            TaskCandidate(
                title="实现一个闭环",
                task_type=TaskType.PROJECT,
                scheduled_date=window.planning_date,
                starter_action="打开项目并运行测试",
                deliverable="一次通过的测试报告",
                estimated_minutes=60,
            )
        ],
    )
    return plan, context


def test_run_schema_is_strict_and_weekly_focus_is_contiguous() -> None:
    with pytest.raises(ValidationError):
        AgentRunCreateRequest.model_validate({"message": "计划", "user_id": str(uuid4())})
    with pytest.raises(ValidationError):
        PlanCandidate(
            plan_date=datetime.now(UTC).date(),
            horizon_start=datetime.now(UTC).date(),
            horizon_end=datetime.now(UTC).date() + timedelta(days=7),
            overall_direction="方向",
            weekly_focus=[
                WeeklyFocusCandidate(week_index=2, focus="错误周序号", success_signal="产物")
            ],
            summary="摘要",
            rationale="原因",
            tasks=[
                TaskCandidate(
                    title="任务",
                    task_type=TaskType.OTHER,
                    scheduled_date=datetime.now(UTC).date(),
                    starter_action="开始",
                    deliverable="产物",
                    estimated_minutes=15,
                )
            ],
        )


def test_risk_intent_and_rule_validation_are_deterministic() -> None:
    assert risk_gate("我想自杀").level == "high"
    assert risk_gate("最近求职压力有点大").level == "none"
    intent = route_intent(
        message="帮我制定未来五周计划",
        hint_intent="create_plan",
        profile=profile(),
        source_plan_exists=False,
    )
    assert intent.requested_horizon_weeks == 5
    assert intent.replan_mode == ReplanMode.INITIAL
    plan, context = candidate()
    report = validate_candidate(plan, context)
    assert report.passed
    over_budget = plan.model_copy(
        update={"tasks": [plan.tasks[0].model_copy(update={"estimated_minutes": 61})]}
    )
    failed = validate_candidate(over_budget, context)
    assert not failed.passed
    assert [check.code for check in failed.checks if not check.passed] == ["TIME_BUDGET"]


def test_explicit_goal_override_wins_when_replanning() -> None:
    intent = route_intent(
        message="调整后续计划",
        hint_intent="replan",
        profile=profile(),
        source_plan_exists=True,
        goal_type_override=GoalType.AI_BACKEND,
    )

    assert intent.effective_goal_type == GoalType.AI_BACKEND
    assert intent.replan_mode == ReplanMode.ADJUST


def test_fallback_has_progressive_weeks_and_seven_dated_tasks() -> None:
    _, context = candidate()
    plan = fallback_candidate(context, ReplanMode.INITIAL)

    assert len({item.focus for item in plan.weekly_focus}) == 5
    assert len({item.success_signal for item in plan.weekly_focus}) == 5
    assert [task.scheduled_date for task in plan.tasks] == [
        context.planning_window.planning_date + timedelta(days=offset)
        for offset in range(7)
    ]
    assert all(task.starter_action.startswith("1. ") for task in plan.tasks)
    assert all("包含" in task.deliverable for task in plan.tasks)


def test_repeated_weekly_focus_fails_validation() -> None:
    plan, context = candidate()
    repeated = plan.model_copy(
        update={
            "weekly_focus": [
                item.model_copy(update={"focus": "重复重点", "success_signal": "重复产物"})
                for item in plan.weekly_focus
            ]
        }
    )

    report = validate_candidate(repeated, context)

    assert report.passed is False
    assert [check.code for check in report.checks if not check.passed] == ["WEEKLY_FOCUS"]


def test_stage2_budget_and_tool_registry_enforce_empty_tool_list() -> None:
    settings = SnapshotService.build_config(get_settings())
    guard = BudgetGuard(
        settings,
        datetime.now(UTC) + timedelta(seconds=5),
        CancellationToken(),
    )
    guard.record_llm_call(100, 100)
    with pytest.raises(BudgetExceededError, match="input_tokens"):
        guard.record_llm_call(settings.max_input_tokens_per_call + 1, 0)
    guard.claim_format_repair()
    assert guard.format_repairs == 1
    assert ToolRegistry(feature_stage=2).available_specs() == []
