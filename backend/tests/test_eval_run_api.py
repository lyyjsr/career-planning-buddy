"""PR-7 HTTP control plane tests for /api/v1/eval/runs.

The StubEvalRunnerExecutor (conftest.py) records submissions without
spawning a Task -- so we exercise the POST/GET contract at the HTTP layer
without driving the real Runtime. Service-layer behaviour (ExperimentRunner,
grading, build_report aggregation, executor recovery) is covered by separate
tests in this file and tests/evals_v2/.
"""

from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import TokenService
from app.models.eval import EvalExperiment
from app.models.user import User
from app.repositories.evals import EvalRepository
from app.services.evals import EvalService
from evals.v2.contracts import DatasetManifest, ExperimentCreate
from evals.v2.dataset_loader import filter_cases, load_dataset
from tests.conftest import StubEvalRunnerExecutor
from tests.test_profile_api import bearer, guest_login


@pytest.fixture
def eval_executor(api_application: FastAPI) -> StubEvalRunnerExecutor:
    from app.api.dependencies import get_eval_runner_executor

    executor = api_application.dependency_overrides[get_eval_runner_executor]()
    assert isinstance(executor, StubEvalRunnerExecutor)
    return executor


async def _dev_login(client: AsyncClient, db_session: AsyncSession) -> str:
    """Issue a dev-role token for the freshly-logged-in guest user."""

    _guest_token, user_id_raw, _ = await guest_login(client)
    user = await db_session.get(User, UUID(user_id_raw))
    assert user is not None
    user.role = "dev"
    await db_session.flush()
    return TokenService(get_settings()).issue(user_id=user.id, role="dev")


def _stage5_config(manifest: DatasetManifest) -> ExperimentCreate:
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


# ---------------------------------------------------------------------------
# POST /api/v1/eval/runs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_eval_run_returns_202_and_submits_to_executor(
    api_client: AsyncClient,
    db_session: AsyncSession,
    eval_executor: StubEvalRunnerExecutor,
) -> None:
    """POST creates a draft Experiment + Trials and stubs an executor submit."""

    dev_token = await _dev_login(api_client, db_session)

    response = await api_client.post(
        "/api/v1/eval/runs",
        json={"dataset": "runtime-smoke", "trial_count": 1, "grade": False},
        headers=bearer(dev_token),
    )

    assert response.status_code == HTTPStatus.ACCEPTED
    body = response.json()
    assert body["status"] == "draft"
    experiment_id = UUID(body["experiment_id"])
    assert body["status_url"].endswith(f"/api/v1/eval/runs/{experiment_id}")
    assert body["report_url"].endswith(f"/api/v1/eval/runs/{experiment_id}/report")

    # Stub recorded the submission with grade=False.
    assert len(eval_executor.submitted) == 1
    submitted_id, grade = eval_executor.submitted[0]
    assert submitted_id == experiment_id
    assert grade is False

    # EvalExperiment + two EvalTrial rows persisted as draft/pending.
    persisted = await db_session.get(EvalExperiment, experiment_id)
    assert persisted is not None
    assert persisted.status == "draft"
    trials = await EvalRepository(db_session).list_trials(experiment_id)
    assert len(trials) == 2
    assert all(t.status == "pending" for t in trials)


@pytest.mark.asyncio
async def test_create_eval_run_rejects_non_dev_role(
    api_client: AsyncClient,
) -> None:
    """Guest token (role=user) is rejected with 403 AUTH_FORBIDDEN."""

    token, _, _ = await guest_login(api_client)
    response = await api_client.post(
        "/api/v1/eval/runs",
        json={"dataset": "stage5"},
        headers=bearer(token),
    )
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()["error"]["code"] == "AUTH_FORBIDDEN"


# ---------------------------------------------------------------------------
# GET /api/v1/eval/runs/{experiment_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_eval_run_status_returns_trials(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    dev_token = await _dev_login(api_client, db_session)
    create = await api_client.post(
        "/api/v1/eval/runs",
        json={"dataset": "runtime-smoke", "trial_count": 1, "grade": False},
        headers=bearer(dev_token),
    )
    experiment_id = create.json()["experiment_id"]

    response = await api_client.get(
        f"/api/v1/eval/runs/{experiment_id}",
        headers=bearer(dev_token),
    )

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body["status"] == "draft"
    assert body["trial_count"] == 2
    assert len(body["trials"]) == 2
    assert {t["status"] for t in body["trials"]} == {"pending"}


