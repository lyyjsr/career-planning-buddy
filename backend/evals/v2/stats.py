"""PR-9a statistical aggregation helpers for multi-trial experiments.

Pure-Python (only stdlib) stats + per-case / per-experiment aggregations.
Zero migrations, zero new deps. Deterministic closed-form intervals.

Public surface::

    wilson_ci(successes, n)              # binomial success-rate 95% CI
    normal_ci(values)                    # normal-approx 95% CI on floats
    CIInterval / CaseStat / ExperimentStat  # frozen dataclasses
    compute_case_stats(summaries, grade_lookup)
    compute_experiment_stats(case_stats)

Aggregation semantics
---------------------
* Grouping is per ``case_id`` **and** ``variant is None``. Counterfactual
  paired variants (PR-8) are excluded from the experiment-level rollup so
  their contamination / context / tool measurements do not dilute the main
  regression pass-rate; per-variant deltas live in
  ``ExperimentReport.counterfactual_pairs``.
* "Passed" means every EvalScore row that landed for the Trial carried
  ``hard_gate=True``. No EvalScore -> None (no signal).
* "First attempt" is the Trial with ``trial_index == 0`` in the group.
  ``first_attempt_passed`` is None when that index is missing.
* Runtime failures (``error_code in runtime_failure_codes``) count toward
  the denominator of success rate but never toward the numerator, and are
  surfaced separately as ``runtime_failure_count``.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    # Avoid an import-time cycle: experiment_runner -> stats is fine; the
    # reverse direction (stats -> experiment_runner) is guarded here.
    from evals.v2.experiment_runner import TrialSummary


# 95% two-sided z-infinity (more than enough precision for 30-case datasets).
_Z_95 = 1.959963984540054

# Error codes that signal a *runtime* failure rather than a model-quality
# failure. Such trials count toward the denominator of success-rate (the
# experiment did not produce a usable output) but never the numerator.
RUNTIME_FAILURE_CODES: tuple[str, ...] = (
    "RUN_NOT_COMPLETED",
    "STATE_RUN_ALREADY_ACTIVE",
    "RUN_DEADLINE_EXCEEDED",
    "PROVIDER_UNAVAILABLE",
    "TOOL_PROVIDER_UNAVAILABLE",
)

# Error codes that mean the user / harness aborted the Trial — not counted
# as a runtime failure either (separate bucket, currently informational only).
USER_CANCEL_CODES: tuple[str, ...] = (
    "USER_REQUESTED_CANCEL",
    "COOPERATIVE_CANCEL",
    "RUN_CANCELLED",
)


# ---------------------------------------------------------------------------
# Confidence intervals
# ---------------------------------------------------------------------------


def wilson_ci(successes: int, n: int, z: float = _Z_95) -> tuple[float, float]:
    """Wilson score 95% CI for a binomial success rate.

    Returns ``(low, high)`` clamped to ``[0, 1]``. ``n <= 0`` -> ``(0.0, 0.0)``.
    Closed-form, deterministic, no resampling required.
    """

    if n <= 0:
        return 0.0, 0.0
    p = successes / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, center - half), min(1.0, center + half)


def normal_ci(values: list[float], z: float = _Z_95) -> tuple[float, float]:
    """Normal-approximation 95% CI (population SD) for a list of floats.

    Returns ``(mean - z*sd, mean + z*sd)``. ``n == 0`` -> ``(0.0, 0.0)``;
    ``n == 1`` -> ``(mean, mean)`` (zero width, no variance info).
    """

    n = len(values)
    if n == 0:
        return 0.0, 0.0
    mean = sum(values) / n
    if n < 2:
        return mean, mean
    var = sum((v - mean) ** 2 for v in values) / n  # population variance
    sd = math.sqrt(var)
    return mean - z * sd, mean + z * sd


def _pop_mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CIInterval:
    low: float
    high: float


@dataclass(frozen=True, slots=True)
class CaseStat:
    """Aggregated stats for one ``(case_id, variant=None)`` group."""

    case_id: str
    trial_count: int
    completed_count: int
    hard_gate_passed_count: int
    runtime_failure_count: int
    first_attempt_passed: bool | None
    pass_at_n: bool | None
    pass_all_n: bool | None
    success_rate: float
    success_rate_ci: CIInterval
    mean_tokens_in: float
    mean_tokens_out: float
    mean_latency_ms: float
    tokens_in_ci: CIInterval
    tokens_out_ci: CIInterval
    latency_ci: CIInterval


@dataclass(frozen=True, slots=True)
class ExperimentStat:
    """Experiment-level aggregate computed from CaseStat rows.

    Built by ``compute_experiment_stats`` — never hand-constructed.
    """

    case_count: int
    trial_count: int
    completed_count: int
    hard_gate_passed_count: int
    runtime_failure_count: int
    first_attempt_success_rate: float
    first_attempt_success_rate_ci: CIInterval
    pass_at_n_rate: float
    pass_all_n_rate: float
    success_rate: float
    success_rate_ci: CIInterval


# ---------------------------------------------------------------------------
# Aggregations
# ---------------------------------------------------------------------------

#: ``grade_lookup`` value type: list of (grader_name, score, hard_gate).
GradeRow = tuple[str, float, bool]


def _trial_passed(rows: list[GradeRow]) -> bool | None:
    """Three-valued trial-passed verdict.

    * ``True`` when every EvalScore carried ``hard_gate=True`` (>=1 row).
    * ``False`` when any row carried ``hard_gate=False``.
    * ``None`` when no scores were persisted (no signal).
    """

    if not rows:
        return None
    return all(hard_gate for _, _, hard_gate in rows)


def compute_case_stats(
    summaries: list[TrialSummary],
    grade_lookup: Mapping[UUID, list[GradeRow]],
    *,
    runtime_failure_codes: tuple[str, ...] = RUNTIME_FAILURE_CODES,
) -> dict[str, CaseStat]:
    """Group ``TrialSummary`` rows by ``case_id`` (variant is None only).

    Variant-tagged trials belong to a counterfactual pair and are excluded
    from this aggregation. Their per-variant deltas live in
    ``ExperimentReport.counterfactual_pairs``.
    """

    grouped: dict[str, list[TrialSummary]] = {}
    for summary in summaries:
        if summary.variant is not None:
            continue
        grouped.setdefault(summary.case_id, []).append(summary)

    case_stats: dict[str, CaseStat] = {}
    for case_id, group in grouped.items():
        trial_count = len(group)
        # Pass verdicts per trial (None=unknown).
        verdicts: list[bool | None] = []
        for s in group:
            verdicts.append(_trial_passed(grade_lookup.get(s.trial_id, [])))

        hard_gate_passed_count = sum(1 for v in verdicts if v is True)
        completed_count = sum(
            1 for s in group if s.status == "completed"
        )
        runtime_failure_count = sum(
            1
            for s in group
            if s.error_code is not None
            and s.error_code in runtime_failure_codes
        )

        first_attempt = next(
            (s for s in group if s.trial_index == 0), None
        )
        if first_attempt is None:
            first_attempt_passed: bool | None = None
        else:
            first_attempt_passed = _trial_passed(
                grade_lookup.get(first_attempt.trial_id, [])
            )

        pass_at_n: bool | None
        pass_all_n: bool | None
        if trial_count == 0:
            pass_at_n = None
            pass_all_n = None
        else:
            pass_at_n = hard_gate_passed_count >= 1
            pass_all_n = hard_gate_passed_count == trial_count

        denom = max(completed_count, 1)
        success_rate = hard_gate_passed_count / denom
        low, high = wilson_ci(hard_gate_passed_count, completed_count)

        tokens_in_values = [float(s.tokens_in) for s in group]
        tokens_out_values = [float(s.tokens_out) for s in group]
        latency_values = [float(s.latency_ms) for s in group]

        ti_low, ti_high = normal_ci(tokens_in_values)
        to_low, to_high = normal_ci(tokens_out_values)
        lat_low, lat_high = normal_ci(latency_values)

        case_stats[case_id] = CaseStat(
            case_id=case_id,
            trial_count=trial_count,
            completed_count=completed_count,
            hard_gate_passed_count=hard_gate_passed_count,
            runtime_failure_count=runtime_failure_count,
            first_attempt_passed=first_attempt_passed,
            pass_at_n=pass_at_n,
            pass_all_n=pass_all_n,
            success_rate=success_rate,
            success_rate_ci=CIInterval(low=low, high=high),
            mean_tokens_in=_pop_mean(tokens_in_values),
            mean_tokens_out=_pop_mean(tokens_out_values),
            mean_latency_ms=_pop_mean(latency_values),
            tokens_in_ci=CIInterval(low=ti_low, high=ti_high),
            tokens_out_ci=CIInterval(low=to_low, high=to_high),
            latency_ci=CIInterval(low=lat_low, high=lat_high),
        )

    return case_stats


def compute_experiment_stats(
    case_stats: Mapping[str, CaseStat],
) -> ExperimentStat:
    """Roll per-case stats up to experiment-level totals + 95% CIs."""

    rows = list(case_stats.values())
    case_count = len(rows)
    if case_count == 0:
        return ExperimentStat(
            case_count=0,
            trial_count=0,
            completed_count=0,
            hard_gate_passed_count=0,
            runtime_failure_count=0,
            first_attempt_success_rate=0.0,
            first_attempt_success_rate_ci=CIInterval(low=0.0, high=0.0),
            pass_at_n_rate=0.0,
            pass_all_n_rate=0.0,
            success_rate=0.0,
            success_rate_ci=CIInterval(low=0.0, high=0.0),
        )

    trial_count = sum(c.trial_count for c in rows)
    completed_count = sum(c.completed_count for c in rows)
    hard_gate_passed_count = sum(c.hard_gate_passed_count for c in rows)
    runtime_failure_count = sum(c.runtime_failure_count for c in rows)

    first_attempts = [c for c in rows if c.first_attempt_passed is not None]
    first_attempt_successes = sum(
        1 for c in first_attempts if c.first_attempt_passed is True
    )
    first_attempt_total = len(first_attempts)
    first_attempt_rate = (
        first_attempt_successes / first_attempt_total
        if first_attempt_total > 0
        else 0.0
    )
    fa_low, fa_high = wilson_ci(first_attempt_successes, first_attempt_total)

    pass_at_n_cases = sum(1 for c in rows if c.pass_at_n is True)
    pass_all_n_cases = sum(1 for c in rows if c.pass_all_n is True)

    success_rate = (
        hard_gate_passed_count / completed_count if completed_count else 0.0
    )
    sr_low, sr_high = wilson_ci(hard_gate_passed_count, completed_count)

    return ExperimentStat(
        case_count=case_count,
        trial_count=trial_count,
        completed_count=completed_count,
        hard_gate_passed_count=hard_gate_passed_count,
        runtime_failure_count=runtime_failure_count,
        first_attempt_success_rate=first_attempt_rate,
        first_attempt_success_rate_ci=CIInterval(low=fa_low, high=fa_high),
        pass_at_n_rate=pass_at_n_cases / case_count,
        pass_all_n_rate=pass_all_n_cases / case_count,
        success_rate=success_rate,
        success_rate_ci=CIInterval(low=sr_low, high=sr_high),
    )
