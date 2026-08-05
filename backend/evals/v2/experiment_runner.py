"""Drive an Experiment's Trials through the TrialRunner.

The ExperimentRunner is a thin orchestrator: it loads the Trials already
created for an Experiment by ``EvalService.create_experiment`` (PR-2), matches
each Trial to its ``EvalCase`` by ``case_id``, marks the Experiment ``running``
and ``completed`` around the TrialRunner, and emits a compact report whose
token / tool / latency / state contents all come from real Runtime traces.

No Scores are produced -- grading is PR-4.
"""

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.database import session_transaction
from app.models.eval import EvalExperiment, EvalTrial
from app.repositories.evals import EvalRepository
from app.services.evals import EvalService
from evals.v2.collectors.outcome import RunOutcome
from evals.v2.contracts import EvalCase
from evals.v2.dataset_loader import DatasetBundle
from evals.v2.trial_runner import TrialRunner


@dataclass(frozen=True, slots=True)
class TrialSummary:
    trial_id: UUID
    case_id: str
    status: str
    run_status: str | None
    result_kind: str | None
    tokens_in: int
    tokens_out: int
    latency_ms: int
    error_code: str | None
    terminal_event_count: int
    tool_call_count: int


@dataclass(frozen=True, slots=True)
class ExperimentReport:
    experiment_id: UUID
    experiment_status: str
    trial_count: int
    trials: list[TrialSummary] = field(default_factory=list)

    @property
    def completed_trial_count(self) -> int:
        return sum(1 for trial in self.trials if trial.status == "completed")

    @property
    def any_score_generated(self) -> bool:
        # PR-3 contract: no fake scores. This is structurally guaranteed
        # because the ExperimentRunner never inserts an EvalScore row.
        return False


class ExperimentRunner:
    """Run every Trial of one Experiment and summarize real Trace facts."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings

    async def run_experiment(
        self,
        experiment_id: UUID,
        dataset: DatasetBundle,
    ) -> ExperimentReport:
        cases_by_id = {case.case_id: case for case in dataset.cases}
        summaries: list[TrialSummary] = []

        # Mark the Experiment ``running`` before executing any Trial.
        async with self._session_factory() as session:
            async with session_transaction(session):
                await EvalService(session).transition_experiment(
                    experiment_id, "running"
                )

        trial_runner = TrialRunner(
            session_factory=self._session_factory, settings=self._settings
        )
        async with self._session_factory() as session:
            trials = await EvalRepository(session).list_trials(experiment_id)
        for trial in trials:
            case = cases_by_id.get(trial.case_id)
            if case is None:
                raise RuntimeError(
                    f"trial {trial.id} references unknown case {trial.case_id}"
                )
            outcome = await trial_runner.run_trial(trial, case)
            summaries.append(_summarize(trial, outcome))

        # Mark the Experiment ``completed`` once no Trial is pending/running.
        async with self._session_factory() as session:
            async with session_transaction(session):
                await EvalService(session).transition_experiment(
                    experiment_id, "completed"
                )
                experiment = await EvalRepository(session).get_experiment(
                    experiment_id
                )
                if experiment is None:
                    raise RuntimeError(f"experiment {experiment_id} disappeared")
                status = experiment.status
        return ExperimentReport(
            experiment_id=experiment_id,
            experiment_status=status,
            trial_count=len(trials),
            trials=summaries,
        )


def _summarize(trial: EvalTrial, outcome: RunOutcome) -> TrialSummary:
    from evals.v2.collectors.outcome import terminal_event_count

    # A Trial is "completed" for reporting purposes when the Run reached a
    # legitimate terminal outcome (completed/degraded). cancelled/failed Runs
    # leave the Trial in a non-completed status. The ``trial`` ORM object may
    # be stale (TrialRunner attached the outcome from another session), so we
    # derive report status from the outcome rather than the ORM row.
    report_status = "completed" if outcome.status in {"completed", "degraded"} else (
        "cancelled" if outcome.status == "cancelled" else "failed"
    )
    return TrialSummary(
        trial_id=trial.id,
        case_id=trial.case_id,
        status=report_status,
        run_status=outcome.status,
        result_kind=outcome.result_kind,
        tokens_in=outcome.total_tokens_in,
        tokens_out=outcome.total_tokens_out,
        latency_ms=outcome.total_latency_ms,
        error_code=outcome.error_code,
        terminal_event_count=terminal_event_count(outcome),
        tool_call_count=len(outcome.tool_calls),
    )


# ``EvalExperiment`` / ``EvalCase`` are re-exported as type aliases for callers
# that build typed reports on top of ``ExperimentRunner``.
_EXPERIMENT_GUARD: type[EvalExperiment] = EvalExperiment  # noqa: F841
_CASE_GUARD: type[EvalCase] = EvalCase  # noqa: F841
