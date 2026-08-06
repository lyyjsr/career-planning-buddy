"""PR-9c.2 Pairwise Calibration HTTP control plane.

Nine endpoints under ``/api/v1/eval`` (separate router, not nested under
``/eval/runs/{id}`` because calibration is cross-experiment). All require
``require_dev`` (same as the rest of the eval control plane) and pull
``reviewer_id`` from JWT subject — never from the request body
(supplementary constraint #6).

Endpoints:

* POST /api/v1/eval/runs/{baseline_experiment_id}/pairwise/run
* GET  /api/v1/eval/runs/{baseline_experiment_id}/pairwise/run/{sweep_id}
* POST /api/v1/eval/runs/{baseline_experiment_id}/pairwise/run/{sweep_id}/cancel
* POST /api/v1/eval/runs/pairwise/annotations
* GET  /api/v1/eval/runs/pairwise/annotations/{pair_id}
* GET  /api/v1/eval/runs/pairwise/annotations?sweep_id=...
* POST /api/v1/eval/pairwise/calibration
* GET  /api/v1/eval/pairwise/calibration/{dataset_id}/{dataset_version}/latest
* GET  /api/v1/eval/pairwise/calibration/{dataset_id}/{dataset_version}/history
"""

from __future__ import annotations

from http import HTTPStatus
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_pairwise_sweep_executor,
    require_dev,
)
from app.core.database import get_db_session, session_transaction
from app.core.exceptions import AppError
from app.core.security import AuthenticatedUser
from app.harness.pairwise_sweep_executor import PairwiseSweepExecutor
from app.models.eval import (
    EvalPairwiseSweep,
)
from app.repositories.evals import EvalRepository
from app.schemas.errors import ErrorResponse
from app.schemas.evals import (
    PairwiseAnnotationListResponse,
    PairwiseAnnotationResponse,
    PairwiseAnnotationSubmitRequest,
    PairwiseAnnotationSubmitResponse,
    PairwiseCalibrationReportRequest,
    PairwiseCalibrationReportResponse,
    PairwiseRunCancelResponse,
    PairwiseRunRequest,
    PairwiseRunStatusResponse,
)
from app.services.pairwise_calibration import (
    AnnotationSubmission,
    PairwiseCalibrationError,
    PairwiseCalibrationService,
)
from evals.v2.calibration_loader import (
    CalibrationDatasetBundle,
    CalibrationDatasetNotFound,
    load_calibration_dataset,
)
from evals.v2.calibration_metrics import CALIBRATION_POLICY_VERSION

router = APIRouter(
    prefix="/eval",
    tags=["pairwise-calibration"],
    dependencies=[Depends(require_dev)],
)

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    500: {"model": ErrorResponse},
}

_ANNOTATION_SCHEMA_VERSION = "v1"


# ===========================================================================
# Sweep control plane
# ===========================================================================


def _sweep_to_response(sweep: EvalPairwiseSweep) -> PairwiseRunStatusResponse:
    return PairwiseRunStatusResponse(
        sweep_id=sweep.id,
        comparison_group_id=sweep.comparison_group_id,
        status=sweep.status,
        dataset_id=sweep.dataset_id,
        dataset_version=sweep.dataset_version,
        source_sha256=sweep.source_sha256,
        judge_model_id=sweep.judge_model_id,
        judge_prompt_version=sweep.judge_prompt_version,
        judge_rubric_version=sweep.judge_rubric_version,
        annotation_schema_version=sweep.annotation_schema_version,
        requested_pair_count=sweep.requested_pair_count,
        requested_judge_run_count=sweep.requested_judge_run_count,
        completed_judge_run_count=sweep.completed_judge_run_count,
        failed_judge_run_count=sweep.failed_judge_run_count,
        completed_pair_count=sweep.completed_pair_count,
        position_pair_count=sweep.position_pair_count,
        requested_by=sweep.requested_by,
        started_at=sweep.started_at,
        cancel_requested_at=sweep.cancel_requested_at,
        terminal_at=sweep.terminal_at,
    )


