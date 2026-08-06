"""HTTP dependency composition for authentication and services."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.eval_executor import EvalRunnerExecutor, eval_runner_executor
from app.agent.executor import AgentRunExecutor, agent_run_executor
from app.core.config import Settings, get_settings
from app.core.database import get_db_session
from app.core.exceptions import AppError
from app.core.security import AuthenticatedUser, TokenService
from app.harness.pairwise_sweep_executor import (
    PairwiseSweepExecutor,
    pairwise_sweep_executor,
)
from app.providers.embedding import EmbeddingProvider, build_embedding_provider
from app.repositories.users import UserRepository
from app.services.agent_runs import AgentRunService
from app.services.auth import AuthService
from app.services.dev import DevTraceService
from app.services.evals import EvalService
from app.services.memories import MemoryService
from app.services.plans import PlanQueryService
from app.services.profiles import ProfileService
from app.services.reviews import ReviewService

bearer_scheme = HTTPBearer(auto_error=False)


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    return build_embedding_provider(get_settings())


def get_token_service(settings: Annotated[Settings, Depends(get_settings)]) -> TokenService:
    return TokenService(settings)


def get_auth_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    token_service: Annotated[TokenService, Depends(get_token_service)],
) -> AuthService:
    return AuthService(session, token_service)


def get_profile_service(
    session: Annotated[AsyncSession, Depends(get_db_session, use_cache=False)],
) -> ProfileService:
    return ProfileService(session)


def get_agent_run_executor() -> AgentRunExecutor:
    return agent_run_executor


def get_eval_runner_executor() -> EvalRunnerExecutor:
    return eval_runner_executor


def get_pairwise_sweep_executor() -> PairwiseSweepExecutor:
    return pairwise_sweep_executor


def get_agent_run_service(
    session: Annotated[AsyncSession, Depends(get_db_session, use_cache=False)],
    settings: Annotated[Settings, Depends(get_settings)],
    executor: Annotated[AgentRunExecutor, Depends(get_agent_run_executor)],
) -> AgentRunService:
    return AgentRunService(session, settings, executor)


def get_eval_service(
    session: Annotated[AsyncSession, Depends(get_db_session, use_cache=False)],
) -> EvalService:
    return EvalService(session)


def get_plan_query_service(
    session: Annotated[AsyncSession, Depends(get_db_session, use_cache=False)],
) -> PlanQueryService:
    return PlanQueryService(session)


def get_review_service(
    session: Annotated[AsyncSession, Depends(get_db_session, use_cache=False)],
    settings: Annotated[Settings, Depends(get_settings)],
    executor: Annotated[AgentRunExecutor, Depends(get_agent_run_executor)],
) -> ReviewService:
    return ReviewService(session, settings, executor)


def get_memory_service(
    session: Annotated[AsyncSession, Depends(get_db_session, use_cache=False)],
    embedding_provider: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
) -> MemoryService:
    return MemoryService(session, embedding_provider)


def get_dev_trace_service(
    session: Annotated[AsyncSession, Depends(get_db_session, use_cache=False)],
) -> DevTraceService:
    return DevTraceService(session)


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    token_service: Annotated[TokenService, Depends(get_token_service)],
) -> AuthenticatedUser:
    raw_token = (
        credentials.credentials
        if credentials is not None and credentials.scheme.lower() == "bearer"
        else None
    )

    if raw_token is None:
        raise AppError(
            code="AUTH_INVALID_TOKEN",
            message="a valid bearer token is required",
            status_code=401,
        )

    user_id, _token_role = token_service.verify(raw_token)
    user = await UserRepository(session).get_by_id(user_id)
    if user is None or not user.is_active:
        raise AppError(
            code="AUTH_INVALID_TOKEN",
            message="a valid bearer token is required",
            status_code=401,
        )
    return AuthenticatedUser(
        id=user.id,
        display_name=user.display_name,
        role=user.role,
    )


async def require_dev(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> AuthenticatedUser:
    """Restrict developer diagnostics to the persisted dev role."""
    if current_user.role != "dev":
        raise AppError(
            code="AUTH_FORBIDDEN",
            message="developer role is required",
            status_code=403,
        )
    return current_user
