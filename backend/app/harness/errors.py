"""PR-9b failure taxonomy for the Eval Harness.

Replaces free-form string literals used for ``EvalTrial.error_code`` /
``AgentRun.error_code`` / ``provider_calls.error_code`` with a single
canonical enum, plus a coarse ``FailureCategory`` classifier and three
bucket helpers consumed by ``evals/v2/stats.py``.

Architectural invariant: the Agent Runtime layer (``app.agent.errors``)
remains the source of truth for the literal ``AgentError.code`` strings
produced by the runtime. This module mirrors those literals as
``EvalFailureCode`` enum values *without* importing from
``app.agent.errors`` (the dependency direction is Eval Harness ->
normalized string -> Agent Runtime, never the reverse). When a new
runtime code lands, add it here and assign a category.
"""

from __future__ import annotations

from enum import StrEnum


class EvalFailureCode(StrEnum):
    """Canonical failure code for one Eval Trial / provider call.

    Values mirror the ``code`` strings on
    ``app.agent.errors.*`` exceptions so the recorder can persist
    ``exc.code`` directly and have it remain joinable with this enum.
    """

    # --- PROVIDER -------------------------------------------------------
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
    PROVIDER_AUTHENTICATION_FAILED = "PROVIDER_AUTHENTICATION_FAILED"
    PROVIDER_RATE_LIMITED = "PROVIDER_RATE_LIMITED"
    PROVIDER_CONFIGURATION_INVALID = "PROVIDER_CONFIGURATION_INVALID"
    TOOL_PROVIDER_UNAVAILABLE = "TOOL_PROVIDER_UNAVAILABLE"
    TOOL_ARGUMENT_INVALID = "TOOL_ARGUMENT_INVALID"
    TOOL_EXECUTION_FAILED = "TOOL_EXECUTION_FAILED"

    # --- AGENT_RUNTIME --------------------------------------------------
    AGENT_EXECUTION_FAILED = "AGENT_EXECUTION_FAILED"
    AGENT_DEADLINE_EXCEEDED = "AGENT_DEADLINE_EXCEEDED"
    AGENT_BUDGET_EXCEEDED = "AGENT_BUDGET_EXCEEDED"
    AGENT_ERROR = "AGENT_ERROR"
    STRUCTURED_OUTPUT_INVALID = "STRUCTURED_OUTPUT_INVALID"

    # --- HARNESS --------------------------------------------------------
    PROCESS_INTERRUPTED = "PROCESS_INTERRUPTED"  # EvalRunnerExecutor recovered after crash
    RUN_DEADLINE_EXCEEDED = "RUN_DEADLINE_EXCEEDED"
    RUN_NOT_COMPLETED = "RUN_NOT_COMPLETED"  # legacy fallback used by TrialRunner

    # --- PERSISTENCE ----------------------------------------------------
    PERSIST_TRANSACTION_FAILED = "PERSIST_TRANSACTION_FAILED"
    STATE_RUN_ALREADY_ACTIVE = "STATE_RUN_ALREADY_ACTIVE"

    # --- USER_ACTION ----------------------------------------------------
    USER_REQUESTED_CANCEL = "USER_REQUESTED_CANCEL"
    COOPERATIVE_CANCEL = "COOPERATIVE_CANCEL"
    RUN_CANCELLED = "RUN_CANCELLED"

    # --- CONFIG ---------------------------------------------------------
    EVAL_PROVIDER_MODE_INVALID = "EVAL_PROVIDER_MODE_INVALID"

    # --- QUALITY --------------------------------------------------------
    QUALITY_HARD_GATE_FAILED = "QUALITY_HARD_GATE_FAILED"

    UNKNOWN = "UNKNOWN"


class FailureCategory(StrEnum):
    PROVIDER = "provider"
    AGENT_RUNTIME = "agent_runtime"
    HARNESS = "harness"
    PERSISTENCE = "persistence"
    USER_ACTION = "user_action"
    CONFIG = "config"
    QUALITY = "quality"
    UNKNOWN = "unknown"


