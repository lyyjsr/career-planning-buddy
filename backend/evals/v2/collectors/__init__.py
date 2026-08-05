"""Outcome collectors for the V2 TrialRunner.

These are thin read-only projections over the persisted Runtime trace. They
never mutate Run/Plan/Step/Event state and contain no Runtime logic.

PR-3 ships ``outcome`` only. ``trace`` and ``evidence`` collectors land with
the grader evidence-authorization layer in PR-4; the package is intentionally
not re-exporting them yet.
"""

from .outcome import (
    RunOutcome,
    collect_outcome,
    terminal_event_count,
    terminal_events,
)

__all__ = ["RunOutcome", "collect_outcome", "terminal_event_count", "terminal_events"]
