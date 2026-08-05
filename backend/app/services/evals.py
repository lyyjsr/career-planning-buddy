"""Use cases and legal state transitions for the Eval V2 control plane."""

from datetime import UTC, datetime
from http import HTTPStatus
from uuid import UUID

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
                await self.add_grade(trial_id, result)
            return results

    @staticmethod
    def _frozen_hash(experiment: EvalExperiment) -> str:
        return canonical_sha256(
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