_FAILURE_CATEGORY: dict[EvalFailureCode, FailureCategory] = {
    # PROVIDER
    EvalFailureCode.PROVIDER_UNAVAILABLE: FailureCategory.PROVIDER,
    EvalFailureCode.PROVIDER_TIMEOUT: FailureCategory.PROVIDER,
    EvalFailureCode.PROVIDER_AUTHENTICATION_FAILED: FailureCategory.PROVIDER,
    EvalFailureCode.PROVIDER_RATE_LIMITED: FailureCategory.PROVIDER,
    EvalFailureCode.PROVIDER_CONFIGURATION_INVALID: FailureCategory.PROVIDER,
    EvalFailureCode.TOOL_PROVIDER_UNAVAILABLE: FailureCategory.PROVIDER,
    EvalFailureCode.TOOL_ARGUMENT_INVALID: FailureCategory.PROVIDER,
    EvalFailureCode.TOOL_EXECUTION_FAILED: FailureCategory.PROVIDER,
    # AGENT_RUNTIME
    EvalFailureCode.AGENT_EXECUTION_FAILED: FailureCategory.AGENT_RUNTIME,
    EvalFailureCode.AGENT_DEADLINE_EXCEEDED: FailureCategory.AGENT_RUNTIME,
    EvalFailureCode.AGENT_BUDGET_EXCEEDED: FailureCategory.AGENT_RUNTIME,
    EvalFailureCode.AGENT_ERROR: FailureCategory.AGENT_RUNTIME,
    EvalFailureCode.STRUCTURED_OUTPUT_INVALID: FailureCategory.AGENT_RUNTIME,
    # HARNESS
    EvalFailureCode.PROCESS_INTERRUPTED: FailureCategory.HARNESS,
    EvalFailureCode.RUN_DEADLINE_EXCEEDED: FailureCategory.HARNESS,
    EvalFailureCode.RUN_NOT_COMPLETED: FailureCategory.HARNESS,
    # PERSISTENCE
    EvalFailureCode.PERSIST_TRANSACTION_FAILED: FailureCategory.PERSISTENCE,
    EvalFailureCode.STATE_RUN_ALREADY_ACTIVE: FailureCategory.PERSISTENCE,
    # USER_ACTION
    EvalFailureCode.USER_REQUESTED_CANCEL: FailureCategory.USER_ACTION,
    EvalFailureCode.COOPERATIVE_CANCEL: FailureCategory.USER_ACTION,
    EvalFailureCode.RUN_CANCELLED: FailureCategory.USER_ACTION,
    # CONFIG
    EvalFailureCode.EVAL_PROVIDER_MODE_INVALID: FailureCategory.CONFIG,
    # QUALITY
    EvalFailureCode.QUALITY_HARD_GATE_FAILED: FailureCategory.QUALITY,
    # UNKNOWN
    EvalFailureCode.UNKNOWN: FailureCategory.UNKNOWN,
}


def category(code: str) -> FailureCategory:
    """Coarse category for an arbitrary error code string.

    Unknown codes map to ``FailureCategory.UNKNOWN`` so legacy / misspelled
    codes do not raise; the caller can decide how to surface them.
    """

    try:
        return _FAILURE_CATEGORY[EvalFailureCode(code)]
    except ValueError:
        return FailureCategory.UNKNOWN


def normalize_failure_code(code: object) -> EvalFailureCode:
    """Best-effort cast to the canonical enum.

    Used by the recorder / TrialRunner to normalize whatever string landed
    on ``AgentError.code`` (or ``exc.__class__.__name__`` in the legacy
    recorder path) into a stable enum value. Unknown inputs round-trip to
    ``EvalFailureCode.UNKNOWN``.
    """

    if code is None:
        return EvalFailureCode.UNKNOWN
    try:
        return EvalFailureCode(str(code))
    except ValueError:
        return EvalFailureCode.UNKNOWN


# Bucket helpers consumed by stats aggregation. The membership of each
# bucket is determined by ``category`` classification so a one-line
# addition to ``_FAILURE_CATEGORY`` propagates automatically.
RUNTIME_FAILURE_CATEGORIES: frozenset[FailureCategory] = frozenset({
    FailureCategory.PROVIDER,
    FailureCategory.AGENT_RUNTIME,
    FailureCategory.HARNESS,
    FailureCategory.PERSISTENCE,
})

#: CONFIG / QUALITY are independent buckets. They are tracked separately
#: from runtime_failure_count so a misconfigured experiment does not
#: inflate the model-stability denominator.
NON_RUNTIME_FAILURE_CATEGORIES: frozenset[FailureCategory] = frozenset({
    FailureCategory.CONFIG,
    FailureCategory.QUALITY,
    FailureCategory.USER_ACTION,
})

#: Concrete code sets derived from the classifier. Re-exported so callers
#: (stats tests, recorder regression tests) can iterate without recomputing.
RUNTIME_FAILURE_CODES: frozenset[str] = frozenset(
    code.value
    for code in EvalFailureCode
    if _FAILURE_CATEGORY[code] in RUNTIME_FAILURE_CATEGORIES
)
USER_CANCEL_CODES: frozenset[str] = frozenset(
    code.value
    for code in EvalFailureCode
    if _FAILURE_CATEGORY[code] == FailureCategory.USER_ACTION
)
CONFIGURATION_FAILURE_CODES: frozenset[str] = frozenset(
    code.value
    for code in EvalFailureCode
    if _FAILURE_CATEGORY[code] == FailureCategory.CONFIG
)


def is_runtime_failure(code: str) -> bool:
    return category(code) in RUNTIME_FAILURE_CATEGORIES


def is_configuration_failure(code: str) -> bool:
    return category(code) == FailureCategory.CONFIG


def is_user_cancel(code: str) -> bool:
    return category(code) == FailureCategory.USER_ACTION
