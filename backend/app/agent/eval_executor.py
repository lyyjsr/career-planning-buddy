"""Background executor for Eval V2 experiments.

Mirrors ``AgentRunExecutor``'s in-process ``asyncio.create_task`` discipline:
``EvalService.create_experiment`` (synchronously, in the request session)
inserts the ``EvalExperiment`` + ``EvalTrial`` rows, then the HTTP handler
calls ``submit()`` here; the spawned coroutine opens its own sessions via
``self._session_factory`` and drives ``ExperimentRunner.run_experiment_and_grade``.

No multi-worker reliability is claimed (same contract as ``AgentRunExecutor``).
Recovery on startup marks any ``running`` experiment ``failed`` because
``ExperimentRunner`` itself is stateless and cannot resume mid-Trial.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings, get_settings
from app.core.database import AsyncSessionFactory, session_transaction
from app.core.exceptions import AppError
from app.models.eval import EvalExperiment
from app.services.evals import EvalService
from evals.v2.dataset_loader import DatasetBundle
from evals.v2.experiment_runner import ExperimentRunner

logger = logging.getLogger(__name__)


class EvalRunnerExecutor:
    """Drives one Eval experiment per asyncio Task in-process."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession] = AsyncSessionFactory,
        settings: Settings | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings or get_settings()
        self._tasks: dict[UUID, asyncio.Task[None]] = {}

    def submit(
        self, experiment_id: UUID, dataset: DatasetBundle, *, grade: bool = True
    ) -> None:
        """Spawn (or no-op if already running) the background coroutine."""

        current = self._tasks.get(experiment_id)
        if current is not None and not current.done():
            return
        task = asyncio.create_task(
            self._execute(experiment_id, dataset, grade=grade),
            name=f"eval-run-{experiment_id}",
        )
        self._tasks[experiment_id] = task
        task.add_done_callback(self._done_callback(experiment_id))

    async def _execute(
        self, experiment_id: UUID, dataset: DatasetBundle, *, grade: bool
    ) -> None:
        """Drive ``ExperimentRunner`` from a fresh session scope.

        ``run_experiment_and_grade`` already transitions the experiment to
        ``failed`` on stage-1 exceptions, so any exception reaching here has
        already been recorded in DB state. We still log the traceback so the
        asyncio default exception handler does not silently swallow it.
        """

        runner = ExperimentRunner(
            session_factory=self._session_factory, settings=self._settings
        )
        try:
            await runner.run_experiment_and_grade(experiment_id, dataset, grade=grade)
        except Exception:
            logger.exception("eval experiment %s failed", experiment_id)

    async def request_cancel(self, experiment_id: UUID) -> None:
        """Cancel a running experiment's background task (if any)."""

        task = self._tasks.get(experiment_id)
        if task is not None and not task.done():
            task.cancel()

    async def recover_interrupted(self) -> int:
        """On process restart, mark every ``running`` experiment ``failed``.

        ``ExperimentRunner`` is stateless and cannot resume a half-executed
        Trial, so re-running is unsafe. We mark the experiment ``failed``
        (legal transition per ``EXPERIMENT_TRANSITIONS``: running -> failed).
        """

        async with self._session_factory() as session:
            async with session_transaction(session):
                rows = list(
                    (
                        await session.scalars(
                            select(EvalExperiment).where(
                                EvalExperiment.status == "running"
                            )
                        )
                    ).all()
                )
                service = EvalService(session)
                for exp in rows:
                    try:
                        await service.transition_experiment(exp.id, "failed")
                    except AppError:
                        # Illegal transition (rare race) -- never block startup.
                        pass
        return len(rows)

    async def shutdown(self) -> None:
        """Cancel and await every outstanding task on application shutdown."""

        tasks = [task for task in self._tasks.values() if not task.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()

    def _discard(self, experiment_id: UUID, task: asyncio.Task[None]) -> None:
        if self._tasks.get(experiment_id) is task:
            self._tasks.pop(experiment_id, None)

    def _done_callback(
        self, experiment_id: UUID
    ) -> Callable[[asyncio.Task[None]], None]:
        def discard(task: asyncio.Task[None]) -> None:
            self._discard(experiment_id, task)

        return discard


eval_runner_executor = EvalRunnerExecutor()
