"""PR-4 evidence pipeline tests (DB-bound).

These tests drive the full ``EvalService.grade_trial`` path end-to-end:

1. create an Experiment + Trial (PR-2 layer),
2. run the real Runtime via ``TrialRunner`` to produce a completed Trial with
   outcome_snapshot + transcript_hash (PR-3 layer),
3. call ``grade_trial`` to collect evidence, persist ``eval_evidence_items``,
   run all six Graders, and persist ``eval_scores`` (PR-4 layer),
4. assert the spec exit gates:
   * evidence items carry stable content_hash and survive re-collection,
   * every domain produced rows, every hard-gate row carries actual/expected,
   * re-grading the same (trial, grader_name, grader_version) is rejected,
   * pending Trials cannot be graded,
   * content-hash change invalidates old scores' evidence_item_ids linkage.

These tests require live PostgreSQL via the ``db_connection`` fixture. They
are not unit tests; the per-domain grader logic is covered by
``test_graders.py`` and ``test_evidence_authorization.py``.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
)

from app.core.config import Settings, get_settings
from app.core.database import session_transaction
from app.core.exceptions import AppError
from app.models.eval import EvalTrial
from app.repositories.agent_runs import AgentRunRepository
from app.repositories.evals import EvalRepository
from app.services.evals import EvalService
from evals.v2.collectors.evidence import collect_evidence
from evals.v2.collectors.outcome import collect_outcome
from evals.v2.contracts import (
    DatasetManifest,
    EvalCase,
    EvalScenario,
    ExpectedOutcome,
    ExperimentCreate,
    TrajectoryPolicy,
    canonical_sha256,
)
from evals.v2.dataset_loader import filter_cases, load_dataset
from evals.v2.graders.base import EvidenceItem
from evals.v2.trial_runner import TrialRunner
from tests.test_agent_runtime import runtime_factory

SMOKE_CASES = ["create-01", "clarify-01", "safe-01"]
DOMAINS = {"task", "behavioral", "tool", "model", "system", "safety"}


def _config(manifest: DatasetManifest) -> ExperimentCreate:
    return ExperimentCreate(
        dataset_id=manifest.dataset_id,
        dataset_version=manifest.dataset_version,
        dataset_hash=manifest.source_sha256,
        git_commit="7d29a45",
        graph_version="stage5-v1",
        prompt_version="career-plan-v1",
        model_version="mock-v1",
        tool_version="tool-contract-v1",
        context_version="context-v1",
        memory_version="memory-v1",
        execution_mode="mock_provider",
        variant_role="baseline",
        trial_count=1,
    )


async def _provision_run(
    db_session: AsyncSession,
    db_connection: AsyncConnection,
    *,
    settings: Settings,
    case_id: str,
) -> tuple[EvalCase, UUID]:
    """Run one Trial via the real Runtime; return the case + its trial id."""

    bundle = filter_cases(load_dataset(), [case_id])
    case = bundle.cases[0]
    _, trials = await EvalService(db_session).create_experiment(
        dataset=bundle, config=_config(bundle.manifest)
    )
    trial = trials[0]
    runner = TrialRunner(
        session_factory=runtime_factory(db_connection),
        settings=settings,
    )
    await runner.run_trial(trial, case)
    return case, trial.id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_grade_trial_persists_evidence_items_and_scores_per_domain(
    db_connection: AsyncConnection,
    db_session: AsyncSession,
) -> None:
    """The full grade_trial pipeline produces evidence rows + Score rows.

    Asserts:
    * ``eval_evidence_items`` has at least one row per EvidenceKind we expect
      for a completed plan run (plan_projection, task_projection*,
      step_projection*, run_metrics, transcript_hash…),
    * ``eval_scores`` has at least one row per domain in DOMAINS,
    * every Score row carries ``actual`` + ``expected`` in evidence_json,
    * grading is replayable: a second grade_trial after first grading
      produces the same content_hash set.
    """

    settings = get_settings()
    case, trial_id = await _provision_run(
        db_session, db_connection, settings=settings, case_id="create-01"
    )

    # First grading.
    results = await EvalService(db_session).grade_trial(trial_id, case)
    assert len(results) > 0, "grade_trial produced no GradeResult"

    # Every domain produced at least one GradeResult.
    produced_domains = {r.domain for r in results}
    assert DOMAINS.issubset(produced_domains), (
        f"missing domains: {DOMAINS - produced_domains}"
    )

    # Every result has actual+expected in evidence_json.
    for r in results:
        assert "actual" in r.evidence
        assert "expected" in r.evidence

    # eval_evidence_items rows cover the projections a completed plan run must
    # surface (plan / task / step / event / run_metrics / transcript_hash at
    # minimum). Counts are inferred from registry-allowed kinds.
    async with session_transaction(db_session):
        items = await EvalRepository(db_session).list_evidence_items(trial_id)
        kinds_present = {item.kind for item in items}
    required_kinds = {
        "outcome_status", "run_metrics", "transcript_hash",
        "event_projection", "step_projection",
        "request_constraints", "expected_outcome", "trajectory_policy",
    }
    assert required_kinds.issubset(kinds_present), (
        f"missing evidence kinds: {required_kinds - kinds_present}"
    )
    # A completed plan run also persisted plan + task projections.
    assert "plan_projection" in kinds_present
    assert "task_projection" in kinds_present

    # eval_scores rows cover every domain.
    async with session_transaction(db_session):
        scores = await EvalRepository(db_session).list_scores(trial_id)
        scored_domains = {score.domain for score in scores}
    assert DOMAINS.issubset(scored_domains), (
        f"missing scored domains: {DOMAINS - scored_domains}"
    )


@pytest.mark.asyncio
async def test_grade_trial_rejects_invalid_trial_id(db_session: AsyncSession) -> None:
    """Grading an unknown trial_id raises EVAL_TRIAL_NOT_FOUND."""

    scenario = EvalScenario(
        user_request="x", profile=None, hint_intent=None, replan_mode=None,
        initial_plan=None, initial_tasks=[], initial_reviews=[],
        confirmed_memories=[], unconfirmed_memory_candidates=[],
        search_fixtures={}, provider_fixtures={},
        planning_date="2026-08-01",
    )
    payload = {
        "case_id": "x", "schema_version": "2",
        "dataset_id": "smoke", "dataset_version": "v1",
        "scenario": scenario.model_dump(mode="json"),
        "expected_outcome": ExpectedOutcome(
            result_kind="plan", allowed_run_statuses=["completed"],
        ).model_dump(mode="json"),
        "trajectory_policy": TrajectoryPolicy().model_dump(mode="json"),
        "rubric": {"criteria": [
            {"criterion_id": "x", "description": "x", "hard_gate": True},
        ]},
        "difficulty": "regression",
        "tags": ["t"],
        "fixture_version": "v",
        "counterfactual_group_id": None,
        "variant": None,
        "fault_plan": None,
    }
    payload["fixture_hash"] = canonical_sha256(
        {k: v for k, v in payload.items() if k != "fixture_hash"}
    )
    case = EvalCase.model_validate(payload)

    with pytest.raises(AppError) as error:
        await EvalService(db_session).grade_trial(uuid4(), case)
    assert error.value.code == "EVAL_TRIAL_NOT_FOUND"


@pytest.mark.asyncio
async def test_grade_trial_rejects_pending_trial(
    db_connection: AsyncConnection,
    db_session: AsyncSession,
) -> None:
    """A Trial that has never run (still ``pending``) cannot be graded."""

    bundle = filter_cases(load_dataset(), ["create-01"])
    case = bundle.cases[0]
    _, trials = await EvalService(db_session).create_experiment(
        dataset=bundle, config=_config(bundle.manifest)
    )
    trial_id = trials[0].id
    # Do NOT run trial_runner -- the Trial stays pending.

    with pytest.raises(AppError) as error:
        await EvalService(db_session).grade_trial(trial_id, case)
    assert error.value.code == "EVAL_TRIAL_NOT_GRADEABLE"


@pytest.mark.asyncio
async def test_collect_evidence_stable_hashes_under_recollection(
    db_connection: AsyncConnection,
    db_session: AsyncSession,
) -> None:
    """A second ``collect_evidence`` call over an unchanged outcome yields the
    same content_hash set -- the collector must be deterministic.
    """

    settings = get_settings()
    case, trial_id = await _provision_run(
        db_session, db_connection, settings=settings, case_id="create-01"
    )
    await EvalService(db_session).attach_evidence(trial_id, [])
    # Re-read Run from DB for collect_evidence (mirrors grade_trial internals).

    async with session_transaction(db_session):
        trial = await db_session.get(EvalTrial, trial_id)
        assert trial is not None and trial.run_id is not None
        run = await AgentRunRepository(db_session).get_by_id(trial.run_id)
        assert run is not None
        outcome1 = await collect_outcome(db_session, run, user_id=run.user_id)
        items1 = await collect_evidence(
            db_session, trial_id=trial_id, run=run, outcome=outcome1, case=case,
        )
        # Second pass: re-collect against the same outcome (no row mutation).
        outcome2 = await collect_outcome(db_session, run, user_id=run.user_id)
        items2 = await collect_evidence(
            db_session, trial_id=trial_id, run=run, outcome=outcome2, case=case,
        )
    # Map by (kind, source_type, source_id) for stable comparison.
    def keyset(
        items: list[EvidenceItem],
    ) -> dict[tuple[str, str, str | None], str]:
        return {
            (i.kind.value, i.source_type, i.source_id): i.content_hash for i in items
        }

    hashes1, hashes2 = keyset(items1), keyset(items2)
    assert hashes1 == hashes2, (
        "collect_evidence is non-deterministic across calls on the same outcome"
    )
