"""Persistence operations for the Eval V2 control plane."""

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.eval import EvalEvidenceItem, EvalExperiment, EvalScore, EvalTrial


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

    async def list_experiments(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[EvalExperiment]:
        """Paginated listing for ``GET /api/v1/eval/runs``.

        Ordering is ``created_at desc`` so the newest Experiments surface
        first; pagination is the standard limit/offset style used by the
        agent-runs list endpoint.
        """

        statement = select(EvalExperiment)
        if status is not None:
            statement = statement.where(EvalExperiment.status == status)
        statement = (
            statement.order_by(EvalExperiment.created_at.desc())
            .limit(max(1, min(limit, 200)))
            .offset(max(0, offset))
        )
        result = await self._session.execute(statement)
        return list(result.scalars())

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

    async def get_trial(
        self, trial_id: UUID, *, for_update: bool = False
    ) -> EvalTrial | None:
        statement: Select[tuple[EvalTrial]] = select(EvalTrial).where(
            EvalTrial.id == trial_id
        )
        if for_update:
            # ``with_for_update`` writes ``FOR UPDATE``. Combine with
            # ``populate_existing`` so the row is re-loaded from the DB rather
            # than served from the session identity map -- otherwise a Trial
            # committed via a different session (TrialRunner's own factory)
            # stays invisible to the caller. PR-5 fix: clears the cached
            # ``status='pending'`` image that pre-dates the attach step.
            statement = statement.with_for_update().execution_options(
                populate_existing=True
            )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def attach_trial_outcome(
        self,
        trial_id: UUID,
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
    ) -> None:
        """Freeze a Trial's terminal outcome.

        Uses an explicit UPDATE keyed on ``trial_id`` so the write does not
        depend on the ORM identity map of the originating session (the
        TrialRunner calls this from a different session than the one that
        created the Trial row).

        Satisfies ``ck_eval_trials_completed_outcome``: a ``completed`` Trial
        must carry a ``run_id`` + ``outcome_snapshot_json`` + 64-hex
        ``transcript_hash``. Non-completed terminal states (``failed``,
        ``timed_out``, ``cancelled``) may omit the snapshot/hash and record an
        ``error_code`` instead.
        """

        await self._session.execute(
            update(EvalTrial)
            .where(EvalTrial.id == trial_id)
            .values(
                status=status,
                run_id=run_id,
                outcome_snapshot_json=outcome_snapshot,
                transcript_hash=transcript_hash,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                latency_ms=latency_ms,
                error_code=error_code,
                error_message=error_message,
                finished_at=finished_at,
            )
        )

    async def mark_trial_running(
        self, trial_id: UUID, *, started_at: datetime
    ) -> None:
        """Transition a pending Trial to ``running`` before execution.

        Uses an explicit UPDATE keyed on ``trial_id`` so the write does not
        depend on the ORM identity map of the originating session (the
        TrialRunner calls this from a different session than the one that
        created the Trial row). Mirrors the DB trigger's legal
        ``pending -> running`` transition.
        """

        await self._session.execute(
            update(EvalTrial)
            .where(EvalTrial.id == trial_id, EvalTrial.status == "pending")
            .values(status="running", started_at=started_at)
        )

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

    async def delete_evidence_for_trial(self, trial_id: UUID) -> None:
        """Remove any previously-collected evidence so the next collect can
        re-insert rows whose ids differ if content changed.

        Used before ``create_evidence_items`` to make re-collection
        deterministic; the foreign key ON DELETE CASCADE would otherwise
        orphan rows that no longer match the projection.
        """

        from sqlalchemy import delete

        await self._session.execute(
            delete(EvalEvidenceItem).where(EvalEvidenceItem.trial_id == trial_id)
        )

    async def create_evidence_items(
        self, items: Sequence[EvalEvidenceItem]
    ) -> list[EvalEvidenceItem]:
        self._session.add_all(items)
        await self._session.flush()
        return list(items)

    async def list_evidence_items(self, trial_id: UUID) -> list[EvalEvidenceItem]:
        result = await self._session.execute(
            select(EvalEvidenceItem)
            .where(EvalEvidenceItem.trial_id == trial_id)
            .order_by(EvalEvidenceItem.kind, EvalEvidenceItem.source_type)
        )
        return list(result.scalars())

