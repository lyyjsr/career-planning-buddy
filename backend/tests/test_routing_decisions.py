"""Pure-function tests for the Stage 4 routing decision table.

These pin the _after_* decisions that decide graph topology. They are
pread-at in the runtime integration tests; here we lock the boundary
behaviour so future refactors of state shape do not silently flip routing.
"""

from uuid import uuid4

from app.agent.graph import FixedPlanningGraph
from app.agent.nodes import risk_gate
from app.schemas.agent_runs import (
    IntentResult,
    ValidationCheck,
    ValidationReport,
)
from app.schemas.enums import ReplanMode, RunIntent


def _state(**kw) -> dict:
    return kw


# --- _after_risk ---
def test_after_risk_routes_high_to_safe_response() -> None:
    assert FixedPlanningGraph._after_risk(_state(risk=risk_gate("我想自杀"))) == "high"


def test_after_risk_routes_non_high_to_intent_router() -> None:
    assert FixedPlanningGraph._after_risk(_state(risk=risk_gate("今天天气不错"))) == "safe"


# --- _after_intent ---
def _intent(intent: RunIntent, missing: list[str] | None = None) -> IntentResult:
    return IntentResult(
        intent=intent,
        replan_mode=ReplanMode.INITIAL,
        confidence=1,
        missing_slots=missing or [],
        effective_goal_type=None,
        requested_horizon_weeks=None,
        requires_fresh_information=False,
        method="rule",
    )


def test_after_intent_unsupported_routes_to_clarification() -> None:
    state = _state(intent=_intent(RunIntent.UNSUPPORTED))
    assert FixedPlanningGraph._after_intent(state) == "clarification"


def test_after_intent_missing_slots_routes_to_clarification() -> None:
    state = _state(intent=_intent(RunIntent.CREATE_PLAN, missing=["goal_type"]))
    assert FixedPlanningGraph._after_intent(state) == "clarification"


def test_after_intent_ready_routes_to_context_builder() -> None:
    state = _state(intent=_intent(RunIntent.CREATE_PLAN))
    assert FixedPlanningGraph._after_intent(state) == "ready"


# --- _after_validation ---
def _validation_report(passed: bool) -> ValidationReport:
    return ValidationReport(
        passed=passed,
        checks=[ValidationCheck(code="X", passed=passed, message="m")],
        repair_instructions=[] if passed else ["Repair X"],
    )


def test_after_validation_passed_goes_to_companion() -> None:
    state = _state(validation_report=_validation_report(True))
    assert FixedPlanningGraph._after_validation(state) == "passed"


def test_after_validation_failed_without_fallback_goes_to_repair() -> None:
    state = _state(validation_report=_validation_report(False), fallback_reason=None)
    assert FixedPlanningGraph._after_validation(state) == "repair"


def test_after_validation_failed_but_already_fallback_skips_repair() -> None:
    # 关键边界：fallback_reason 已存在时即使 validator 再失败也不应再循环回 repair
    state = _state(
        validation_report=_validation_report(False),
        fallback_reason="business_repair_exhausted",
    )
    assert FixedPlanningGraph._after_validation(state) == "passed"