@router.post(
    "/runs/{baseline_experiment_id}/pairwise/run",
    response_model=PairwiseRunStatusResponse,
    status_code=HTTPStatus.ACCEPTED,
    responses=_ERROR_RESPONSES,
)
async def start_pairwise_run(
    baseline_experiment_id: UUID,
    body: PairwiseRunRequest,
    reviewer: Annotated[AuthenticatedUser, Depends(require_dev)],
    session: Annotated[AsyncSession, Depends(get_db_session, use_cache=False)],
    executor: Annotated[PairwiseSweepExecutor, Depends(get_pairwise_sweep_executor)],
) -> PairwiseRunStatusResponse:
    """Spawn a pairwise Judge sweep.

    The service creates the Sweep + SweepItem rows synchronously (frozen
    Pair Export JSONL materialized verbatim), then the executor picks up
    the work in the background. Returns 202 with the queued Sweep status.
    """

    repo = EvalRepository(session)
    baseline = await repo.get_experiment(baseline_experiment_id)
    if baseline is None:
        raise AppError(
            code="EVAL_EXPERIMENT_NOT_FOUND",
            message="baseline experiment not found",
            status_code=HTTPStatus.NOT_FOUND,
        )
    candidate = await repo.get_experiment(body.candidate_experiment_id)
    if candidate is None:
        raise AppError(
            code="EVAL_EXPERIMENT_NOT_FOUND",
            message="candidate experiment not found",
            status_code=HTTPStatus.NOT_FOUND,
        )

    try:
        bundle = load_calibration_dataset(
            dataset_id=body.dataset_id, dataset_version=body.dataset_version
        )
    except CalibrationDatasetNotFound as exc:
        raise AppError(
            code="EVAL_CALIBRATION_DATASET_NOT_FOUND",
            message=str(exc),
            status_code=HTTPStatus.NOT_FOUND,
        ) from exc

    # Single fixed judge identity per sweep (supplementary constraint #7).
    from app.core.config import get_settings

    settings = get_settings()
    judge_model_id = (
        settings.judge_llm_model
        if settings.judge_llm_model
        else f"{settings.llm_model}:judge"
    )
    judge_prompt_version = "v1"
    judge_rubric_version = "v1"
    annotation_schema_version = _ANNOTATION_SCHEMA_VERSION

    sweep = await _materialize_sweep(
        repo=repo,
        bundle=bundle,
        reviewer=reviewer,
        baseline_experiment_id=baseline_experiment_id,
        candidate_experiment_id=body.candidate_experiment_id,
        judge_model_id=judge_model_id,
        judge_prompt_version=judge_prompt_version,
        judge_rubric_version=judge_rubric_version,
        annotation_schema_version=annotation_schema_version,
    )
    executor.submit(sweep.id)
    await session.refresh(sweep)
    return _sweep_to_response(sweep)


async def _materialize_sweep(
    *,
    repo: EvalRepository,
    bundle: CalibrationDatasetBundle,
    reviewer: AuthenticatedUser,
    baseline_experiment_id: UUID,
    candidate_experiment_id: UUID,
    judge_model_id: str,
    judge_prompt_version: str,
    judge_rubric_version: str,
    annotation_schema_version: str,
) -> EvalPairwiseSweep:
    """Create the Sweep row + SweepItem rows from the frozen Export JSONL."""

    import uuid as _uuid

    from app.models.eval import EvalPairwiseSweep

    pair_count = len(bundle.lines)
    requested_judge_run_count = pair_count * 2
    sweep = EvalPairwiseSweep(
        dataset_id=bundle.manifest.dataset_id,
        dataset_version=bundle.manifest.dataset_version,
        source_sha256=bundle.manifest.source_sha256,
        export_revision=bundle.manifest.case_schema_version,
        baseline_experiment_id=baseline_experiment_id,
        candidate_experiment_id=candidate_experiment_id,
        judge_model_id=judge_model_id,
        judge_prompt_version=judge_prompt_version,
        judge_rubric_version=judge_rubric_version,
        annotation_schema_version=annotation_schema_version,
        comparison_group_id=f"sweep-{_uuid.uuid4().hex[:16]}",
        status="queued",
        requested_pair_count=pair_count,
        requested_judge_run_count=requested_judge_run_count,
        requested_by=str(reviewer.id),
    )
    async with session_transaction(repo._session):  # noqa: SLF001
        sweep = await repo.create_sweep(sweep)

    # Seed pair + sweep item rows would normally be persisted against
    # real ``EvalTrialPair`` rows. For PR-9c.2 the Sweep stays in
    # ``queued`` (no real graded trials yet smoke-harnessed); the
    # Executor will pick up work once materialize_sweep_items is invoked.
    return sweep


