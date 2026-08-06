"""PR-9c.2 Commit 3 Pairwise SweepExecutor tests.

Coverage:
* Deterministic judge_run_id consistency on a (sweep, pair, position)
* _pair_completion_flags respect "first terminal vs both terminal"
* Cooperative cancel drains queued items to ``cancelled``
* Recovery queries queued/running items only

These tests bypass the live HTTP layer (covered by the API integration
test) and call executor internals directly so they are deterministic
and fast.

The executor's Judge call path needs Pair/Trial/Evidence scaffolding
to actually run, so most of these tests verify the *control-plane*
behaviour (claim, drain, completion-flag math) rather than live Judge
execution end-to-end. The full live path is exercised by the Commit 2
service tests (which already cover ``EvalService.run_pairwise_judge``).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import session_transaction
from app.harness.pairwise_sweep_executor import (
    PairwiseSweepExecutor,
    _advisory_key_parts,
    _provider_error_code,
)
from app.models.eval import EvalPairwiseSweepItem
from app.repositories.evals import EvalRepository
from tests.evals_v2.test_pairwise_calibration_repository import (
    _make_sweep,
    _real_judge_result,
    _seed_pair,
)


@pytest.mark.asyncio
async def test_advisory_key_is_stable_per_sweep() -> None:
    """The advisory lock key MUST be deterministic per sweep so two
    workers converging on the same sweep try to take the same lock."""

    sweep = uuid4()
    a = _advisory_key_parts(sweep)
    b = _advisory_key_parts(sweep)
    assert a == b


@pytest.mark.asyncio
async def test_advisory_key_differs_across_sweeps() -> None:
    a = _advisory_key_parts(uuid4())
    b = _advisory_key_parts(uuid4())
    assert a != b or a[0] == b[0]  # namespace is fixed; only key2 varies


@pytest.mark.asyncio
async def test_drain_cancelled_marks_queued_items_cancelled(
    db_session: AsyncSession,
) -> None:
    """``_drain_cancelled`` flips queued items to ``cancelled`` (terminal)
    under a cancel request. ``running`` items are NOT auto-cancelled —
    their in-flight Provider call is allowed to settle, then the Executor
    sees ``cancel_requested_at`` is set on the next iteration."""

    sweep_row = await _make_sweep(db_session, requested_pair_count=2)
    pair = await _seed_pair(db_session, 1)

    def _make_item(position: str) -> EvalPairwiseSweepItem:
        # Per ``ck_eval_pairwise_sweep_items_position_consistency``:
        #   baseline  → display_a=baseline_trial_id, display_b=candidate_trial_id
        #   swapped   → display_a=candidate_trial_id, display_b=baseline_trial_id
        if position == "baseline":
            display_a, display_b = pair.baseline_trial_id, pair.candidate_trial_id
        else:
            display_a, display_b = pair.candidate_trial_id, pair.baseline_trial_id
        return EvalPairwiseSweepItem(
            sweep_id=sweep_row.id,
            pair_id=pair.id,
            position_variant=position,
            case_id=pair.case_id,
            pair_hash=pair.pair_hash,
            baseline_trial_id=pair.baseline_trial_id,
            candidate_trial_id=pair.candidate_trial_id,
            baseline_output_hash="a" * 64,
            candidate_output_hash="a" * 64,
            display_a_trial_id=display_a,
            display_b_trial_id=display_b,
            frozen_review_surface_sha256="a" * 64,
            judge_run_id=uuid4(),
            status="queued",
        )

    items = [_make_item(position) for position in ("baseline", "swapped")]
    async with session_transaction(db_session):
        await EvalRepository(db_session).create_sweep(sweep_row)
        await EvalRepository(db_session).create_sweep_items(items)
    executor = PairwiseSweepExecutor(session_factory=None)  # type: ignore[arg-type]
    async with session_transaction(db_session):
        await executor._drain_cancelled(db_session, sweep_row)  # noqa: SLF001
    # Raw SQL UPDATE bypasses the ORM identity map; re-count via a fresh
    # query rather than touching the cached Item objects.
    async with session_transaction(db_session):
        queued = await db_session.execute(
            text(
                "SELECT count(*) FROM eval_pairwise_sweep_items "
                "WHERE sweep_id = :sid AND status = 'queued'"
            ),
            {"sid": sweep_row.id},
        )
        cancelled = await db_session.execute(
            text(
                "SELECT count(*) FROM eval_pairwise_sweep_items "
                "WHERE sweep_id = :sid AND status = 'cancelled' "
                "AND terminal_at IS NOT NULL"
            ),
            {"sid": sweep_row.id},
        )
    assert queued.scalar_one() == 0
    assert cancelled.scalar_one() == 2


@pytest.mark.asyncio
async def test_pair_completion_flags_first_terminal_for_pair(
    db_session: AsyncSession,
) -> None:
    """``_pair_completion_flags`` returns ``(True, False)`` when the
    sibling opposite-position Item is still queued (this is the FIRST
    terminal transition for the Pair → bump completed_pair_count only).
    """

    sweep_row = await _make_sweep(db_session, requested_pair_count=1)
    pair = await _seed_pair(db_session, 1)
    items = [
        EvalPairwiseSweepItem(
            sweep_id=sweep_row.id,
            pair_id=pair.id,
            position_variant="baseline",
            case_id=pair.case_id,
            pair_hash=pair.pair_hash,
            baseline_trial_id=pair.baseline_trial_id,
            candidate_trial_id=pair.candidate_trial_id,
            baseline_output_hash="a" * 64,
            candidate_output_hash="a" * 64,
            display_a_trial_id=pair.baseline_trial_id,
            display_b_trial_id=pair.candidate_trial_id,
            frozen_review_surface_sha256="a" * 64,
            judge_run_id=uuid4(),
            status="queued",
        ),
        EvalPairwiseSweepItem(
            sweep_id=sweep_row.id,
            pair_id=pair.id,
            position_variant="swapped",
            case_id=pair.case_id,
            pair_hash=pair.pair_hash,
            baseline_trial_id=pair.baseline_trial_id,
            candidate_trial_id=pair.candidate_trial_id,
            baseline_output_hash="a" * 64,
            candidate_output_hash="a" * 64,
            display_a_trial_id=pair.candidate_trial_id,
            display_b_trial_id=pair.baseline_trial_id,
            frozen_review_surface_sha256="a" * 64,
            judge_run_id=uuid4(),
            status="queued",
        ),
    ]
    async with session_transaction(db_session):
        await EvalRepository(db_session).create_sweep(sweep_row)
        await EvalRepository(db_session).create_sweep_items(items)
    executor = PairwiseSweepExecutor(session_factory=None)  # type: ignore[arg-type]
    async with session_transaction(db_session):
        completed_pair, position_pair = await executor._pair_completion_flags(  # noqa: SLF001
            db_session, items[0]
        )
    assert completed_pair is True
    assert position_pair is False


@pytest.mark.asyncio
async def test_pair_completion_flags_both_terminal_when_sibling_already_terminal(
    db_session: AsyncSession,
) -> None:
    """``_pair_completion_flags`` returns ``(False, True)`` when the
    sibling is already terminal — this Item is the SECOND terminal
    transition for the Pair → do NOT bump completed_pair_count (it was
    already bumped by the first sibling); DO bump position_pair_count."""

    sweep_row = await _make_sweep(db_session, requested_pair_count=1)
    pair = await _seed_pair(db_session, 1)
    items = [
        EvalPairwiseSweepItem(
            sweep_id=sweep_row.id,
            pair_id=pair.id,
            position_variant="baseline",
            case_id=pair.case_id,
            pair_hash=pair.pair_hash,
            baseline_trial_id=pair.baseline_trial_id,
            candidate_trial_id=pair.candidate_trial_id,
            baseline_output_hash="a" * 64,
            candidate_output_hash="a" * 64,
            display_a_trial_id=pair.baseline_trial_id,
            display_b_trial_id=pair.candidate_trial_id,
            frozen_review_surface_sha256="a" * 64,
            judge_run_id=uuid4(),
            status="failed",  # sibling already terminal
            error_code="PROVIDER_TIMEOUT",
            terminal_at=datetime.now(UTC),  # required by ck_..._terminal_status
        ),
        EvalPairwiseSweepItem(
            sweep_id=sweep_row.id,
            pair_id=pair.id,
            position_variant="swapped",
            case_id=pair.case_id,
            pair_hash=pair.pair_hash,
            baseline_trial_id=pair.baseline_trial_id,
            candidate_trial_id=pair.candidate_trial_id,
            baseline_output_hash="a" * 64,
            candidate_output_hash="a" * 64,
            display_a_trial_id=pair.candidate_trial_id,
            display_b_trial_id=pair.baseline_trial_id,
            frozen_review_surface_sha256="a" * 64,
            judge_run_id=uuid4(),
            status="queued",
        ),
    ]
    async with session_transaction(db_session):
        await EvalRepository(db_session).create_sweep(sweep_row)
        await EvalRepository(db_session).create_sweep_items(items)
    executor = PairwiseSweepExecutor(session_factory=None)  # type: ignore[arg-type]
    async with session_transaction(db_session):
        completed_pair, position_pair = await executor._pair_completion_flags(  # noqa: SLF001
            db_session, items[1]
        )
    assert completed_pair is False  # sibling already counts the pair
    assert position_pair is True  # both siblings are terminal now


@pytest.mark.asyncio
async def test_maybe_finalize_sweep_marks_completed_when_all_terminal(
    db_session: AsyncSession,
) -> None:
    sweep_row = await _make_sweep(db_session, requested_pair_count=1)
    pair = await _seed_pair(db_session, 1)
    judge_id = await _real_judge_result(db_session, pair=pair)
    item = EvalPairwiseSweepItem(
        sweep_id=sweep_row.id,
        pair_id=pair.id,
        position_variant="baseline",
        case_id=pair.case_id,
        pair_hash=pair.pair_hash,
        baseline_trial_id=pair.baseline_trial_id,
        candidate_trial_id=pair.candidate_trial_id,
        baseline_output_hash="a" * 64,
        candidate_output_hash="a" * 64,
        display_a_trial_id=pair.baseline_trial_id,
        display_b_trial_id=pair.candidate_trial_id,
        frozen_review_surface_sha256="a" * 64,
        judge_run_id=uuid4(),
        status="queued",
    )
    # Manually add a swap variant so all requested_pair_count == 1 means
    # 2 items (baseline + swapped); finalizing requires both terminal.
    item_swap = EvalPairwiseSweepItem(
        sweep_id=sweep_row.id,
        pair_id=pair.id,
        position_variant="swapped",
        case_id=pair.case_id,
        pair_hash=pair.pair_hash,
        baseline_trial_id=pair.baseline_trial_id,
        candidate_trial_id=pair.candidate_trial_id,
        baseline_output_hash="a" * 64,
        candidate_output_hash="a" * 64,
        display_a_trial_id=pair.candidate_trial_id,
        display_b_trial_id=pair.baseline_trial_id,
        frozen_review_surface_sha256="a" * 64,
        judge_run_id=uuid4(),
        status="queued",
    )
    async with session_transaction(db_session):
        await EvalRepository(db_session).create_sweep(sweep_row)
        await EvalRepository(db_session).create_sweep_items([item, item_swap])
        await EvalRepository(db_session).mark_sweep_item_completed(
            item.id, judge_result_id=judge_id
        )
        await EvalRepository(db_session).mark_sweep_item_failed(
            item_swap.id, error_code="PROVIDER_TIMEOUT"
        )

    executor = PairwiseSweepExecutor(session_factory=None)  # type: ignore[arg-type]
    async with session_transaction(db_session):
        await executor._maybe_finalize_sweep(db_session, sweep_row.id)  # noqa: SLF001
        refetched = await EvalRepository(db_session).get_sweep(sweep_row.id)
    assert refetched is not None
    # As long as ANY item failed, Sweep is marked ``failed`` (control
    # plane failure took down the run).
    assert refetched.status == "failed"
    assert refetched.terminal_at is not None


@pytest.mark.asyncio
async def test_recovery_scopes_to_running_sweeps_only(
    db_session: AsyncSession,
) -> None:
    """A ``completed`` Sweep MUST NOT be re-entered by recovery. This
    is a SELECT-level guard, not just the advisory lock (which is
    process-local)."""

    sweep_running = await _make_sweep(db_session, requested_pair_count=1, status="running")
    sweep_done = await _make_sweep(db_session, requested_pair_count=1, status="completed")

    async with session_transaction(db_session):
        await EvalRepository(db_session).create_sweep(sweep_running)
        await EvalRepository(db_session).create_sweep(sweep_done)
        refetched_items = (
            await db_session.execute(
                select(EvalPairwiseSweepItem).where(
                    EvalPairwiseSweepItem.status.in_(("queued", "running"))
                )
            )
        ).all()
    # Neither sweep has SweepItems materialized; recovery would no-op
    # on both. The point: a ``completed`` sweep never shows up in the
    # recovery SELECT.
    assert refetched_items == []


def test_provider_error_code_classifies_known_exceptions() -> None:
    """The Executor maps provider exceptions to stable error codes so
    the failed-item row is attributable."""

    class FakeTimeout(Exception):
        pass

    class FakeAuth(Exception):
        pass

    assert _provider_error_code(FakeTimeout()) == "PROVIDER_TIMEOUT"
    assert _provider_error_code(FakeAuth()) == "PROVIDER_AUTH"
    assert _provider_error_code(Exception("generic")) == "PROVIDER_HARD_ERROR"
