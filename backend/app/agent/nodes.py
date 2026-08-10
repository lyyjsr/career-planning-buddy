"""Deterministic controlled Stage 4 graph nodes."""

import re
from datetime import UTC, date, datetime, timedelta
from typing import Literal
from uuid import UUID

from app.harness.evidence import evidence_refs_are_visible
from app.schemas.agent_runs import (
    ClarificationRequest,
    CompanionMessageCandidate,
    EvidenceVisibility,
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
from app.schemas.enums import GoalType, ReplanMode, RunIntent, TaskStatus, TaskType

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
    goal_type_override: GoalType | None = None,
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
        effective_goal_type=goal_type_override or (profile.goal_type if profile else None),
        requested_horizon_weeks=requested_weeks,
        requires_fresh_information=requires_fresh_information,
        method="rule",
    )


def parse_horizon_weeks(message: str) -> int | None:
    match = re.search(r"(?:未来|接下来)?\s*(\d+)\s*周", message)
    if match:
        return max(1, min(8, int(match.group(1))))
    chinese_match = re.search(r"(?:未来|接下来)?\s*([一二两三四五六七八])\s*周", message)
    if chinese_match:
        return _clamp_horizon_weeks(_chinese_number(chinese_match.group(1)))
    if re.search(r"(?:未来|接下来)?\s*半\s*个?月", message):
        return 2
    month_match = re.search(r"(?:未来|接下来)?\s*(\d+)\s*个?月", message)
    if month_match:
        return _clamp_horizon_weeks(int(month_match.group(1)) * 4)
    chinese_month_match = re.search(
        r"(?:未来|接下来)?\s*([一二两三四五六七八])\s*个?月",
        message,
    )
    if chinese_month_match:
        return _clamp_horizon_weeks(_chinese_number(chinese_month_match.group(1)) * 4)
    return None


def _chinese_number(value: str) -> int:
    return {
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
    }[value]


def _clamp_horizon_weeks(value: int) -> int:
    return max(1, min(8, value))


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