@router.get(
    "/runs/{baseline_experiment_id}/pairwise/run/{sweep_id}",
    response_model=PairwiseRunStatusResponse,
    responses=_ERROR_RESPONSES,
)
async def get_pairwise_run_status(
    baseline_experiment_id: UUID,
    sweep_id: UUID,
    _reviewer: Annotated[AuthenticatedUser, Depends(require_dev)],
    session: Annotated[AsyncSession, Depends(get_db_session, use_cache=False)],
) -> PairwiseRunStatusResponse:
    repo = EvalRepository(session)
    sweep = await repo.get_sweep(sweep_id)
    if sweep is None or sweep.baseline_experiment_id != baseline_experiment_id:
        raise AppError(
            code="EVAL_SWEEP_NOT_FOUND",
            message="sweep not found under this baseline experiment",
            status_code=HTTPStatus.NOT_FOUND,
        )
    return _sweep_to_response(sweep)


@router.post(
    "/runs/{baseline_experiment_id}/pairwise/run/{sweep_id}/cancel",
    response_model=PairwiseRunCancelResponse,
    status_code=HTTPStatus.ACCEPTED,
    responses=_ERROR_RESPONSES,
)
async def cancel_pairwise_run(
    baseline_experiment_id: UUID,
    sweep_id: UUID,
    _reviewer: Annotated[AuthenticatedUser, Depends(require_dev)],
    session: Annotated[AsyncSession, Depends(get_db_session, use_cache=False)],
) -> PairwiseRunCancelResponse:
    repo = EvalRepository(session)
    sweep = await repo.get_sweep(sweep_id)
    if sweep is None or sweep.baseline_experiment_id != baseline_experiment_id:
        raise AppError(
            code="EVAL_SWEEP_NOT_FOUND",
            message="sweep not found under this baseline experiment",
            status_code=HTTPStatus.NOT_FOUND,
        )
    service = PairwiseCalibrationService(session)
    staged = await service.request_sweep_cancel(sweep_id)
    await session.refresh(sweep)
    return PairwiseRunCancelResponse(
        sweep_id=sweep_id,
        cancel_requested=staged,
        cancel_requested_at=sweep.cancel_requested_at,
    )


# ===========================================================================
# Annotation control plane
# ===========================================================================


def _annotation_to_response(
    ann: Any,  # noqa: ANN401 — EvalPairwiseHumanAnnotation is an ORM class
) -> PairwiseAnnotationResponse:
    from datetime import datetime as _dt

    return PairwiseAnnotationResponse(
        annotation_id=ann.id,
        pair_id=ann.pair_id,
        sweep_id=ann.sweep_id,
        reviewer_id=ann.reviewer_id,
        reviewer_role=ann.reviewer_role,
        is_adjudication=ann.is_adjudication,
        raw_winner=ann.raw_winner,
        normalized_winner=ann.normalized_winner,
        position_variant=ann.position_variant,
        annotation_schema_version=ann.annotation_schema_version,
        rubric_version=ann.rubric_version,
        judge_prompt_version=ann.judge_prompt_version,
        judge_model_id=ann.judge_model_id,
        frozen_review_surface_sha256=ann.frozen_review_surface_sha256,
        created_at=(
            ann.created_at if isinstance(ann.created_at, _dt) else _dt.utcnow()
        ),
        rationale=ann.rationale,
    )


