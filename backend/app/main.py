"""FastAPI application entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent.executor import agent_run_executor
from app.api.router import api_router
from app.core.config import get_settings
from app.core.database import AsyncSessionFactory
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.providers.embedding import build_embedding_provider
from app.providers.llm import build_planning_provider
from app.providers.search import build_search_provider
from app.tools.registry import build_tool_registry


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Recover expired single-worker Runs and cancel local tasks on shutdown."""
    await agent_run_executor.recover_interrupted()
    try:
        yield
    finally:
        await agent_run_executor.shutdown()


def create_app() -> FastAPI:
    """Create and configure one FastAPI application instance."""
    settings = get_settings()
    configure_logging()
    agent_run_executor.set_provider(build_planning_provider(settings))
    embedding_provider = build_embedding_provider(settings)
    agent_run_executor.set_tool_registry(
        build_tool_registry(
            settings=settings,
            session_factory=AsyncSessionFactory,
            embedding_provider=embedding_provider,
            search_provider=build_search_provider(),
        )
    )

    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH"],
        allow_headers=["Accept", "Authorization", "Content-Type", "Idempotency-Key"],
    )
    register_exception_handlers(application)
    application.include_router(api_router)
    return application


app = create_app()
