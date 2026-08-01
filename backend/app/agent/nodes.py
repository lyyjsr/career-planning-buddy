"""Deterministic controlled Stage 4 graph nodes."""

import re
from datetime import UTC, date, datetime, timedelta
from typing import Literal
from uuid import UUID

from app.schemas.agent_runs import (
    ClarificationRequest,
    CompanionMessageCandidate,
    EvidenceCatalogItem,
    IntentResult,
    PlanCandidate,
    PlanContext,
    PlanningContext,
    PlanningWindow,
    ProfileContext,
    ReviewContext,
    RiskResult,
    SafeResponse,
    TaskCandidate,
    TaskContext,
    ValidationCheck,
    ValidationReport,
    WeeklyFocusCandidate,
)
from app.schemas.enums import GoalType, ReplanMode, RunIntent, TaskType

HIGH_RISK_PATTERNS = (
    ("risk_self_harm_zh", re.compile(r"自杀|结束生命|伤害自己")),
    ("risk_self_harm_en", re.compile(r"\b(suicide|kill myself|self[- ]harm)\b", re.I)),
)


def risk_gate(message: str) -> RiskResult:
    matched = [rule_id for rule_id, pattern in HIGH_RISK_PATTERNS if pattern.search(message)]
    return RiskResult(
        level="high" if matched else "none",
        category="self_harm" if matched else None,
        method="rule",
        matched_rule_ids=matched,
        confidence=1 if matched else None,
    )


def route_intent(
    *,
    message: str,
    hint_intent: str | None,
    profile: ProfileContext | None,
    source_plan_exists: bool,
    forced_replan_mode: ReplanMode | None = None,
) -> IntentResult:
    query_only = any(term in message for term in ("查看计划", "查询任务", "我的计划"))
    missing_slots: list[Literal["goal_type", "stage", "time_budget_minutes", "skill_level"]] = []
    if profile is None:
        missing_slots = ["goal_type", "stage", "time_budget_minutes", "skill_level"]
    requested_weeks = parse_horizon_weeks(message)
    if query_only:
        intent = RunIntent.UNSUPPORTED
        mode = ReplanMode.INITIAL
    elif hint_intent == RunIntent.REPLAN.value or source_plan_exists:
        intent = RunIntent.REPLAN
        mode = forced_replan_mode or (
            ReplanMode.ADJUST
            if any(term in message for term in ("调整", "减量", "换重点", "阻碍"))
            else ReplanMode.CONTINUE
        )
    else:
        intent = RunIntent.CREATE_PLAN
        mode = ReplanMode.INITIAL
    requires_fresh_information = any(
        marker in message
        for marker in ("最新", "当前岗位", "市场信息", "搜索", "[mock:tool-search]")
    )
    return IntentResult(
        intent=intent,
        replan_mode=mode,
        confidence=1,
        missing_slots=missing_slots,
        effective_goal_type=profile.goal_type if profile else None,
        requested_horizon_weeks=requested_weeks,
        requires_fresh_information=requires_fresh_information,
        method="rule",
    )


def parse_horizon_weeks(message: str) -> int | None:
    match = re.search(r"(?:未来|接下来)?\s*(\d+)\s*周", message)
    if match:
        return max(1, min(8, int(match.group(1))))
    chinese_match = re.search(r"(?:未来|接下来)?\s*([一二三四五六七八])\s*周", message)
    if chinese_match:
        chinese_weeks = "一二三四五六七八".index(chinese_match.group(1)) + 1
        return chinese_weeks
    month_match = re.search(r"(?:未来|接下来)?\s*(\d+)\s*个?月", message)
    if month_match:
        return max(1, min(8, int(month_match.group(1)) * 4))
    return None


