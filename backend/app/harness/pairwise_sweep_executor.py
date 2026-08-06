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

from sqlalchemy import func, select, text, update
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

        Commit 3.1 revision (issue #6): the advisory lock is now held at
        SESSION level for the whole ``_drive_sweep`` lifetime, NOT
        transaction level. This removes the prior coupling where the LLM
        Provider call ran inside the advisory-lock transaction (long
        transaction + DB connection pinned during a slow network call).
        Each Item's claim/process/mark sequence now runs in its own short
        transaction; the lock prevents a second worker from acting on the
        same Sweep in the meantime.

        Commit 3.1 revision (issue #3): on each entry we call
        ``_recover_running_items`` *under* the advisory lock. Items left
        ``running`` by a previous crash are either re-queued (no
        persisted JudgeResult) or reconciled straight to ``completed``
        (result already exists) — they cannot stay stuck.
        """

        judge = build_pairwise_judge(self._settings)
        # Session-level advisory lock. Acquired at the start, released in
        # finally. Other workers converging on this Sweep block here (or
        # on the same key on another connection) until we release.
        key1, key2 = _advisory_key_parts(sweep_id)
        async with self._session_factory() as lock_session:
            await lock_session.execute(
                text("SELECT pg_advisory_lock(:k1, :k2)"),
                {"k1": key1, "k2": key2},
            )
            try:
                await self._recover_running_items(lock_session, sweep_id)
                while True:
                    done = await self._pump_one_item(sweep_id, judge)
                    if done:
                        return
            finally:
                await lock_session.execute(
                    text("SELECT pg_advisory_unlock(:k1, :k2)"),
                    {"k1": key1, "k2": key2},
                )

    async def _pump_one_item(
        self, sweep_id: UUID, judge: PairwiseJudge
    ) -> bool:
        """Run ONE claim → process → mark iteration in a short
        transaction. Returns True if the Sweep has reached a terminal
        state (no further work this call); False to keep pumping."""

        async with self._session_factory() as session:
            async with session_transaction(session):
                sweep = await EvalRepository(session).get_sweep(sweep_id)
                if sweep is None or sweep.terminal_at is not None:
                    return True
                if sweep.cancel_requested_at is not None:
                    await self._drain_cancelled(session, sweep)
                    await self._maybe_finalize_sweep(session, sweep.id)
                    return True

                item = await self._claim_one_item(session, sweep_id)
                if item is None:
                    await self._maybe_finalize_sweep(session, sweep_id)
                    return True

                await self._process_item(session, sweep, item, judge)
                return False

    async def _recover_running_items(
        self, session: AsyncSession, sweep_id: UUID
    ) -> None:
        """Requeue / reconcile Items left ``running`` by a crash.

        Under the session-level advisory lock (so no other worker is
        racing), we partition the running Item set:

        * Item has NO persisted ``EvalPairwiseJudgeResult`` for its
          deterministic ``judge_run_id`` → flip back to ``queued``. The
          main pump will re-claim and re-execute it (Provider call).
        * Item HAS a persisted Result → CAS it straight to ``completed``
          via the existing ``mark_sweep_item_completed`` path. No
          duplicate Provider invocation. Pair-counter delta is applied
          via ``_apply_pair_deltas`` so a recovery-completed Item honors
          the same per-Pair accounting as the happy path (e.g. if the
          sibling was already terminal, this is the SECOND terminal and
          must bump completed_pair; if both siblings are completed with
          results, position_pair bumps once).

        Both paths are safe because ``judge_run_id`` is uuid5-derived
        from (sweep, pair, position, model, prompt, rubric) — the second
        attempt deterministically re-resolves to the same id.
        """

        async with session_transaction(session):
            sweep = await EvalRepository(session).get_sweep(sweep_id)
            if sweep is None:
                return
            running_items = await EvalRepository(
                session
            ).list_running_sweep_items(sweep_id)
            for item in running_items:
                existing = await EvalRepository(session).get_judge_result_by_run(
                    item.judge_run_id
                )
                if existing is None:
                    # No result yet — requeue (CAS: only running → queued).
                    # Use ORM update() with synchronize_session so that
                    # Item rows already loaded in this Session's identity
                    # map reflect the new status; raw text() would leave
                    # them stale (Issue #7).
                    await session.execute(
                        update(EvalPairwiseSweepItem)
                        .where(
                            EvalPairwiseSweepItem.id == item.id,
                            EvalPairwiseSweepItem.status == "running",
                        )
                        .values(status="queued")
                        .execution_options(synchronize_session="fetch")
                    )
                    continue
                # Result already persisted — reconcile to completed.
                transitioned = await EvalRepository(
                    session
                ).mark_sweep_item_completed(
                    item.id, judge_result_id=existing.id
                )
                if not transitioned:
                    continue
                # Apply the same per-Pair delta accounting as the happy
                # path so counter invariants hold across recovery.
                await session.refresh(item)
                await self._apply_pair_deltas(session, sweep, item)

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
        ``judge_run_id`` is forwarded by us. ``run_pairwise_judge`` guards
        against an existing result for this ``judge_run_id`` (Commit 3.1)
        so a re-executed recovery Item does NOT raise IntegrityError nor
        double-spend Provider cost.
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
            if not transitioned:
                return
            await EvalRepository(session).increment_sweep_failed_run(sweep.id)
            # THIS terminal transition may also complete the Pair (if the
            # sibling was already terminal). The completed_pair counter
            # must advance; position_pair never advances on a failed Item
            # because failed Items never have judge_result_id set.
            await self._apply_pair_deltas(session, sweep, item)
            return

        transitioned = await EvalRepository(session).mark_sweep_item_completed(
            item.id, judge_result_id=result.id
        )
        if not transitioned:
            return  # already terminal (idempotent replay)

        # Refresh the local Item so _pair_completion_flags sees the just-
        # committed status + judge_result_id rather than the in-memory
        # pre-transition snapshot.
        await session.refresh(item)
        await self._apply_pair_deltas(session, sweep, item)

    async def _apply_pair_deltas(
        self,
        session: AsyncSession,
        sweep: EvalPairwiseSweep,
        item: EvalPairwiseSweepItem,
    ) -> None:
        """Compute per-Pair deltas after ``item`` has just transitioned
        to terminal and apply them to the Sweep counters."""

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
        """Return ``(completed_pair_delta, position_pair_delta)`` to apply
        AFTER the current Item's transition just landed.

        REVISED SEMANTICS (per Commit 3.1 reviewer issue #1 + #2):

        * ``completed_pair_delta`` — +1 only when this transition marks
          the LAST required Item for the Pair as terminal (i.e. BOTH
          baseline + swapped variants are now terminal). Earlier terminal
          transitions are NO-OPs so the Pair count reflects how many
          Pairs have fully completed, not "started completing".
        * ``position_pair_delta`` — +1 only when BOTH required Items are
          ``completed`` AND BOTH have a persisted ``judge_result_id``.
          ``failed`` / ``cancelled`` items never count toward position
          metrics — a Pair without a valid pair of completed Judge
          results cannot contribute to position-bias analysis.

        Both deltas therefore evaluate the SIBLING's post-transition state.
        Return ``(False, False)`` when no bump is due.
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
            # forces both variants). Treat this single Item as completing
            # both Pair counts iff it itself is completed with a result.
            return (
                True,
                item.status == "completed" and item.judge_result_id is not None,
            )

        sibling_terminal = sibling.status in {"completed", "failed", "cancelled"}
        # This transition only just landed; for THIS Item to be the
        # "second terminal" we require the sibling already terminal.
        if not sibling_terminal:
            # First terminal transition for the Pair — no deltas yet.
            return False, False

        # THIS Item is the SECOND terminal transition → bump
        # completed_pair once. The sibling side was already terminal and
        # did NOT bump completed_pair (it returned False on its own
        # transition), so we are not double-counting.
        completed_pair = True

        # position_pair requires BOTH items completed WITH results.
        this_completed = (
            item.status == "completed" and item.judge_result_id is not None
        )
        sibling_completed = (
            sibling.status == "completed"
            and sibling.judge_result_id is not None
        )
        position_pair = this_completed and sibling_completed
        return completed_pair, position_pair

    async def _drain_cancelled(
        self, session: AsyncSession, sweep: EvalPairwiseSweep
    ) -> None:
        """Cancel every still-queued Item. Per supplementary #4 the
        cancel request itself does not flip status; we (Executor) flip
        queued Items to ``cancelled`` here.

        Issue #7: use SQLAlchemy's ``update(...).execution_options(
        synchronize_session="fetch")`` so the ORM Identity Map is
        synchronised to the new ``status`` / ``terminal_at`` values
        without requiring ``session.expire_all()`` (which triggers
        lazy-load autoflushes that fail under async). Downstream
        ``_maybe_finalize_sweep`` then queries via SQL GROUP BY for
        its decision so there is no risk of acting on stale state.
        """

        await session.execute(
            update(EvalPairwiseSweepItem)
            .where(
                EvalPairwiseSweepItem.sweep_id == sweep.id,
                EvalPairwiseSweepItem.status == "queued",
            )
            .values(status="cancelled", terminal_at=func.now())
            .execution_options(synchronize_session="fetch")
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
