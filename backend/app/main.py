"""FastAPI application entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent.eval_executor import eval_runner_executor
from app.agent.executor import agent_run_executor
from app.api.router import api_router
from app.core.config import get_settings
from app.core.database import AsyncSessionFactory
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.harness.pairwise_sweep_executor import pairwise_sweep_executor
from app.providers.registry import build_runtime_provider_registry


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Start durable dispatchers and release local leases on shutdown."""
    await agent_run_executor.recover_interrupted()
    await agent_run_executor.start()
    await eval_runner_executor.recover_interrupted()
    await pairwise_sweep_executor.recover_interrupted()
    try:
        yield
    finally:
        await pairwise_sweep_executor.shutdown()
        await eval_runner_executor.shutdown()
        await agent_run_executor.shutdown()


def create_app() -> FastAPI:
    """Create and configure one FastAPI application instance."""
    settings = get_settings()
    configure_logging()
    providers = build_runtime_provider_registry(
        settings=settings,
        session_factory=AsyncSessionFactory,
    )
    agent_run_executor.set_provider(providers.planning)
    agent_run_executor.set_embedding_provider(providers.embedding)
    agent_run_executor.set_evidence_distillation_provider(providers.evidence_distillation)
    agent_run_executor.set_tool_registry(providers.tools)
    agent_run_executor.configure_dispatcher(
        poll_interval_seconds=settings.agent_poll_interval_seconds,
        heartbeat_seconds=settings.agent_heartbeat_seconds,
        lease_seconds=settings.agent_lease_seconds,
        max_attempts=settings.agent_max_run_attempts,
        worker_concurrency=settings.agent_worker_concurrency,
    )

    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )
    application.state.runtime_providers = providers
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH"],
        allow_headers=[
            "Accept",
            "Authorization",
            "Content-Type",
            "Idempotency-Key",
            "Last-Event-ID",
        ],
    )
    register_exception_handlers(application)
    application.include_router(api_router)
    return application


app = create_app()