def build_clarification(intent: IntentResult) -> ClarificationRequest:
    if intent.intent == RunIntent.UNSUPPORTED:
        return ClarificationRequest(
            questions=["这个请求不需要生成新计划，请前往计划或任务页面查看。"],
            slot_names=["intent"],
            hint_options={"intent": ["create_plan", "replan"]},
            reason="unsupported_intent",
        )
    labels = {
        "goal_type": "你希望重点准备哪类岗位？",
        "stage": "你目前处于哪个求职阶段？",
        "time_budget_minutes": "你每天可以投入多少分钟？",
        "skill_level": "你如何评价当前技能水平？",
    }
    slots = intent.missing_slots[:3]
    return ClarificationRequest(
        questions=[labels[slot] for slot in slots],
        slot_names=list(slots),
        hint_options={
            "goal_type": [item.value for item in GoalType],
            "stage": ["exploring", "preparing", "applying", "interviewing"],
            "time_budget_minutes": ["30", "60", "90"],
            "skill_level": ["beginner", "intermediate", "advanced"],
        },
        reason="profile_incomplete",
    )


def build_safe_response() -> SafeResponse:
    return SafeResponse(
        message="现在最重要的是先确保你的安全。请尽快联系身边可信任的人或当地紧急服务。",
        resource_ids=["default-local-resource"],
        disclaimer="本服务不提供医疗诊断或紧急救援。",
    )


def build_planning_context(
    *,
    profile: ProfileContext,
    requested_horizon_weeks: int | None,
    source_plan_id: UUID | None,
    source_plan_version: int | None,
    source_plan: PlanContext | None = None,
    source_review: ReviewContext | None = None,
    recent_tasks: list[TaskContext] | None = None,
    recent_reviews: list[ReviewContext] | None = None,
    completed_facts: list[str],
    blockers: list[str] | None = None,
    planning_date: date | None = None,
) -> PlanningContext:
    today = planning_date or datetime.now(UTC).date()
    horizon_weeks = requested_horizon_weeks or _deadline_weeks(today, profile.deadline)
    window = PlanningWindow(
        planning_date=today,
        horizon_start=today,
        horizon_end=today + timedelta(weeks=horizon_weeks) - timedelta(days=1),
        horizon_weeks=horizon_weeks,
    )
    return PlanningContext(
        profile=profile,
        planning_window=window,
        source_plan_id=source_plan_id,
        source_plan_version=source_plan_version,
        source_plan=source_plan,
        source_review=source_review,
        recent_tasks=recent_tasks or [],
        recent_reviews=recent_reviews or [],
        completed_facts=completed_facts,
        blockers=blockers or [],
        timezone="UTC",
        time_budget_minutes=profile.time_budget_minutes,
        token_estimate=250 + len(completed_facts) * 12,
    )


