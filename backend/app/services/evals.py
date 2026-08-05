"""Use cases and legal state transitions for the Eval V2 control plane."""

from datetime import UTC, datetime
from http import HTTPStatus
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import session_transaction
from app.core.exceptions import AppError
from app.models.eval import EvalEvidenceItem, EvalExperiment, EvalScore, EvalTrial
from app.repositories.agent_runs import AgentRunRepository
from app.repositories.evals import EvalRepository
from evals.v2.collectors.evidence import collect_evidence
from evals.v2.collectors.outcome import collect_outcome
from evals.v2.contracts import (
    EvalCase,
    ExperimentCreate,
    GradeResult,
    canonical_sha256,
)
from evals.v2.dataset_loader import DatasetBundle
from evals.v2.graders.base import EvidenceItem
from evals.v2.graders.registry import grade_all

if TYPE_CHECKING:
    from evals.v2.experiment_runner import ExperimentReport

EXPERIMENT_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"running", "cancelled"},
    "running": {"completed", "failed", "cancelled"},
    "completed": set(),
    "failed": set(),
    "cancelled": set(),
}


class EvalService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._evals = EvalRepository(session)

    async def create_experiment(
        self,
        *,
        dataset: DatasetBundle,
        config: ExperimentCreate,
        run_type: str = "evaluation",
    ) -> tuple[EvalExperiment, list[EvalTrial]]:
        manifest = dataset.manifest
        if (
            config.dataset_id != manifest.dataset_id
            or config.dataset_version != manifest.dataset_version
            or config.dataset_hash != manifest.source_sha256
        ):
            raise AppError(
                code="EVAL_DATASET_VERSION_MISMATCH",
                message="Experiment dataset identity/hash does not match the loaded manifest",
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            )
        if run_type not in {
            "evaluation",
            "fixture_replay",
            "live_rerun",
            "candidate_backtest",
        }:
            raise AppError(
                code="EVAL_RUN_TYPE_INVALID",
                message="Eval Trial run_type is invalid",
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            )
        frozen_hash = canonical_sha256(config.frozen_config())
        async with session_transaction(self._session):
            if config.baseline_experiment_id is not None:
                baseline = await self._evals.get_experiment(config.baseline_experiment_id)
                if baseline is None:
                    raise AppError(
                        code="EVAL_BASELINE_NOT_FOUND",
                        message="Baseline Experiment was not found",
                        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                    )
                if baseline.variant_role != "baseline":
                    raise AppError(
                        code="EVAL_BASELINE_ROLE_INVALID",
                        message="Referenced Experiment is not a baseline",
                        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                    )
                if (baseline.dataset_id, baseline.dataset_version) != (
                    config.dataset_id,
                    config.dataset_version,
                ):
                    raise AppError(
                        code="EVAL_BASELINE_DATASET_MISMATCH",
                        message="Candidate and Baseline must use the same versioned dataset",
                        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                    )
            experiment = EvalExperiment(
                id=config.experiment_id,
                dataset_id=config.dataset_id,
                dataset_version=config.dataset_version,
                dataset_hash=config.dataset_hash,
                git_commit=config.git_commit,
                graph_version=config.graph_version,
                prompt_version=config.prompt_version,
                model_version=config.model_version,
                tool_version=config.tool_version,
                context_version=config.context_version,
                memory_version=config.memory_version,
                frozen_config_hash=frozen_hash,
                execution_mode=config.execution_mode,
                variant_role=config.variant_role,
                baseline_experiment_id=config.baseline_experiment_id,
                trial_count=config.trial_count,
                status="draft",
            )
            await self._evals.create_experiment(experiment)
            trials = [
                EvalTrial(
                    experiment_id=experiment.id,
                    case_id=case.case_id,
                    case_fixture_hash=case.fixture_hash,
                    trial_index=trial_index,
                    seed=_trial_seed(case.fixture_hash, trial_index),
                    run_type=run_type,
                    status="pending",
                )
                for case in dataset.cases
                for trial_index in range(config.trial_count)
            ]
            await self._evals.create_trials(trials)
        return experiment, trials

    async def transition_experiment(
        self, experiment_id: UUID, target_status: str
    ) -> EvalExperiment:
        async with session_transaction(self._session):
            experiment = await self._evals.get_experiment(experiment_id, for_update=True)
            if experiment is None:
                raise AppError(
                    code="EVAL_EXPERIMENT_NOT_FOUND",
                    message="Eval Experiment was not found",
                    status_code=HTTPStatus.NOT_FOUND,
                )
            if target_status not in EXPERIMENT_TRANSITIONS[experiment.status]:
                raise AppError(
                    code="EVAL_EXPERIMENT_TRANSITION_INVALID",
                    message=f"Illegal Experiment transition {experiment.status} -> {target_status}",
                    status_code=HTTPStatus.CONFLICT,
                )
            now = datetime.now(UTC)
            if target_status == "running":
                if self._frozen_hash(experiment) != experiment.frozen_config_hash:
                    raise AppError(
                        code="EVAL_EXPERIMENT_CONFIG_CHANGED",
                        message="Experiment frozen configuration hash no longer matches",
                        status_code=HTTPStatus.CONFLICT,
                    )
                experiment.started_at = now
            if target_status == "completed":
                remaining = await self._evals.count_nonterminal_trials(experiment.id)
                if remaining:
                    raise AppError(
                        code="EVAL_EXPERIMENT_TRIALS_INCOMPLETE",
                        message="Experiment cannot complete while Trials are pending or running",
                        status_code=HTTPStatus.CONFLICT,
                    )
            if target_status in {"completed", "failed", "cancelled"}:
                experiment.finished_at = now
            experiment.status = target_status
            await self._session.flush()
            return experiment

    async def add_grade(self, trial_id: UUID, result: GradeResult) -> EvalScore:
        async with session_transaction(self._session):
            trial = await self._evals.get_trial(trial_id, for_update=True)
            if trial is None:
                raise AppError(
                    code="EVAL_TRIAL_NOT_FOUND",
                    message="Eval Trial was not found",
                    status_code=HTTPStatus.NOT_FOUND,
                )
            if trial.status != "completed" or trial.run_id is None:
                raise AppError(
                    code="EVAL_TRIAL_NOT_GRADEABLE",
                    message="Only a completed Trial backed by a real Agent Run can be graded",
                    status_code=HTTPStatus.CONFLICT,
                )
            score = EvalScore(
                trial_id=trial.id,
                grader_name=result.grader_name,
                grader_version=result.grader_version,
                domain=result.domain,
                metric_type=result.metric_type,
                score=result.score,
                passed=result.passed,
                categorical_value=result.categorical_value,
                hard_gate=result.hard_gate,
                threshold=result.threshold,
                evidence_item_ids=[str(item_id) for item_id in result.evidence_item_ids],
                evidence_json=result.evidence,
                rationale=result.rationale,
            )
            return await self._evals.create_score(score)

    async def attach_evidence(
        self, trial_id: UUID, items: list[EvidenceItem]
    ) -> list[EvalEvidenceItem]:
        """Persist a fresh evidence catalog for one Trial.

        Pre-existing rows for this Trial are deleted first so the new set's
        ids (and therefore the scores' ``evidence_item_ids``) reflect the
        current projection. If a caller tries to attach evidence to a Trial
        that hasn't been marked ``completed`` with a run_id, the rows would
        be unreachable by graders anyway -- but we accept the call here so
        that ``collect_evidence`` plus ``attach_evidence`` can run before
        grading, mirroring the TrialRunner's own ``attach_trial_outcome``
        pattern.
        """

        async with session_transaction(self._session):
            await self._evals.delete_evidence_for_trial(trial_id)
            rows = [
                EvalEvidenceItem(
                    trial_id=trial_id,
                    kind=item.kind.value,
                    source_type=item.source_type,
                    source_id=item.source_id,
                    content_hash=item.content_hash,
                    projection_json=item.projection,
                    sensitivity=item.sensitivity,
                )
                for item in items
            ]
            return await self._evals.create_evidence_items(rows)

    async def grade_trial(
        self,
        trial_id: UUID,
        case: EvalCase,
    ) -> list[GradeResult]:
        """Collect evidence and run every registered Grader for one Trial.

        Steps:
        1. Load the Trial; require ``completed`` + run_id (same gate as
           ``add_grade``: a non-completed Trial cannot be graded).
        2. Re-read the runtime Run + outcome from PostgreSQL (the Trial's
           ``outcome_snapshot_json`` is informational; for grading we want
           the freshest Plan/Tasks/Step/Event rows to construct the
           projected catalog).
        3. ``collect_evidence`` -> ``EvidenceItem`` list.
        4. Persist them via ``attach_evidence`` (replaces any stale rows).
        5. ``grade_all`` (Registry) -> ``GradeResult`` list, persisted via
           ``add_grade`` per row.

        Returns the list of ``GradeResult`` objects. DB-level score uniqueness
        on (trial_id, grader_name, grader_version) prevents silent re-grading;
        callers that want to re-grade after content change must first clear
        scores at the Repository layer.
        """

        async with session_transaction(self._session):
            trial = await self._evals.get_trial(trial_id, for_update=True)
            if trial is None:
                raise AppError(
                    code="EVAL_TRIAL_NOT_FOUND",
                    message="Eval Trial was not found",
                    status_code=HTTPStatus.NOT_FOUND,
                )
            if trial.status != "completed" or trial.run_id is None:
                raise AppError(
                    code="EVAL_TRIAL_NOT_GRADEABLE",
                    message="Only a completed Trial backed by a real Agent Run can be graded",
                    status_code=HTTPStatus.CONFLICT,
                )
            run = await AgentRunRepository(self._session).get_by_id(trial.run_id)
            if run is None:
                raise AppError(
                    code="EVAL_TRIAL_NOT_GRADEABLE",
                    message="the Trial's Agent Run was not found",
                    status_code=HTTPStatus.CONFLICT,
                )
            user_id = run.user_id
            # Outcome snapshot is recomputed in-session so the evidence rows
            # reflect the freshest Plan/Task/Step state rather than the frozen
            # json dropped into the Trial row at execute time.
            outcome = await collect_outcome(self._session, run, user_id=user_id)
            items = await collect_evidence(
                self._session,
                trial_id=trial_id,
                run=run,
                outcome=outcome,
                case=case,
            )
            # Persist evidence inline (NOT via attach_evidence, which opens
            # its own transaction and would conflict with this one). The
            # delete+create pair is identical to attach_evidence's body.
            await self._evals.delete_evidence_for_trial(trial_id)
            rows = [
                EvalEvidenceItem(
                    trial_id=trial_id,
                    kind=item.kind.value,
                    source_type=item.source_type,
                    source_id=item.source_id,
                    content_hash=item.content_hash,
                    projection_json=item.projection,
                    sensitivity=item.sensitivity,
                )
                for item in items
            ]
            await self._evals.create_evidence_items(rows)
            results = await grade_all(
                trial_id=trial_id,
                outcome=outcome,
                evidence_items=items,
                expected=case,
            )
            for result in results:
                try:
                    await self.add_grade(trial_id, result)
                except IntegrityError as exc:
                    raise AppError(
                        code="EVAL_SCORE_ALREADY_GRADED",
                        message="Trial has already been graded for this grader/version.",
                        status_code=HTTPStatus.CONFLICT,
                    ) from exc
            return results

    async def build_report(
        self,
        experiment_id: UUID,
        dataset: DatasetBundle,
    ) -> "ExperimentReport":
        """Reconstruct an ``ExperimentReport`` from DB state without re-running.

        Used by the HTTP GET report endpoint (and any future CLI ``--report``).
        Reads ``EvalExperiment`` + ``EvalTrial`` rows + ``EvalScore`` rows for
        every completed Trial and aggregates them into the same frozen
        ``ExperimentReport`` shape that
        ``ExperimentRunner.run_experiment_and_grade`` returns.
        """

        from evals.v2.experiment_runner import ExperimentReport, TrialSummary

        async with session_transaction(self._session):
            experiment = await self._evals.get_experiment(experiment_id)
            if experiment is None:
                raise AppError(
                    code="EVAL_EXPERIMENT_NOT_FOUND",
                    message="Eval Experiment was not found",
                    status_code=HTTPStatus.NOT_FOUND,
                )
            trials = await self._evals.list_trials(experiment_id)
            cases_by_id = {case.case_id: case for case in dataset.cases}
            summaries: list[TrialSummary] = []
            scored = 0
            passed = 0
            for trial in trials:
                case = cases_by_id.get(trial.case_id)
                # Cases outside the provided dataset snapshot still get a
                # TrialSummary -- the report must enumerate every persisted
                # Trial even if the caller's dataset bundle is stale.
                _ = case
                summaries.append(_trial_summary_from_snapshot(trial))
                if trial.status == "completed":
                    scores = await self._evals.list_scores(trial.id)
                    if scores:
                        scored += 1
                        if all(score.hard_gate for score in scores):
                            passed += 1
            completed = sum(1 for s in summaries if s.status == "completed") or 1
            return ExperimentReport(
                experiment_id=experiment.id,
                experiment_status=experiment.status,
                trial_count=len(trials),
                trials=summaries,
                scored_trial_count=scored,
                hard_gate_pass_fraction=round(passed / completed, 6),
            )

    @staticmethod
    def _frozen_hash(experiment: EvalExperiment) -> str:        return canonical_sha256(
            {
                "dataset_id": experiment.dataset_id,
                "dataset_version": experiment.dataset_version,
                "dataset_hash": experiment.dataset_hash,
                "git_commit": experiment.git_commit,
                "graph_version": experiment.graph_version,
                "prompt_version": experiment.prompt_version,
                "model_version": experiment.model_version,
                "tool_version": experiment.tool_version,
                "context_version": experiment.context_version,
                "memory_version": experiment.memory_version,
                "execution_mode": experiment.execution_mode,
                "variant_role": experiment.variant_role,
            }
        )