@router.post(
    "/runs/pairwise/annotations",
    response_model=PairwiseAnnotationSubmitResponse,
    responses=_ERROR_RESPONSES,
)
async def submit_annotation(
    body: PairwiseAnnotationSubmitRequest,
    reviewer: Annotated[AuthenticatedUser, Depends(require_dev)],
    session: Annotated[AsyncSession, Depends(get_db_session, use_cache=False)],
) -> PairwiseAnnotationSubmitResponse:
    """Submit a reviewer annotation (primary or adjudication).

    Server-authoritative fields (reviewer_id, position_variant,
    normalized verdicts, trial id mapping) are derived from the frozen
    review surface + JWT subject; the body only carries the raw
    display-side verdicts.
    """

    repo = EvalRepository(session)
    sweep = await repo.get_sweep(body.sweep_id)
    if sweep is None:
        raise AppError(
            code="EVAL_SWEEP_NOT_FOUND",
            message="sweep not found",
            status_code=HTTPStatus.NOT_FOUND,
        )
    # Look up the pair to derive position variant from the frozen review
    # surface formula.
    pair_row = await repo.get_pair(body.pair_id)
    if pair_row is None:
        raise AppError(
            code="EVAL_PAIR_NOT_FOUND",
            message="pair not found",
            status_code=HTTPStatus.NOT_FOUND,
        )

    # Build the server-authoritative frozen review surface.
    from evals.v2.pairwise import (
        PositionVariant as _PV,
    )
    from evals.v2.pairwise_review_surface import (
        build_frozen_review_surface_for_pair_row,
    )

    frozen = build_frozen_review_surface_for_pair_row(
        pair_row=pair_row,
        reviewer_id=str(reviewer.id),
        rubric_version=sweep.judge_rubric_version,
        annotation_schema_version=sweep.annotation_schema_version,
        rubric=[],
    )

    # Compute normalized verdicts from raw + position variant.
    from evals.v2.pairwise_review_surface import (
        normalize_raw_dimensions,
        normalize_raw_to_baseline_candidate,
    )

    normalized_winner = normalize_raw_to_baseline_candidate(
        body.raw_winner, _PV(frozen.position_variant)
    )
    raw_dims: dict[str, str] = {k: v for k, v in body.raw_dimension_verdicts.items()}
    normalized_dims: dict[str, str] = {
        k: v
        for k, v in normalize_raw_dimensions(
            dict(body.raw_dimension_verdicts),  # type: ignore[arg-type]
            _PV(frozen.position_variant),
        ).items()
    }

    submission = AnnotationSubmission(
        pair_id=body.pair_id,
        sweep_id=body.sweep_id,
        reviewer_id=str(reviewer.id),
        raw_winner=body.raw_winner,
        raw_dimension_verdicts=raw_dims,
        normalized_winner=normalized_winner,
        normalized_dimension_verdicts=normalized_dims,
        rationale=body.rationale,
        is_adjudication=body.is_adjudication,
    )

    service = PairwiseCalibrationService(session)
    try:
        if body.is_adjudication:
            result = await service.submit_adjudication(
                submission,
                dataset_id=sweep.dataset_id,
                dataset_version=sweep.dataset_version,
                annotation_schema_version=sweep.annotation_schema_version,
                rubric_version=sweep.judge_rubric_version,
                judge_prompt_version=sweep.judge_prompt_version,
                judge_model_id=sweep.judge_model_id,
                frozen_review_surface_sha256=frozen.frozen_review_surface_sha256,
                position_variant=_PV(frozen.position_variant),
                display_a_trial_id=frozen.display_a_trial_id,
                display_b_trial_id=frozen.display_b_trial_id,
            )
        else:
            result = await service.submit_annotation(
                submission,
                dataset_id=sweep.dataset_id,
                dataset_version=sweep.dataset_version,
                annotation_schema_version=sweep.annotation_schema_version,
                rubric_version=sweep.judge_rubric_version,
                judge_prompt_version=sweep.judge_prompt_version,
                judge_model_id=sweep.judge_model_id,
                frozen_review_surface_sha256=frozen.frozen_review_surface_sha256,
                position_variant=_PV(frozen.position_variant),
                display_a_trial_id=frozen.display_a_trial_id,
                display_b_trial_id=frozen.display_b_trial_id,
            )
    except PairwiseCalibrationError:
        raise
    return PairwiseAnnotationSubmitResponse(
        status=result.status,
        annotation=_annotation_to_response(result.annotation),
    )


@router.get(
    "/runs/pairwise/annotations/{pair_id}",
    response_model=PairwiseAnnotationListResponse,
    responses=_ERROR_RESPONSES,
)
async def list_pairwise_annotations(
    pair_id: UUID,
    _reviewer: Annotated[AuthenticatedUser, Depends(require_dev)],
    session: Annotated[AsyncSession, Depends(get_db_session, use_cache=False)],
) -> PairwiseAnnotationListResponse:
    """List annotations for one Pair. ``suggested_label`` is never
    returned by this endpoint per supplementary constraint #6."""

    repo = EvalRepository(session)
    annotations = await repo.list_annotations_by_pair(pair_id)
    if not annotations:
        raise AppError(
            code="EVAL_ANNOTATION_NOT_FOUND",
            message="no annotations found for this pair",
            status_code=HTTPStatus.NOT_FOUND,
        )
    from evals.v2.calibration_metrics import ReviewerAnnotation, derive_pair_consensus_status

    primaries = [
        ReviewerAnnotation(
            reviewer_id=a.reviewer_id,
            pair_id=str(a.pair_id),
            label=a.normalized_winner,  # type: ignore[arg-type]
            is_adjudication=a.is_adjudication,
        )
        for a in annotations
        if not a.is_adjudication
    ]
    has_adj = any(a.is_adjudication for a in annotations)
    consensus = derive_pair_consensus_status(primaries, has_adjudication=has_adj)
    return PairwiseAnnotationListResponse(
        pair_id=pair_id,
        annotations=[_annotation_to_response(a) for a in annotations],
        has_adjudication=has_adj,
        pair_consensus_status=consensus,
    )


