"""Model-domain deterministic Graders.

Spec gate (PR-4): structured-output / format-repair-count / evidence-
visibility are hard gates. Token-usage-nonzero is a quality signal
(``hard_gate=False``) that future runs can grow into a hard gate once the
price/quality baseline is frozen.

The evidence-visibility check reuses ``evidence_refs_are_visible`` from
``app.harness.evidence`` indirectly, by relying on the collector to emit a
``plan_projection`` that carries both ``evidence_refs`` and ``visible_refs``
as already-validated sets. The Model grader stays pure-python over the
projection.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from evals.v2.collectors.outcome import RunOutcome
from evals.v2.contracts import GradeResult
from evals.v2.graders.base import AuthorizedView, EvidenceKind, as_dict_list

if TYPE_CHECKING:
    from evals.v2.contracts import EvalCase

GRADER_NAME_PREFIX = "model"
GRADER_VERSION = "v1"
ALLOWED_KINDS = frozenset({
    EvidenceKind.TOOL_CALL_PROJECTION,
    EvidenceKind.EVIDENCE_VISIBLE_REFS,
    EvidenceKind.RUN_METRICS,
    EvidenceKind.REPAIR_SIGNAL,
})


def _boolean_grade(
    *, name: str, passed: bool, actual: object, expected: object,
    evidence_ids: list[UUID], rationale: str,
) -> GradeResult:
    return GradeResult(
        grader_name=f"{GRADER_NAME_PREFIX}.{name}",
        grader_version=GRADER_VERSION,
        domain="model",
        metric_type="boolean",
        passed=passed, hard_gate=True,
        evidence_item_ids=evidence_ids,
        evidence={"actual": actual, "expected": expected, "subgrader": name},
        rationale=rationale,
    )


def _numeric_grade(
    *, name: str, score: float, threshold: float,
    evidence_ids: list[UUID], rationale: str,
) -> GradeResult:
    return GradeResult(
        grader_name=f"{GRADER_NAME_PREFIX}.{name}",
        grader_version=GRADER_VERSION,
        domain="model",
        metric_type="numeric",
        score=score, threshold=threshold, hard_gate=False,
        evidence_item_ids=evidence_ids,
        evidence={"actual": score, "expected": f">= {threshold}", "subgrader": name},
        rationale=rationale,
    )


def _not_applicable(name: str, evidence_ids: list[UUID], rationale: str) -> GradeResult:
    return GradeResult(
        grader_name=f"{GRADER_NAME_PREFIX}.{name}",
        grader_version=GRADER_VERSION,
        domain="model",
        metric_type="categorical",
        categorical_value="not_applicable", hard_gate=False,
        evidence_item_ids=evidence_ids,
        evidence={"actual": None, "expected": None, "subgrader": name, "reason": "na"},
        rationale=rationale,
    )


async def grade(outcome: RunOutcome, view: AuthorizedView, expected: EvalCase) -> list[GradeResult]:
    del expected
    metrics = view.first(EvidenceKind.RUN_METRICS)
    metrics_id = metrics.id if metrics is not None else None
    repair = view.first(EvidenceKind.REPAIR_SIGNAL)
    repair_id = repair.id if repair is not None else None
    visible = view.first(EvidenceKind.EVIDENCE_VISIBLE_REFS)
    visible_id = visible.id if visible is not None else None

    results: list[GradeResult] = []

    # 1. structured_output -- completed ⇒ has plan; degraded ⇒ one of the
    #    known degraded result_kinds with appropriate event emitted.
    if outcome.status == "completed":
        structured_ok = outcome.final_plan_id is not None and outcome.plan is not None
        structured_expected = "final_plan_id present + plan projection present"
    elif outcome.status == "degraded":
        seen = {e.get("event_type") for e in outcome.events}
        structured_ok = outcome.result_kind in {"clarification", "safe_response"} and (
            "clarification.requested" in seen or "run.degraded" in seen
        )
        structured_expected = (
            "result_kind in {clarification,safe_response} "
            "+ clarification.requested or run.degraded event"
        )
    elif outcome.status in {"failed", "cancelled"}:
        structured_ok = True
        structured_expected = "no structured-output expectation on failed/cancelled runs"
    else:
        structured_ok = False
        structured_expected = "unknown status"
    results.append(_boolean_grade(
        name="structured_output",
        passed=structured_ok,
        actual={"status": outcome.status, "result_kind": outcome.result_kind,
                "has_plan": outcome.plan is not None},
        expected=structured_expected,
        evidence_ids=[metrics_id] if metrics_id else [],
        rationale="model output must satisfy the structural contract for the run terminal",
    ))

    # 2. format_repair_count -- ≤1 format repair.
    repair_raw = repair.projection.get("format_repair_attempts", 0) if repair else 0
    repair_count = int(repair_raw) if isinstance(repair_raw, (int, float)) else 0
    if outcome.status == "completed":
        results.append(_boolean_grade(
            name="format_repair_count",
            passed=repair_count <= 1,
            actual=repair_count, expected="<= 1",
            evidence_ids=[repair_id] if repair_id else [],
            rationale="model output may fix structure at most once before fallback",
        ))
    else:
        results.append(_not_applicable(
            "format_repair_count",
            [repair_id] if repair_id else [],
            "non-completed runs do not exercise the format-repair path",
        ))

    # 3. evidence_visibility -- plan evidence_refs must be a subset of the
    #    visible_refs evidence captured by the collector. This is the PR-1
    #    invariant that the Model grader pins at the evaluation layer.
    plan_projection = outcome.plan or {}
    plan_refs_raw: list[dict[str, object]] = as_dict_list(
        plan_projection.get("evidence_refs", []) or []
    )
    if plan_refs_raw or outcome.status == "completed":
        if visible is None:
            evidence_ok = False
            actual_refs: list[object] = list(plan_refs_raw)
            visible_refs_str: object = "<missing visible_refs evidence>"
        else:
            visible_refs_raw = as_dict_list(visible.projection.get("visible_refs", []) or [])
            plan_ref_set = {
                f"{r.get('kind')}:{r.get('id')}"
                for r in plan_refs_raw if isinstance(r, dict)
            }
            visible_ref_set = {
                f"{r.get('kind')}:{r.get('id')}"
                for r in visible_refs_raw if isinstance(r, dict)
            }
            outside = plan_ref_set - visible_ref_set
            evidence_ok = not outside
            sorted_outside = sorted(outside)
            actual_refs = list(sorted_outside) if sorted_outside else list(plan_refs_raw)
            visible_refs_str = sorted(visible_ref_set)
        results.append(_boolean_grade(
            name="evidence_visibility",
            passed=evidence_ok,
            actual={"plan_refs_outside_visibility": actual_refs if not evidence_ok else []},
            expected=f"refs in visible {visible_refs_str}",
            evidence_ids=[visible_id] if visible_id else [],
            rationale="every Plan evidence_ref must be present in the call's visible_refs window",
        ))
    else:
        results.append(_not_applicable(
            "evidence_visibility", [],
            "no plan projection to verify",
        ))

    # 4. token_usage_nonzero -- quality (soft). Mock provider should still emit >0 tokens.
    total = outcome.total_tokens_in + outcome.total_tokens_out
    results.append(_numeric_grade(
        name="token_usage_nonzero",
        score=float(total),
        threshold=0.0,
        evidence_ids=[metrics_id] if metrics_id else [],
        rationale="tokens should be non-zero on any real model interaction",
    ))

    return results