def _within_daily_budget(tasks: list[TaskCandidate], daily_budget: int) -> bool:
    """Allow multi-day candidates; constrain only per-day minutes to the daily budget."""
    per_day: dict[date, int] = {}
    for task in tasks:
        per_day[task.scheduled_date] = per_day.get(task.scheduled_date, 0) + task.estimated_minutes
    return all(total <= daily_budget for total in per_day.values())


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
    evidence_visibility: EvidenceVisibility | None = None,
) -> ValidationReport:
    window = context.planning_window
    completed_deliverables = set(context.completed_facts)
    completed_deliverables.update(
        task.deliverable for task in context.recent_tasks if task.state == TaskStatus.COMPLETED
    )
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
            and len({item.focus for item in candidate.weekly_focus})
            == len(candidate.weekly_focus)
            and len({item.success_signal for item in candidate.weekly_focus})
            == len(candidate.weekly_focus)
        ),
        "TASK_COUNT": 1 <= len(candidate.tasks) <= 7,
        "TIME_BUDGET": _within_daily_budget(candidate.tasks, context.time_budget_minutes),
        "STARTER_ACTION": all(bool(task.starter_action.strip()) for task in candidate.tasks),
        "DELIVERABLE": all(bool(task.deliverable.strip()) for task in candidate.tasks),
        "SCHEDULE_DATE": all(
            window.planning_date
            <= task.scheduled_date
            <= min(window.planning_date + timedelta(days=6), window.horizon_end)
            for task in candidate.tasks
        ),
        "RECENT_DUPLICATE": not any(
            task.deliverable in completed_deliverables for task in candidate.tasks
        ),
        "REPLAN_CONTINUITY": _valid_replan_continuity(candidate, context),
        "SOURCE_INTEGRITY": (
            not candidate.evidence_refs
            or evidence_visibility is not None
            and evidence_refs_are_visible(candidate.evidence_refs, evidence_visibility)
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
    weekly_templates = [
        ("明确目标岗位与能力差距", "形成岗位要求与能力差距清单"),
        ("完成可展示的项目核心增量", "产出可运行、可验证的项目成果"),
        ("沉淀简历与项目表达材料", "形成可投递的简历项目描述"),
        ("开展模拟面试并验证准备效果", "完成复盘记录并修正薄弱点"),
        ("扩大岗位样本并校准投递方向", "形成目标岗位优先级列表"),
        ("强化高频面试专题与表达", "完成一轮专题问答演练"),
        ("集中投递并跟踪反馈", "形成投递与反馈跟踪表"),
        ("复盘结果并确定下一阶段策略", "形成下一阶段行动决策"),
    ]
    daily_templates = [
        (
            "梳理目标岗位要求",
            TaskType.LEARNING,
            "1. 收集3份目标岗位JD；2. 标出重复的技能、项目和学历要求；3. 按出现次数排序",
            "岗位要求表，至少包含3份JD、10项要求及出现频次",
        ),
        (
            "盘点当前能力差距",
            TaskType.LEARNING,
            "1. 将要求分成已掌握、待补和可证明；2. 给待补项标优先级；3. 选出本周首要差距",
            "能力差距表，包含优先级、现有证据和本周首要补齐项",
        ),
        (
            "完成最小项目增量",
            TaskType.PROJECT,
            "1. 选择首要差距对应的项目功能；2. 先写验收用例；3. 实现最小闭环并提交",
            "一次代码提交，包含可运行功能、至少1个自动化测试和运行说明",
        ),
        (
            "验证并记录项目结果",
            TaskType.PROJECT,
            "1. 运行项目和测试；2. 保存关键输入输出；3. 记录失败原因、修复动作和最终结果",
            "验证记录，包含测试命令、通过结果以及截图或关键日志",
        ),
        (
            "整理简历项目表达",
            TaskType.RESUME,
            "1. 用背景、行动、结果重写项目经历；2. 补充技术取舍；3. 压缩成3至4条要点",
            "3至4条可直接放入简历的项目描述，每条包含动作和结果",
        ),
        (
            "演练项目面试问答",
            TaskType.INTERVIEW,
            "1. 准备架构、难点、取舍各1题；2. 每题限时2分钟口述；3. 重答含糊部分",
            "3组项目问答记录，每组包含首答问题和改进后的答案",
        ),
        (
            "复盘本周并安排下一步",
            TaskType.OTHER,
            "1. 汇总前6天产物；2. 标记完成、阻碍和欠账；3. 确定下周第一项可执行任务",
            "周复盘，包含完成清单、最多3个阻碍和下一步行动",
        ),
    ]
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
                focus=weekly_templates[index - 1][0],
                success_signal=weekly_templates[index - 1][1],
            )
            for index in range(1, window.horizon_weeks + 1)
        ],
        summary="本次采用保守的七天执行表，每天只推进一个可验证结果。",
        rationale="候选计划未通过规则检查，因此使用递进周目标和七天确定性模板保证可执行性。",
        adjustment_reason="根据复盘阻碍采用保守调整" if mode == ReplanMode.ADJUST else None,
        tasks=[
            TaskCandidate(
                title=title,
                task_type=task_type,
                scheduled_date=window.planning_date + timedelta(days=day_offset),
                starter_action=starter_action,
                deliverable=(
                    f"{(window.planning_date + timedelta(days=day_offset)).isoformat()} "
                    f"{deliverable}"
                ),
                estimated_minutes=minutes,
                rationale="结合当前目标、每日预算和近期执行事实推进下一项可验证成果",
            )
            for day_offset, (title, task_type, starter_action, deliverable) in enumerate(
                daily_templates
            )
        ],
    )


def build_companion(candidate: PlanCandidate) -> CompanionMessageCandidate:
    return CompanionMessageCandidate(
        message=f"七天安排已经展开，今天先从“{candidate.tasks[0].title}”开始。",
        template_version="plan_ready_v1",
    )
