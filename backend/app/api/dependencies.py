"""HTTP dependency composition for authentication and services."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.executor import AgentRunExecutor, agent_run_executor
from app.core.config import Settings, get_settings
from app.core.database import get_db_session
from app.core.exceptions import AppError
from app.core.security import AuthenticatedUser, TokenService
from app.providers.embedding import EmbeddingProvider, build_embedding_provider
from app.repositories.users import UserRepository
from app.services.agent_runs import AgentRunService
from app.services.auth import AuthService
from app.services.dev import DevTraceService
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


def get_agent_run_service(
    session: Annotated[AsyncSession, Depends(get_db_session, use_cache=False)],
    settings: Annotated[Settings, Depends(get_settings)],
    executor: Annotated[AgentRunExecutor, Depends(get_agent_run_executor)],
) -> AgentRunService:
    return AgentRunService(session, settings, executor)


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
    request: Annotated[Request, "request"],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    token_service: Annotated[TokenService, Depends(get_token_service)],
) -> AuthenticatedUser:
    raw_token: str | None = None
    if credentials is not None and credentials.scheme.lower() == "bearer":
        raw_token = credentials.credentials
    else:
        # SSE 端点（EventSource 无法设置 Header）通过 query 参数 ?access_token= 发凭证
        query_token = request.query_params.get("access_token")
        if isinstance(query_token, str) and query_token:
            raw_token = query_token

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
