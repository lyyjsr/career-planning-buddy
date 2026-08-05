"""Deterministic history compression and conservative token estimation."""

from dataclasses import dataclass
from math import ceil

from app.schemas.agent_runs import PlanningContext, ReviewContext, TaskContext


@dataclass(frozen=True, slots=True)
class ContextCompressionResult:
    context: PlanningContext
    before_chars: int
    after_chars: int
    task_compressed_count: int
    review_compressed_count: int


def estimate_text_tokens(text: str) -> int:
    """Conservatively estimate mixed Chinese/Latin text without a Provider tokenizer."""
    if not text:
        return 0
    non_ascii = sum(ord(character) > 127 for character in text)
    ascii_chars = len(text) - non_ascii
    return non_ascii + ceil(ascii_chars / 4)


def compress_context_history(
    context: PlanningContext,
    *,
    recent_tasks_budget: int = 5,
    recent_reviews_budget: int = 2,
) -> ContextCompressionResult:
    """Compress history.

    PR-8 exposes the per-context budget as kwargs. Pre-PR-8 callers see the
    same defaults (5 tasks / 2 reviews) and identical behaviour.
    """
    before_chars = len(context.model_dump_json())
    recent_tasks = context.recent_tasks[:recent_tasks_budget]
    older_tasks = context.recent_tasks[recent_tasks_budget:]
    recent_reviews = context.recent_reviews[:recent_reviews_budget]
    older_reviews = context.recent_reviews[recent_reviews_budget:]
    task_summary = _task_summary(older_tasks)
    review_summary = _review_summary(older_reviews)
    summarized_deliverables = {task.deliverable.strip() for task in context.recent_tasks}
    completed_facts = [
        fact
        for fact in dict.fromkeys(context.completed_facts)
        if fact.strip() not in summarized_deliverables
    ][:5]
    compressed = context.model_copy(
        update={
            "recent_tasks": recent_tasks,
            "recent_reviews": recent_reviews,
            "completed_facts": completed_facts,
            "task_history_summary": task_summary,
            "review_history_summary": review_summary,
            "token_estimate": 0,
        }
    )
    token_estimate = estimate_text_tokens(compressed.model_dump_json())
    compressed = compressed.model_copy(update={"token_estimate": token_estimate})
    final_estimate = estimate_text_tokens(compressed.model_dump_json())
    if final_estimate != token_estimate:
        compressed = compressed.model_copy(update={"token_estimate": final_estimate})
    return ContextCompressionResult(
        context=compressed,
        before_chars=before_chars,
        after_chars=len(compressed.model_dump_json()),
        task_compressed_count=len(older_tasks),
        review_compressed_count=len(older_reviews),
    )


def _task_summary(tasks: list[TaskContext]) -> str | None:
    completed = list(
        dict.fromkeys(task.deliverable.strip() for task in tasks if task.state == "completed")
    )[:5]
    blockers = list(
        dict.fromkeys(
            (task.abandoned_reason_text or task.deliverable).strip()
            for task in tasks
            if task.state == "abandoned"
        )
    )[:3]
    parts: list[str] = []
    if completed:
        parts.append("更早任务已完成：" + "、".join(completed))
    if blockers:
        parts.append("主要阻碍：" + "、".join(blockers))
    return "；".join(parts) or None


def _review_summary(reviews: list[ReviewContext]) -> str | None:
    blocker_counts: dict[str, int] = {}
    adjustments: list[str] = []
    for review in reviews:
        if review.blockers and review.blockers.strip():
            blocker = review.blockers.strip()
            blocker_counts[blocker] = blocker_counts.get(blocker, 0) + 1
        if review.adjustment_request and review.adjustment_request.strip():
            adjustments.append(review.adjustment_request.strip())
    repeated = [value for value, count in blocker_counts.items() if count >= 2][:3]
    parts: list[str] = []
    if repeated:
        parts.append("重复阻碍：" + "、".join(repeated))
    unique_adjustments = list(dict.fromkeys(adjustments))[:3]
    if unique_adjustments:
        parts.append("调整模式：" + "、".join(unique_adjustments))
    return "；".join(parts) or None
