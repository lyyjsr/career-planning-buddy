"""Command-line entrypoint for the Eval Harness V2.

Invoke as ``python -m evals.v2 run``. The CLI creates (or resumes) an
Experiment, drives its Trials through the real Runtime via
``ExperimentRunner.run_experiment_and_grade``, and prints a single JSON
report line on stdout. Exit codes::

    0   report emitted
    1   execution failed (error envelope printed)
    2   configuration / argument error

The HTTP ``/api/v1/eval/runs`` endpoint is intentionally out of scope --
this entrypoint exists for batch driver runs and local development.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import Settings, get_settings
from app.services.evals import EvalService
from evals.v2.contracts import ExperimentCreate
from evals.v2.dataset_loader import DatasetBundle, filter_cases, load_dataset
from evals.v2.experiment_runner import ExperimentRunner
from evals.v2.runtime_smoke import load_runtime_smoke_dataset

_PROVIDER_MODE_TO_EXECUTION: dict[str, str] = {
    "mock": "mock_provider",
    "fixture": "fixture_provider",
    "live": "live_provider",
}


def _build_dataset(args: argparse.Namespace) -> DatasetBundle:
    if args.dataset == "stage5":
        bundle = load_dataset()
    else:
        bundle = load_runtime_smoke_dataset()
    if args.cases:
        bundle = filter_cases(bundle, list(args.cases))
    return bundle


def _build_config(
    settings: Settings, bundle: DatasetBundle, *, trial_count: int
) -> ExperimentCreate:
    manifest = bundle.manifest
    return ExperimentCreate(
        dataset_id=manifest.dataset_id,
        dataset_version=manifest.dataset_version,
        dataset_hash=manifest.source_sha256,
        git_commit="0000000",
        graph_version=settings.agent_graph_version,
        prompt_version="career-plan-v1",
        model_version=settings.llm_model or "mock-v1",
        tool_version="tool-contract-v1",
        context_version="context-v1",
        memory_version="memory-v1",
        execution_mode=_PROVIDER_MODE_TO_EXECUTION[settings.eval_provider_mode],
        variant_role="baseline",
        trial_count=trial_count,
    )


async def _run_experiment(args: argparse.Namespace, settings: Settings) -> dict[str, object]:
    dataset = _build_dataset(args)
    engine = create_async_engine(settings.database_url)
    try:
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            if args.experiment_id:
                experiment_id = UUID(args.experiment_id)
            else:
                config = _build_config(settings, dataset, trial_count=args.trial_count)
                experiment, _ = await EvalService(session).create_experiment(
                    dataset=dataset, config=config
                )
                experiment_id = experiment.id
                await session.commit()

        runner = ExperimentRunner(session_factory=session_factory, settings=settings)
        report = await runner.run_experiment_and_grade(
            experiment_id, dataset, grade=not args.no_grade
        )
        return report.to_dict()
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="python -m evals.v2",
        description="Eval Harness V2 batch driver.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    run_p = sub.add_parser("run", help="Run an eval experiment end-to-end.")
    run_p.add_argument(
        "--dataset",
        choices=["stage5", "runtime-smoke"],
        default="stage5",
        help="Dataset to load (default: stage5).",
    )
    run_p.add_argument(
        "--cases",
        nargs="*",
        default=None,
        help="Subset of case_ids to keep (default: all cases in the dataset).",
    )
    run_p.add_argument(
        "--provider-mode",
        choices=["mock", "fixture", "live"],
        default=None,
        help="Override settings.eval_provider_mode for this run.",
    )
    run_p.add_argument(
        "--trial-count",
        type=int,
        default=1,
        help="Number of Trials per case (>=1).",
    )
    run_p.add_argument(
        "--no-grade",
        action="store_true",
        help="Skip the grading phase after executing Trials.",
    )
    run_p.add_argument(
        "--experiment-id",
        type=str,
        default=None,
        help="Resume an existing Experiment instead of creating a new one.",
    )
    args = parser.parse_args()

    if args.cmd == "run":
        try:
            settings = get_settings()
        except ValidationError as exc:
            print(
                json.dumps(
                    {
                        "status": "configuration_error",
                        "error_type": type(exc).__name__,
                        "details": exc.errors(),
                    }
                )
            )
            return 2

        if args.provider_mode is not None:
            settings = settings.model_copy(
                update={"eval_provider_mode": args.provider_mode}
            )
    else:
        return 2

    try:
        result = asyncio.run(_run_experiment(args, settings))
    except Exception as exc:  # noqa: BLE001 -- CLI boundary must print JSON.
        payload: dict[str, object] = {
            "status": "failed",
            "error_code": getattr(exc, "code", "EVAL_RUN_FAILED"),
            "error_type": type(exc).__name__,
            "message": str(exc),
        }
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 1

    result["checked_at"] = datetime.now(UTC).isoformat()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
