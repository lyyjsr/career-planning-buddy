"""Developer-only cross-user Trace queries."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_run import AgentEvent, AgentRun, AgentStep, ToolCall


class DevTraceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_runs(
        self,
        *,
        status: str | None,
        result_kind: str | None,
        error_code: str | None,
        cursor: UUID | None,
        limit: int,
    ) -> list[AgentRun]:
        statement = select(AgentRun)
        if status is not None:
            statement = statement.where(AgentRun.status == status)
        if result_kind is not None:
            statement = statement.where(AgentRun.result_kind == result_kind)
        if error_code is not None:
            statement = statement.where(AgentRun.error_code == error_code)
        if cursor is not None:
            cursor_created_at = await self._session.scalar(
                select(AgentRun.created_at).where(AgentRun.id == cursor)
            )
            if cursor_created_at is not None:
                statement = statement.where(AgentRun.created_at < cursor_created_at)
        rows = await self._session.scalars(
            statement.order_by(AgentRun.created_at.desc()).limit(limit + 1)
        )
        return list(rows)

    async def get_run(self, run_id: UUID) -> AgentRun | None:
        return await self._session.get(AgentRun, run_id)

    async def get_trace(
        self, run_id: UUID
    ) -> tuple[list[AgentStep], list[ToolCall], list[AgentEvent]]:
        steps = list(
            await self._session.scalars(
                select(AgentStep).where(AgentStep.run_id == run_id).order_by(AgentStep.sequence)
            )
        )
        tools = list(
            await self._session.scalars(
                select(ToolCall)
                .where(ToolCall.run_id == run_id)
                .order_by(ToolCall.created_at, ToolCall.id)
            )
        )
        events = list(
            await self._session.scalars(
                select(AgentEvent).where(AgentEvent.run_id == run_id).order_by(AgentEvent.sequence)
            )
        )
        return steps, tools, events
