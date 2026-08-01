"""Vector and evidence persistence queries used by read-only Stage 4 Tools."""

from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evidence import ExperienceAtom, Memory, SearchSource


class EvidenceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def pinned_memories(self, user_id: UUID, *, limit: int = 3) -> list[Memory]:
        rows = await self._session.scalars(
            select(Memory)
            .where(
                Memory.user_id == user_id,
                Memory.status == "active",
                Memory.content_json["pinned"].as_boolean().is_(True),
            )
            .order_by(Memory.updated_at.desc())
            .limit(limit)
        )
        return list(rows)

    async def memory_lookup(
        self,
        *,
        user_id: UUID,
        query: str,
        vector: list[float] | None,
        limit: int,
    ) -> list[tuple[Memory, float]]:
        if vector is not None:
            distance = Memory.embedding.cosine_distance(vector)
            vector_rows = await self._session.execute(
                select(Memory, (1 - distance).label("score"))
                .where(
                    Memory.user_id == user_id,
                    Memory.status == "active",
                    Memory.embedding.is_not(None),
                )
                .order_by(distance)
                .limit(limit)
            )
            return [(memory, max(0.0, min(1.0, float(score)))) for memory, score in vector_rows]
        terms = [term for term in query.split() if term][:5]
        statement = select(Memory).where(
            Memory.user_id == user_id,
            Memory.status == "active",
        )
        if terms:
            statement = statement.where(Memory.summary.ilike(f"%{terms[0]}%"))
        memory_rows = await self._session.scalars(
            statement.order_by(Memory.updated_at.desc()).limit(limit)
        )
        return [(memory, 0.5) for memory in memory_rows]

    async def rag_retrieve(
        self,
        *,
        goal_type: str,
        vector: list[float],
        limit: int,
    ) -> list[tuple[ExperienceAtom, float]]:
        distance = ExperienceAtom.embedding.cosine_distance(vector)
        rows = await self._session.execute(
            select(ExperienceAtom, (1 - distance).label("score"))
            .where(
                ExperienceAtom.goal_type == goal_type,
                ExperienceAtom.is_active.is_(True),
                ExperienceAtom.embedding.is_not(None),
            )
            .order_by(distance)
            .limit(limit)
        )
        return [(atom, max(0.0, min(1.0, float(score)))) for atom, score in rows]

    async def upsert_search_source(
        self,
        *,
        run_id: UUID,
        url: str,
        title: str | None,
        snippet: str,
        source_type: str,
        reliability: float,
        provider: str,
        retrieved_at: datetime,
    ) -> SearchSource:
        statement = (
            insert(SearchSource)
            .values(
                run_id=run_id,
                url=url,
                title=title,
                snippet=snippet,
                source_type=source_type,
                reliability=Decimal(str(reliability)),
                provider=provider,
                retrieved_at=retrieved_at,
            )
            .on_conflict_do_nothing(index_elements=["run_id", "url"])
        )
        await self._session.execute(statement)
        source = await self._session.scalar(
            select(SearchSource).where(SearchSource.run_id == run_id, SearchSource.url == url)
        )
        if source is None:
            raise RuntimeError("SearchSource upsert did not return a row")
        return source

    async def search_sources_for_run(self, run_id: UUID) -> list[SearchSource]:
        rows = await self._session.scalars(
            select(SearchSource)
            .where(SearchSource.run_id == run_id)
            .order_by(SearchSource.retrieved_at, SearchSource.id)
        )
        return list(rows)

    async def evidence_ids_for_run(
        self,
        *,
        run_id: UUID,
        user_id: UUID,
    ) -> set[tuple[str, UUID]]:
        catalog: set[tuple[str, UUID]] = set()
        memory_ids = await self._session.scalars(
            select(Memory.id).where(Memory.user_id == user_id, Memory.status == "active")
        )
        catalog.update(("memory", memory_id) for memory_id in memory_ids)
        source_ids = await self._session.scalars(
            select(SearchSource.id).where(SearchSource.run_id == run_id)
        )
        catalog.update(("search_source", source_id) for source_id in source_ids)
        tool_rows = await self._session.execute(
            select(ExperienceAtom.id).where(ExperienceAtom.is_active.is_(True))
        )
        catalog.update(("experience_atom", atom_id) for atom_id in tool_rows.scalars())
        return catalog

    async def resolve_memories(self, user_id: UUID, ids: Iterable[UUID]) -> list[Memory]:
        values = list(ids)
        if not values:
            return []
        rows = await self._session.scalars(
            select(Memory).where(Memory.user_id == user_id, Memory.id.in_(values))
        )
        return list(rows)

    async def resolve_atoms(self, ids: Iterable[UUID]) -> list[ExperienceAtom]:
        values = list(ids)
        if not values:
            return []
        rows = await self._session.scalars(
            select(ExperienceAtom).where(ExperienceAtom.id.in_(values))
        )
        return list(rows)

    async def resolve_sources(self, run_id: UUID, ids: Iterable[UUID]) -> list[SearchSource]:
        values = list(ids)
        if not values:
            return []
        rows = await self._session.scalars(
            select(SearchSource).where(SearchSource.run_id == run_id, SearchSource.id.in_(values))
        )
        return list(rows)
