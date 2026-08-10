"""Guards for the multi-day SCHEDULE_DATE / per-day TIME_BUDGET validator semantics.

These tests pin the bug fix that lets a real LLM spread tasks across the
1~8 week planning window while still enforcing each individual day's budget.
"""

from datetime import date, timedelta
from uuid import uuid4

from app.agent.nodes import build_planning_context, validate_candidate
from app.schemas.agent_runs import (
    PlanCandidate,
    PlanningContext,
    ProfileContext,
    TaskCandidate,
    ValidationReport,
    WeeklyFocusCandidate,
)
from app.schemas.enums import CareerStage, GoalType, SkillLevel, TaskType


def _profile() -> ProfileContext:
    return ProfileContext(
        user_id=uuid4(),
        version=1,
        goal_type=GoalType.AGENT_APP,
        stage=CareerStage.PREPARING,
        time_budget_minutes=60,
        skill_level=SkillLevel.INTERMEDIATE,
    )


def _context(daily_budget: int = 60, weeks: int = 4) -> PlanningContext:
    context = build_planning_context(
        profile=_profile(),
        requested_horizon_weeks=weeks,
        source_plan_id=None,
        source_plan_version=None,
        completed_facts=[],
    )
    return context.model_copy(update={"time_budget_minutes": daily_budget})


def _candidate(context: PlanningContext, tasks: list[TaskCandidate]) -> PlanCandidate:
    window = context.planning_window
    return PlanCandidate(
        plan_date=window.planning_date,
        horizon_start=window.horizon_start,
        horizon_end=window.horizon_end,
        overall_direction="方向",
        weekly_focus=[
            WeeklyFocusCandidate(week_index=i, focus=f"重点{i}", success_signal=f"产物{i}")
            for i in range(1, window.horizon_weeks + 1)
        ],
        summary="摘要",
        rationale="原因",
        tasks=tasks,
    )


def _task(
    scheduled_date: date,
    minutes: int,
    *,
    title: str = "任务",
    deliverable: str = "产物",
) -> TaskCandidate:
    return TaskCandidate(
        title=title,
        task_type=TaskType.LEARNING,
        scheduled_date=scheduled_date,
        starter_action="打开",
        deliverable=deliverable,
        estimated_minutes=minutes,
        rationale="原因",
    )


def _failed_codes(report: ValidationReport) -> list[str]:
    return [check.code for check in report.checks if not check.passed]


# 1. 旧语义（单日多 task 总和超预算）依然要失败 —— 守护预算硬约束没被放开
def test_single_day_over_budget_still_fails() -> None:
    context = _context(daily_budget=60)
    plan = _candidate(
        context,
        [
            _task(context.planning_window.planning_date, 40, title="a", deliverable="da"),
            _task(context.planning_window.planning_date, 40, title="b", deliverable="db"),
        ],
    )
    report = validate_candidate(plan, context)
    assert report.passed is False
    assert "TIME_BUDGET" in _failed_codes(report)


# 2. 新语义：窗口内多日任务（每天各自不超预算）必须通过 —— 守护修复本身
def test_multi_day_in_window_within_daily_budget_passes() -> None:
    context = _context(daily_budget=60)
    window = context.planning_window
    plan = _candidate(
        context,
        [
            _task(window.planning_date, 40, title="today", deliverable="d1"),
            _task(window.planning_date + timedelta(days=6), 30, title="day7", deliverable="d2"),
        ],
    )
    report = validate_candidate(plan, context)
    assert report.passed, _failed_codes(report)


# 3. 窗口外的日期仍被拒绝（horizon_start 之前 / horizon_end 之后）
def test_task_outside_window_still_fails_schedule_date() -> None:
    context = _context(daily_budget=60)
    window = context.planning_window
    out_of_range = window.horizon_end + timedelta(days=2)
    plan = _candidate(context, [_task(out_of_range, 10, title="x", deliverable="dx")])
    report = validate_candidate(plan, context)
    assert report.passed is False
    assert "SCHEDULE_DATE" in _failed_codes(report)


def test_task_after_seven_day_action_window_fails_schedule_date() -> None:
    context = _context(daily_budget=60)
    window = context.planning_window
    plan = _candidate(
        context,
        [_task(window.planning_date + timedelta(days=7), 10, title="day8", deliverable="d8")],
    )
    report = validate_candidate(plan, context)
    assert report.passed is False
    assert "SCHEDULE_DATE" in _failed_codes(report)


# 4. 多日，某一天的总和超预算 —— TIME_BUDGET 按日分组生效
def test_multi_day_one_day_over_budget_fails_only_time_budget() -> None:
    context = _context(daily_budget=60)
    window = context.planning_window
    plan = _candidate(
        context,
        [
            _task(window.planning_date, 40, title="a", deliverable="da"),
            _task(window.planning_date, 40, title="b", deliverable="db"),
            _task(window.planning_date + timedelta(days=6), 30, title="c", deliverable="dc"),
        ],
    )
    report = validate_candidate(plan, context)
    assert report.passed is False
    codes = _failed_codes(report)
    assert "TIME_BUDGET" in codes
    # 排期日期本身都在窗口内，所以 SCHEDULE_DATE 不应失败
    assert "SCHEDULE_DATE" not in codes


# 5. 单 task 单日，正好等于预算 —— 边界通过
def test_single_task_equal_to_budget_passes() -> None:
    context = _context(daily_budget=60)
    plan = _candidate(
        context,
        [_task(context.planning_window.planning_date, 60, title="only", deliverable="d")],
    )
    report = validate_candidate(plan, context)
    assert report.passed, _failed_codes(report)