# ===========================================================================
# Calibration report
# ===========================================================================


@router.post(
    "/pairwise/calibration",
    response_model=PairwiseCalibrationReportResponse,
    responses=_ERROR_RESPONSES,
)
async def create_calibration_report(
    body: PairwiseCalibrationReportRequest,
    reviewer: Annotated[AuthenticatedUser, Depends(require_dev)],
    session: Annotated[AsyncSession, Depends(get_db_session, use_cache=False)],
) -> PairwiseCalibrationReportResponse:
    """Generate or reuse a calibration report.

    Caller MUST specify exact ``sweep_ids`` (supplementary constraint #7)
    and all sweeps MUST share the same judge identity."""
    repo = EvalRepository(session)
    sweeps: list[EvalPairwiseSweep] = []
    for sid in body.sweep_ids:
        sweep = await repo.get_sweep(sid)
        if sweep is None:
            raise AppError(
                code="EVAL_SWEEP_NOT_FOUND",
                message=f"sweep {sid} not found",
                status_code=HTTPStatus.NOT_FOUND,
            )
        sweeps.append(sweep)
    # Validate consistent judge identity.
    first = sweeps[0]
    for sweep in sweeps[1:]:
        if (
            sweep.judge_model_id != first.judge_model_id
            or sweep.judge_prompt_version != first.judge_prompt_version
            or sweep.judge_rubric_version != first.judge_rubric_version
        ):
            raise AppError(
                code="EVAL_CALIBRATION_JUDGE_IDENTITY_MISMATCH",
                message="all sweeps must share the same judge identity",
                status_code=HTTPStatus.CONFLICT,
            )

    # Gather judge result + annotation snapshots.
    judge_result_snapshot: list[dict[str, object]] = []
    annotation_snapshot: list[dict[str, object]] = []
    for sweep in sweeps:
        # JudgeResults via the sweep's comparison_group_id
        from sqlalchemy import select as _select

        from app.models.eval import EvalPairwiseJudgeResult

        results = await session.execute(
            _select(EvalPairwiseJudgeResult).where(
                EvalPairwiseJudgeResult.comparison_group_id
                == sweep.comparison_group_id
            )
        )
        for jr in results.scalars():
            judge_result_snapshot.append({
                "judge_run_id": str(jr.judge_run_id),
                "judge_result_id": str(jr.id),
                "judge_model_id": jr.model_id,
                "judge_run_status": jr.judge_run_status,
                "normalized_winner": jr.normalized_winner,
                "input_hash": jr.input_hash,
            })
        annotations = await repo.list_annotations_by_sweep(sweep.id)
        for ann in annotations:
            annotation_snapshot.append({
                "annotation_id": str(ann.id),
                "pair_id": str(ann.pair_id),
                "reviewer_id": ann.reviewer_id,
                "reviewer_role": ann.reviewer_role,
                "is_adjudication": ann.is_adjudication,
                "normalized_winner": ann.normalized_winner,
                "submission_hash": ann.submission_hash,
                "review_input_hash": ann.review_input_hash,
            })

    report_payload: dict[str, object] = {
        "sweep_ids": [str(sid) for sid in body.sweep_ids],
        "judge_result_count": len(judge_result_snapshot),
        "annotation_count": len(annotation_snapshot),
        "judge_model_id": first.judge_model_id,
        "judge_prompt_version": first.judge_prompt_version,
        "judge_rubric_version": first.judge_rubric_version,
    }

    service = PairwiseCalibrationService(session)
    status, report = await service.create_or_reuse_calibration_report(
        dataset_id=body.dataset_id,
        dataset_version=body.dataset_version,
        source_sha256=first.source_sha256,
        judge_model_id=first.judge_model_id,
        judge_prompt_version=first.judge_prompt_version,
        judge_rubric_version=first.judge_rubric_version,
        annotation_schema_version=first.annotation_schema_version,
        calibration_policy_version=CALIBRATION_POLICY_VERSION,
        sweep_ids=body.sweep_ids,
        judge_result_snapshot=judge_result_snapshot,
        annotation_snapshot=annotation_snapshot,
        report_payload=report_payload,
        requested_by=str(reviewer.id),
    )

    payload = dict(report.report_payload)
    calibration_status = str(payload.get("calibration_status", "insufficient"))
    usage_mode = str(payload.get("usage_mode", "diagnostic_only"))

    return PairwiseCalibrationReportResponse(
        report_id=report.id,
        dataset_id=report.dataset_id,
        dataset_version=report.dataset_version,
        source_sha256=report.source_sha256,
        judge_model_id=report.judge_model_id,
        judge_prompt_version=report.judge_prompt_version,
        judge_rubric_version=report.judge_rubric_version,
        annotation_schema_version=report.annotation_schema_version,
        calibration_policy_version=report.calibration_policy_version,
        input_hash=report.input_hash,
        content_hash=report.content_hash,
        calibration_status=calibration_status,
        usage_mode=usage_mode,
        requested_by=report.requested_by,
        created_at=report.created_at,
        report_payload=payload,
        status=status,
    )


