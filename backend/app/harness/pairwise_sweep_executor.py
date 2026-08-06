"""PR-9c.2 Pairwise Sweep Executor.

Drives one Judge Sweep over its frozen SweepItem work list. The executor
is the COMMIT 3 process-side component that:

* claims work atomically (single-instance advisory lock per Sweep plus
  per-item CAS via ``status IN ('queued','running')``);
* runs ``EvalService.run_pairwise_judge`` for each (pair, position_variant)
  row using the deterministic ``judge_run_id`` already stored on the Item;
* mutates Item to ``completed`` only when a JudgeResult row exists, then
  bumps Sweep counters when the CAS transition returns ``True``;
* mutates Item to ``failed`` on control-plane errors (provider timeouts
  with no retry budget) — a Judge that returned ``invalid_structured_output``
  is STILL a real ``EvalPairwiseJudgeResult`` row, so the Item goes to
  ``completed`` with that result (per supplementary constraint #3);
* cooperatively honours ``cancel_requested_at`` between Items and marks
  remaining queued Items as ``cancelled`` (terminal), then transitions
  the Sweep to ``cancelled`` if all of its Items are terminal;
* on process restart, ``recover_interrupted`` scans Sweeps in
  ``status='running'`` and replays them — SweepItem rows ARE the work
  list, so no sampler re-run is needed.

Multi-instance safety:

* ``pg_advisory_xact_lock`` keyed on a hash of the sweep id prevents two
  worker processes from acting on the same Sweep concurrently.

NOT provided here (out of scope for PR-9c.2): true Redis-style lease,
distributed lease. The advisory lock is a co-located-Postgres lease.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings, get_settings
from app.core.database import AsyncSessionFactory, session_transaction
from app.models.eval import (
    EvalPairwiseSweep,
    EvalPairwiseSweepItem,
)
from app.repositories.evals import EvalRepository
from app.services.evals import EvalService
from evals.v2.judge import PairwiseJudge
from evals.v2.judge_factory import build_pairwise_judge
from evals.v2.pairwise import PositionVariant

logger = logging.getLogger(__name__)

# Stable Postgres advisory-lock namespace for Pairwise Sweeps. Two int32
# keys: namespace tag + low-32 bits of the sweep id.
_SWEEP_LOCK_NAMESPACE = 0x9C20


def _advisory_key_parts(sweep_id: UUID) -> tuple[int, int]:
    """Decompose a UUID into (namespace, sweep-hashed-key32) for
    ``pg_advisory_xact_lock``."""

    return _SWEEP_LOCK_NAMESPACE, int.from_bytes(sweep_id.bytes[-4:], "big")


class PairwiseSweepExecutor:
    """In-process async executor for Sweeps. Mirrors ``EvalRunnerExecutor``
    in shape (in-process ``asyncio.create_task``, no distributed lease
    beyond the Postgres advisory lock)."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession] = AsyncSessionFactory,
        settings: Settings | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings or get_settings()
        self._tasks: dict[UUID, asyncio.Task[None]] = {}

    # ----------------------------------------------------------- public

    def submit(self, sweep_id: UUID) -> None:
        """Spawn the worker for ``sweep_id`` (no-op if already running)."""

        current = self._tasks.get(sweep_id)
        if current is not None and not current.done():
            return
        task = asyncio.create_task(
            self._execute(sweep_id),
            name=f"pairwise-sweep-{sweep_id}",
        )
        self._tasks[sweep_id] = task
        task.add_done_callback(self._discard_callback(sweep_id))

    async def recover_interrupted(self) -> int:
        """On process restart, replay every Sweep left ``running``.

        Per supplementary constraint #3, the SweepItem rows ARE the work
        list; the sampler is NEVER re-run. We simply reenter
        ``_execute`` for each running Sweep — the advisory lock + CAS
        pattern makes this safe even if the original task somehow still
        lingers.

        Returns the count of Sweeps re-entered.
        """

        async with self._session_factory() as session:
            async with session_transaction(session):
                rows = list(
                    (
                        await session.scalars(
                            select(EvalPairwiseSweep).where(
                                EvalPairwiseSweep.status == "running"
                            )
                        )
                    ).all()
                )
        for sweep in rows:
            # Don't auto-spawn: tests may want to call _execute directly.
            # Production startup hook should call ``submit`` instead.
            self.submit(sweep.id)
        return len(rows)

    # ---------------------------------------------------------- internals

    async def _execute(self, sweep_id: UUID) -> None:
        """Drive the Sweep to terminal inside a per-call advisory lock.

        The lock is acquired inside a transaction-per-item pattern so two
        concurrent processes cannot act on the same Sweep — second
        process blocks on the advisory lock until the first commits its
        item (or the whole Sweep is terminal).
        """

        try:
            await self._drive_sweep(sweep_id)
        except Exception:
            logger.exception("pairwise sweep %s failed", sweep_id)

    async def _drive_sweep(self, sweep_id: UUID) -> None:
        """Lock-and-pump loop. Repeats until every Item is terminal OR a
        cancel drains the remaining Items.

        Each iteration acquires the advisory lock at the top of a
        transaction, claims ONE queued/running Item, runs the Judge,
        applies the CAS transition + counter bump, and commits. Then
        the loop continues.
        """

        judge = build_pairwise_judge(self._settings)
        while True:
            async with self._session_factory() as session:
                async with session_transaction(session):
                    # Acquire advisory lock for this Sweep's lifetime of
                    # this transaction. Other workers block here until
                    # we commit.
                    key1, key2 = _advisory_key_parts(sweep_id)
                    await session.execute(
                        text("SELECT pg_advisory_xact_lock(:k1, :k2)"),
                        {"k1": key1, "k2": key2},
                    )

                    sweep = await EvalRepository(session).get_sweep(sweep_id)
                    if sweep is None:
                        # Sweep was hard-deleted out from under us.
                        return
                    if sweep.terminal_at is not None:
                        return

                    if sweep.cancel_requested_at is not None:
                        # Drain remaining queued Items as cancelled.
                        await self._drain_cancelled(session, sweep)
                        await self._maybe_finalize_sweep(session, sweep.id)
                        return

                    item = await self._claim_one_item(session, sweep_id)
                    if item is None:
                        # No more work to do this cycle — finalize if
                        # everything is terminal.
                        await self._maybe_finalize_sweep(session, sweep_id)
                        return

                    await self._process_item(session, sweep, item, judge)

    async def _claim_one_item(
        self, session: AsyncSession, sweep_id: UUID
    ) -> EvalPairwiseSweepItem | None:
        """Atomically flip the next ``queued`` Item to ``running`` under
        the advisory lock. Returns ``None`` if no queued Item remains."""

        result = await session.execute(
            select(EvalPairwiseSweepItem)
            .where(
                EvalPairwiseSweepItem.sweep_id == sweep_id,
                EvalPairwiseSweepItem.status == "queued",
            )
            .order_by(
                EvalPairwiseSweepItem.pair_hash,
                EvalPairwiseSweepItem.position_variant,
            )
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        item = result.scalar_one_or_none()
        if item is None:
            return None
        item.status = "running"
        return item

    async def _process_item(
        self,
        session: AsyncSession,
        sweep: EvalPairwiseSweep,
        item: EvalPairwiseSweepItem,
        judge: PairwiseJudge,
    ) -> None:
        """Run one Judge execution for an Item and persist the result.

        Wraps ``EvalService.run_pairwise_judge`` (PR-9c.1) which already
        handles Evidence authorization + the deterministic
        ``judge_run_id`` is forwarded by us.
        """

        service = EvalService(session)
        try:
            _pair, result = await service.run_pairwise_judge(
                baseline_trial_id=item.baseline_trial_id,
                candidate_trial_id=item.candidate_trial_id,
                case_id=item.case_id,
                comparison_group_id=sweep.comparison_group_id,
                judge_run_id=item.judge_run_id,
                judge=judge,
                position_variant=PositionVariant(item.position_variant),
            )
        except Exception as exc:
            # Provider-level hard error: retry budget exhausted by the
            # adapter. Mark Item as failed (control-plane failure).
            transitioned = await EvalRepository(session).mark_sweep_item_failed(
                item.id, error_code=_provider_error_code(exc)
            )
            if transitioned:
                await EvalRepository(session).increment_sweep_failed_run(sweep.id)
            return

        transitioned = await EvalRepository(session).mark_sweep_item_completed(
            item.id, judge_result_id=result.id
        )
        if not transitioned:
            return  # already terminal (idempotent replay)

        # Counter bump — per Pair only once. Items for the same Pair come
        # in two flavours: BASELINE and SWAPPED. A Pair count increments
        # only on the FIRST completed Item of either variant; a Position
        # pair count increments only when BOTH variants are terminal.
        completed_pair, position_pair = await self._pair_completion_flags(
            session, item
        )
        await EvalRepository(session).increment_sweep_completed_run(
            sweep.id,
            completed_pair=completed_pair,
            position_pair=position_pair,
        )

    async def _pair_completion_flags(
        self, session: AsyncSession, item: EvalPairwiseSweepItem
    ) -> tuple[bool, bool]:
        """Return ``(completed_pair, position_pair)`` AFTER the current
        Item's transition. ``completed_pair`` is True if at least one
        Item for this (sweep, pair) is now terminal (i.e. the pair
        started completing). ``position_pair`` is True iff both variants
        are terminal.

        Per supplementary constraint #5, completed_pair_count and
        position_pair_count are bumped AT MOST ONCE per Pair. The
        Service-level caller (here) decides by looking at the OTHER
        sibling's status:

        * completed_pair: True iff the sibling is NOT yet terminal
          (this Item is the FIRST terminal for the Pair).
        * position_pair: True iff the sibling is also terminal after
          this Item's transition.
        """

        sibling_position = (
            "swapped"
            if item.position_variant == "baseline"
            else "baseline"
        )
        sibling = await EvalRepository(session).get_sweep_item(
            item.sweep_id, item.pair_id, sibling_position
        )
        if sibling is None:
            # No sibling materialized (shouldn't happen — every sweep
            # forces both variants). Treat this Item as completing the
            # pair and the position pair.
            return True, True
        sibling_terminal = sibling.status in {
            "completed", "failed", "cancelled"
        }
        # completed_pair: this Item is the first terminal transition
        # for the Pair iff sibling is not yet terminal.
        completed_pair = not sibling_terminal
        # position_pair: BOTH Items are now terminal.
        position_pair = sibling_terminal
        return completed_pair, position_pair

    async def _drain_cancelled(
        self, session: AsyncSession, sweep: EvalPairwiseSweep
    ) -> None:
        """Cancel every still-queued Item. Per supplementary #4 the
        cancel request itself does not flip status; we (Executor) flip
        queued Items to ``cancelled`` here."""

        await session.execute(
            text(
                "UPDATE eval_pairwise_sweep_items "
                "SET status = 'cancelled', terminal_at = now() "
                "WHERE sweep_id = :sid AND status = 'queued'"
            ),
            {"sid": sweep.id},
        )

    async def _maybe_finalize_sweep(
        self, session: AsyncSession, sweep_id: UUID
    ) -> None:
        """If every Item is terminal, transition the Sweep itself.

        Sweep is marked ``cancelled`` iff ``cancel_requested_at`` is set;
        ``completed`` if all items succeeded; ``failed`` if any Item
        failed (control-plane failure) and the rest are completed /
        cancelled.
        """

        # Item counts by status.
        result = await session.execute(
            select(
                EvalPairwiseSweepItem.status,
                func.count(EvalPairwiseSweepItem.id),
            )
            .where(EvalPairwiseSweepItem.sweep_id == sweep_id)
            .group_by(EvalPairwiseSweepItem.status)
        )
        counts = {status: n for status, n in result.all()}
        non_terminal = counts.get("queued", 0) + counts.get("running", 0)
        if non_terminal:
            return  # not done yet

        sweep = await EvalRepository(session).get_sweep(sweep_id)
        if sweep is None:
            return
        if sweep.terminal_at is not None:
            return  # already finalized

        if sweep.cancel_requested_at is not None:
            # Cooperative cancel fully drained → mark cancelled.
            self._finalize_cancelled(session, sweep)
            return

        any_failed = counts.get("failed", 0) > 0 or counts.get("cancelled", 0) > 0
        terminal_status = "failed" if any_failed else "completed"
        await EvalRepository(session).mark_sweep_terminal(
            sweep_id, status=terminal_status
        )

    @staticmethod
    def _finalize_cancelled(
        session: AsyncSession, sweep: EvalPairwiseSweep
    ) -> None:
        """``mark_sweep_terminal`` reserves status choices to
        ``completed``/``failed``. Cancelled is the only status that
        requires setting BOTH ``cancel_requested_at`` (already set) and
        ``terminal_at`` together, so we write it directly via SQL rather
        than going through the repo's restricted transition helper.
        """

        sweep.status = "cancelled"
        sweep.terminal_at = func.now()

    # ---------------------------------------------------- bookkeeping

    def _discard_callback(
        self, sweep_id: UUID
    ) -> Callable[[asyncio.Task[None]], None]:
        def discard(task: asyncio.Task[None]) -> None:
            if self._tasks.get(sweep_id) is task:
                self._tasks.pop(sweep_id, None)

        return discard

    async def shutdown(self) -> None:
        """Cancel and await every outstanding task."""

        tasks = [task for task in self._tasks.values() if not task.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()


def _provider_error_code(exc: Exception) -> str:
    """Classify a provider-raised exception into a stable error code."""

    name = type(exc).__name__
    if "Timeout" in name:
        return "PROVIDER_TIMEOUT"
    if "RateLimit" in name:
        return "PROVIDER_RATE_LIMIT"
    if "Auth" in name:
        return "PROVIDER_AUTH"
    if "Unavailable" in name:
        return "PROVIDER_UNAVAILABLE"
    return "PROVIDER_HARD_ERROR"


pairwise_sweep_executor = PairwiseSweepExecutor()