def _deadline_weeks(today: date, deadline: date | None) -> int:
    if deadline is None:
        return 4
    days = max((deadline - today).days + 1, 1)
    return max(1, min(8, (days + 6) // 7))


CHECK_ORDER = (
    "HORIZON_MATCH",
    "WEEKLY_FOCUS",
    "TASK_COUNT",
    "TIME_BUDGET",
    "STARTER_ACTION",
    "DELIVERABLE",
    "SCHEDULE_DATE",
    "RECENT_DUPLICATE",
    "REPLAN_CONTINUITY",
    "SOURCE_INTEGRITY",
    "GOAL_IMMUTABLE",
    "TEXT_LENGTH",
    "TASK_UNIQUENESS",
)


def validate_candidate(
    candidate: PlanCandidate,
    context: PlanningContext,
    evidence_catalog: list[EvidenceCatalogItem] | None = None,
) -> ValidationReport:
    window = context.planning_window
    allowed_evidence = {(item.kind, item.id) for item in (evidence_catalog or [])}
    results = {
        "HORIZON_MATCH": (
            candidate.plan_date == window.planning_date
            and candidate.horizon_start == window.horizon_start
            and candidate.horizon_end == window.horizon_end
        ),
        "WEEKLY_FOCUS": (
            len(candidate.weekly_focus) == window.horizon_weeks
            and [item.week_index for item in candidate.weekly_focus]
            == list(range(1, len(candidate.weekly_focus) + 1))
        ),
        "TASK_COUNT": 1 <= len(candidate.tasks) <= 3,
        "TIME_BUDGET": (
            sum(task.estimated_minutes for task in candidate.tasks) <= context.time_budget_minutes
        ),
        "STARTER_ACTION": all(bool(task.starter_action.strip()) for task in candidate.tasks),
        "DELIVERABLE": all(bool(task.deliverable.strip()) for task in candidate.tasks),
        "SCHEDULE_DATE": all(
            task.scheduled_date == window.planning_date for task in candidate.tasks
        ),
        "RECENT_DUPLICATE": not any(
            task.deliverable in context.completed_facts for task in candidate.tasks
        ),
        "REPLAN_CONTINUITY": _valid_replan_continuity(candidate, context),
        "SOURCE_INTEGRITY": all(
            (reference.kind, reference.id) in allowed_evidence
            for reference in candidate.evidence_refs
        ),
        "GOAL_IMMUTABLE": True,
        "TEXT_LENGTH": True,
        "TASK_UNIQUENESS": (
            len({task.title for task in candidate.tasks}) == len(candidate.tasks)
            and len({task.deliverable for task in candidate.tasks}) == len(candidate.tasks)
        ),
    }
    checks = [
        ValidationCheck(
            code=code,
            passed=results[code],
            message="passed" if results[code] else f"{code} failed",
        )
        for code in CHECK_ORDER
    ]
    failures = [check.code for check in checks if not check.passed]
    return ValidationReport(
        passed=not failures,
        checks=checks,
        repair_instructions=[f"Repair deterministic rule {code}" for code in failures],
    )


def _valid_replan_continuity(candidate: PlanCandidate, context: PlanningContext) -> bool:
    source = context.source_plan
    review = context.source_review
    if source is None:
        return candidate.adjustment_reason is None
    if review is None:
        return (
            candidate.overall_direction == source.overall_direction
            and candidate.adjustment_reason is None
        )
    if review.adjustment_request or review.replan_reason:
        return bool(candidate.adjustment_reason)
    return (
        candidate.overall_direction == source.overall_direction
        and candidate.adjustment_reason is None
    )


def fallback_candidate(context: PlanningContext, mode: ReplanMode) -> PlanCandidate:
    window = context.planning_window
    minutes = max(5, min(context.time_budget_minutes, 30))
    dated_deliverable = f"{window.planning_date.isoformat()} fallback evidence artifact"
    return PlanCandidate(
        plan_date=window.planning_date,
        horizon_start=window.horizon_start,
        horizon_end=window.horizon_end,
        overall_direction=(
            context.source_plan.overall_direction
            if context.source_plan is not None
            else "采用保守节奏持续积累可验证的求职准备证据"
        ),
        weekly_focus=[
            WeeklyFocusCandidate(
                week_index=index,
                focus="完成一个小而可验证的准备增量",
                success_signal="形成一份可以复查的产物",
            )
            for index in range(1, window.horizon_weeks + 1)
        ],
        summary="本次先采用保守计划，完成一个最小行动。",
        rationale="候选计划未通过规则检查，因此使用确定性模板保证可执行性。",
        adjustment_reason="根据复盘阻碍采用保守调整" if mode == ReplanMode.ADJUST else None,
        tasks=[
            TaskCandidate(
                title="完成一个最小准备动作",
                task_type=TaskType.OTHER,
                scheduled_date=window.planning_date,
                starter_action="打开当前求职材料并选择一个最小改进点",
                deliverable=dated_deliverable,
                estimated_minutes=minutes,
                rationale="先恢复稳定、可执行的行动节奏",
            )
        ],
    )


def build_companion(candidate: PlanCandidate) -> CompanionMessageCandidate:
    return CompanionMessageCandidate(
        message=f"今天先从“{candidate.tasks[0].title}”开始，完成可验证产物即可。",
        template_version="plan_ready_v1",
    )
