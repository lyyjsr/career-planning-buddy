"""Persistence operations for the Eval V2 control plane."""

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.eval import EvalExperiment, EvalScore, EvalTrial


class EvalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_experiment(self, experiment: EvalExperiment) -> EvalExperiment:
        self._session.add(experiment)
        await self._session.flush()
        return experiment

    async def get_experiment(
        self, experiment_id: UUID, *, for_update: bool = False
    ) -> EvalExperiment | None:
        statement: Select[tuple[EvalExperiment]] = select(EvalExperiment).where(
            EvalExperiment.id == experiment_id
        )
        if for_update:
            statement = statement.with_for_update()
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def create_trials(self, trials: Sequence[EvalTrial]) -> list[EvalTrial]:
        self._session.add_all(trials)
        await self._session.flush()
        return list(trials)

    async def list_trials(self, experiment_id: UUID) -> list[EvalTrial]:
        result = await self._session.execute(
            select(EvalTrial)
            .where(EvalTrial.experiment_id == experiment_id)
            .order_by(EvalTrial.case_id, EvalTrial.trial_index)
        )
        return list(result.scalars())

    async def get_trial(self, trial_id: UUID, *, for_update: bool = False) -> EvalTrial | None:
        statement: Select[tuple[EvalTrial]] = select(EvalTrial).where(EvalTrial.id == trial_id)
        if for_update:
            statement = statement.with_for_update()
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def attach_trial_outcome(
        self,
        trial: EvalTrial,
        *,
        status: str,
        run_id: UUID | None,
        outcome_snapshot: dict[str, object] | None,
        transcript_hash: str | None,
        tokens_in: int,
        tokens_out: int,
        latency_ms: int,
        finished_at: datetime,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> EvalTrial:
        """Freeze a Trial's terminal outcome.

        Satisfies ``ck_eval_trials_completed_outcome``: a ``completed`` Trial
        must carry a ``run_id`` + ``outcome_snapshot_json`` + 64-hex
        ``transcript_hash``. Non-completed terminal states (``failed``,
        ``timed_out``, ``cancelled``) may omit the snapshot/hash and record an
        ``error_code`` instead.
        """

        trial.status = status
        trial.run_id = run_id
        trial.outcome_snapshot_json = outcome_snapshot
        trial.transcript_hash = transcript_hash
        trial.tokens_in = tokens_in
        trial.tokens_out = tokens_out
        trial.latency_ms = latency_ms
        trial.error_code = error_code
        trial.error_message = error_message
        trial.finished_at = finished_at
        await self._session.flush()
        return trial

    async def mark_trial_running(self, trial: EvalTrial, *, started_at: datetime) -> EvalTrial:
        """Transition a pending Trial to ``running`` before execution."""

        trial.status = "running"
        trial.started_at = started_at
        await self._session.flush()
        return trial

    async def count_nonterminal_trials(self, experiment_id: UUID) -> int:
        result = await self._session.execute(
            select(func.count(EvalTrial.id)).where(
                EvalTrial.experiment_id == experiment_id,
                EvalTrial.status.in_(("pending", "running")),
            )
        )
        return int(result.scalar_one())

    async def create_score(self, score: EvalScore) -> EvalScore:
        self._session.add(score)
        await self._session.flush()
        return score

    async def list_scores(self, trial_id: UUID) -> list[EvalScore]:
        result = await self._session.execute(
            select(EvalScore)
            .where(EvalScore.trial_id == trial_id)
            .order_by(EvalScore.domain, EvalScore.grader_name)
        )
        return list(result.scalars())