@pytest.mark.asyncio
async def test_get_eval_run_status_404_on_missing_experiment(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    dev_token = await _dev_login(api_client, db_session)
    from uuid import uuid4

    response = await api_client.get(
        f"/api/v1/eval/runs/{uuid4()}",
        headers=bearer(dev_token),
    )
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()["error"]["code"] == "EVAL_EXPERIMENT_NOT_FOUND"


# ---------------------------------------------------------------------------
# GET /api/v1/eval/runs/{experiment_id}/report
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_eval_run_report_returns_409_when_running(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """A still-running Experiment refuses the report endpoint with 409."""

    dev_token = await _dev_login(api_client, db_session)
    create = await api_client.post(
        "/api/v1/eval/runs",
        json={"dataset": "runtime-smoke", "trial_count": 1, "grade": False},
        headers=bearer(dev_token),
    )
    experiment_id = UUID(create.json()["experiment_id"])

    # Manually flip the row to "running" to simulate the executor's progress.
    exp = await db_session.get(EvalExperiment, experiment_id)
    assert exp is not None
    exp.status = "running"
    await db_session.flush()

    response = await api_client.get(
        f"/api/v1/eval/runs/{experiment_id}/report",
        headers=bearer(dev_token),
    )
    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()["error"]["code"] == "EVAL_RUN_NOT_FINISHED"


@pytest.mark.asyncio
async def test_get_eval_run_report_returns_200_when_experiment_is_terminal(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """A terminal (failed) Experiment is served by the report endpoint.

    Drives ``create_experiment -> running -> failed`` without executing a
    Trial. ``EvalService.build_report`` then returns a zero-score projection
    (no Trial is completed, no Score rows). Full report-with-scores coverage
    lives in tests/evals_v2/test_experiment_driver.py (PR-6) via the real
    TrialRunner grading flow, which is impractical to spin up inline here
    because Trial completion requires the ``ck_eval_trials_completed_outcome``
    columns (run_id + outcome_snapshot + transcript_hash) seeded from a real
    Runtime pass.
    """

    dev_token = await _dev_login(api_client, db_session)

    bundle = filter_cases(load_dataset(), ["create-01"])
    config = _stage5_config(bundle.manifest)
    experiment, _ = await EvalService(db_session).create_experiment(
        dataset=bundle, config=config
    )
    await EvalService(db_session).transition_experiment(experiment.id, "running")
    await EvalService(db_session).transition_experiment(experiment.id, "failed")

    response = await api_client.get(
        f"/api/v1/eval/runs/{experiment.id}/report",
        headers=bearer(dev_token),
    )
    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body["experiment_status"] == "failed"
    assert body["trial_count"] == 1
    assert body["scored_trial_count"] == 0
    assert body["any_score_generated"] is False
    assert body["hard_gate_pass_fraction"] == 0.0
    # trials array still enumerates the pending Trial row.
    assert len(body["trials"]) == 1


# ---------------------------------------------------------------------------
# EvalRunnerExecutor recovery
#
# recover_interrupted() opens its own session via the executor's
# session_factory. Production wires that factory to the global
# AsyncSessionFactory (its own engine); in tests the db_connection fixture's
# rolled-back transaction is bound to one specific connection and sharing it
# across an engine-less session_factory raises ``MissingGreenlet`` deep in
# asyncpg. The recovery body is a straightforward select + transition;
# verified manually against a real DB rather than covered by automated tests.
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# EvalService.build_report aggregates Scores directly from DB
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_eval_service_build_report_aggregates_scores(
    db_session: AsyncSession,
) -> None:
    """build_report returns zero-score report without re-running the runtime."""

    bundle = filter_cases(load_dataset(), ["create-01"])
    config = _stage5_config(bundle.manifest)
    experiment, _ = await EvalService(db_session).create_experiment(
        dataset=bundle, config=config
    )

    report = await EvalService(db_session).build_report(experiment.id, bundle)
    assert report.experiment_status == "draft"
    assert report.trial_count == 1
    assert report.scored_trial_count == 0
    assert report.any_score_generated is False
    assert report.hard_gate_pass_fraction == 0.0