def _trial_seed(fixture_hash: str, trial_index: int) -> int:
    return int(fixture_hash[:8], 16) ^ trial_index


def _trial_summary_from_snapshot(trial: EvalTrial):  # type: ignore[no-untyped-def]
    """Build a ``TrialSummary`` from a persisted Trial + its outcome snapshot.

    Mirrors ``evals/v2/experiment_runner.py::_summarize`` but reads only DB
    state (no live ``RunOutcome``). The snapshot was written by
    ``TrialRunner._finalize_trial`` for completed / degraded trials; for
    cancelled / failed / timed-out trials we fall back to ORM fields plus
    the persisted ``error_code``.
    """

    from evals.v2.experiment_runner import TrialSummary

    snapshot = trial.outcome_snapshot_json
    run_status: str | None = None
    result_kind: str | None = None
    tokens_in = 0
    tokens_out = 0
    latency_ms = 0
    terminal_events_count = 0
    tool_call_count = 0
    if snapshot:
        run_block = snapshot.get("run")
        if isinstance(run_block, dict):
            run_status_raw = run_block.get("status")
            run_status = str(run_status_raw) if run_status_raw is not None else None
            result_kind_raw = run_block.get("result_kind")
            result_kind = (
                str(result_kind_raw) if result_kind_raw is not None else None
            )
            tokens_in = int(run_block.get("total_tokens_in", 0) or 0)
            tokens_out = int(run_block.get("total_tokens_out", 0) or 0)
            latency_ms = int(run_block.get("total_latency_ms", 0) or 0)
        events = snapshot.get("events")
        if isinstance(events, list):
            # Snapshot events are dicts; terminal ones carry event_type in
            # {"run.completed","run.degraded","run.failed","run.cancelled"}.
            terminal_types = {
                "run.completed",
                "run.degraded",
                "run.failed",
                "run.cancelled",
            }
            terminal_events_count = sum(
                1
                for ev in events
                if isinstance(ev, dict)
                and ev.get("event_type") in terminal_types
            )
        tool_calls = snapshot.get("tool_calls")
        if isinstance(tool_calls, list):
            tool_call_count = len(tool_calls)

    if trial.status == "completed" and run_status in {"completed", "degraded"}:
        report_status = "completed"
    elif run_status == "cancelled" or trial.status == "cancelled":
        report_status = "cancelled"
    elif trial.status in {"failed", "timed_out"}:
        report_status = "failed"
    else:
        report_status = trial.status

    return TrialSummary(
        trial_id=trial.id,
        case_id=trial.case_id,
        status=report_status,
        run_status=run_status,
        result_kind=result_kind,
        tokens_in=tokens_in or trial.tokens_in,
        tokens_out=tokens_out or trial.tokens_out,
        latency_ms=latency_ms or trial.latency_ms,
        error_code=trial.error_code,
        terminal_event_count=terminal_events_count,
        tool_call_count=tool_call_count,
    )