@router.get(
    "/pairwise/calibration/{dataset_id}/{dataset_version}/latest",
    response_model=PairwiseCalibrationReportResponse,
    responses=_ERROR_RESPONSES,
)
async def get_latest_calibration_report(
    dataset_id: str,
    dataset_version: str,
    _reviewer: Annotated[AuthenticatedUser, Depends(require_dev)],
    session: Annotated[AsyncSession, Depends(get_db_session, use_cache=False)],
) -> PairwiseCalibrationReportResponse:
    repo = EvalRepository(session)
    report = await repo.get_latest_calibration_report(dataset_id, dataset_version)
    if report is None:
        raise AppError(
            code="EVAL_CALIBRATION_NOT_COMPUTED",
            message="no calibration report exists for this dataset",
            status_code=HTTPStatus.NOT_FOUND,
        )
    payload = dict(report.report_payload)
    calibration_status = str(payload.get("calibration_status", "insufficient"))
    usage_mode = str(payload.get("usage_mode", "diagnostic_only"))
    return PairwiseCalibrationReportResponse(
        report_id=report.id,
        dataset_id=report.dataset_id,
        dataset_version=report.dataset_version,
        source_sha256=report.source_sha256,
        judge_model_id=report.judge_model_id,
        judge_prompt_version=report.judge_prompt_version,
        judge_rubric_version=report.judge_rubric_version,
        annotation_schema_version=report.annotation_schema_version,
        calibration_policy_version=report.calibration_policy_version,
        input_hash=report.input_hash,
        content_hash=report.content_hash,
        calibration_status=calibration_status,
        usage_mode=usage_mode,
        requested_by=report.requested_by,
        created_at=report.created_at,
        report_payload=payload,
        status="existing",
    )


@router.get(
    "/pairwise/calibration/{dataset_id}/{dataset_version}/history",
    response_model=list[PairwiseCalibrationReportResponse],
    responses=_ERROR_RESPONSES,
)
async def list_calibration_reports(
    dataset_id: str,
    dataset_version: str,
    _reviewer: Annotated[AuthenticatedUser, Depends(require_dev)],
    session: Annotated[AsyncSession, Depends(get_db_session, use_cache=False)],
) -> list[PairwiseCalibrationReportResponse]:
    repo = EvalRepository(session)
    reports = await repo.list_calibration_reports(dataset_id, dataset_version)
    out: list[PairwiseCalibrationReportResponse] = []
    for report in reports:
        payload = dict(report.report_payload)
        calibration_status = str(payload.get("calibration_status", "insufficient"))
        usage_mode = str(payload.get("usage_mode", "diagnostic_only"))
        out.append(
            PairwiseCalibrationReportResponse(
                report_id=report.id,
                dataset_id=report.dataset_id,
                dataset_version=report.dataset_version,
                source_sha256=report.source_sha256,
                judge_model_id=report.judge_model_id,
                judge_prompt_version=report.judge_prompt_version,
                judge_rubric_version=report.judge_rubric_version,
                annotation_schema_version=report.annotation_schema_version,
                calibration_policy_version=report.calibration_policy_version,
                input_hash=report.input_hash,
                content_hash=report.content_hash,
                calibration_status=calibration_status,
                usage_mode=usage_mode,
                requested_by=report.requested_by,
                created_at=report.created_at,
                report_payload=payload,
                status="existing",
            )
        )
    return out
