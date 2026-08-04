"""Read-only Stage 4 Tool handlers backed by repositories and Provider protocols."""

import re
from decimal import Decimal
from hashlib import sha256
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agent.errors import AgentError, ProviderUnavailableError
from app.core.database import session_transaction
from app.providers.embedding import EmbeddingProvider
from app.providers.search import SearchProvider
from app.repositories.evidence import EvidenceRepository
from app.tools.contracts import (
    EvidenceItem,
    MemoryLookupInput,
    MemoryLookupItem,
    MemoryLookupOutput,
    RagEvidenceItem,
    RagRetrieveInput,
    RagRetrieveOutput,
    ToolContext,
    WebSearchInput,
    WebSearchItem,
    WebSearchOutput,
)

CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
SCRIPT_BLOCK = re.compile(r"(?is)<script\b[^>]*>.*?</script>")


class MemoryLookupHandler:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        embedding_provider: EmbeddingProvider,
    ) -> None:
        self._sessions = session_factory
        self._embedding = embedding_provider

    async def __call__(self, payload: BaseModel, context: ToolContext) -> BaseModel:
        request = MemoryLookupInput.model_validate(payload)
        vector: list[float] | None = None
        try:
            vectors = await self._embedding.embed([request.query])
            vector = vectors[0] if vectors else None
        except AgentError:
            vector = None
        async with self._sessions() as session:
            async with session_transaction(session):
                rows = await EvidenceRepository(session).memory_lookup(
                    user_id=context.user_id,
                    query=request.query,
                    vector=vector,
                    limit=request.limit,
                )
        items: list[MemoryLookupItem] = []
        evidence: list[EvidenceItem] = []
        remaining = 4000
        for memory, relevance in rows:
            content = _clean(memory.summary, min(remaining, 1000))
            if not content:
                continue
            remaining -= len(content)
            items.append(
                MemoryLookupItem(
                    memory_id=memory.id,
                    content=content,
                    memory_type=memory.memory_type,
                    relevance=relevance,
                    updated_at=memory.updated_at,
                )
            )
            evidence.append(
                EvidenceItem(
                    kind="memory",
                    id=memory.id,
                    title=memory.memory_type,
                    content=content,
                    reliability=0.9,
                )
            )
            if remaining <= 0:
                break
        return MemoryLookupOutput(items=items, evidence=evidence)


class RagRetrieveHandler:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        embedding_provider: EmbeddingProvider,
        min_similarity: float = 0.35,
    ) -> None:
        self._sessions = session_factory
        self._embedding = embedding_provider
        self._min_similarity = min_similarity

    async def __call__(self, payload: BaseModel, context: ToolContext) -> BaseModel:
        request = RagRetrieveInput.model_validate(payload)
        if request.goal_type != context.goal_type:
            raise ValueError("goal_type must match the current Run")
        vectors = await self._embedding.embed([request.query])
        if not vectors:
            raise ProviderUnavailableError("Embedding Provider returned no vector")
        async with self._sessions() as session:
            async with session_transaction(session):
                rows = await EvidenceRepository(session).rag_retrieve(
                    goal_type=context.goal_type.value,
                    vector=vectors[0],
                    limit=request.limit,
                    min_similarity=self._min_similarity,
                )
        items: list[RagEvidenceItem] = []
        evidence_items: list[EvidenceItem] = []
        for atom, score in rows:
            raw_reliability = atom.evidence_json.get("reliability", 0.7)
            reliability = (
                float(raw_reliability)
                if isinstance(raw_reliability, (int, float, Decimal))
                else 0.7
            )
            excerpt = atom.evidence_json.get("evidence_excerpt", "curated")
            evidence_text = _clean(str(excerpt), 300)
            content = _clean(atom.content, 1200)
            items.append(
                RagEvidenceItem(
                    atom_id=atom.id,
                    title=atom.title,
                    content=content,
                    evidence=evidence_text,
                    reliability=max(0.0, min(1.0, reliability)),
                    score=score,
                )
            )
            evidence_items.append(
                EvidenceItem(
                    kind="experience_atom",
                    id=atom.id,
                    title=atom.title,
                    content=content,
                    reliability=max(0.0, min(1.0, reliability)),
                )
            )
        return RagRetrieveOutput(items=items, evidence=evidence_items)


class WebSearchHandler:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        search_provider: SearchProvider,
    ) -> None:
        self._sessions = session_factory
        self._search = search_provider

    async def __call__(self, payload: BaseModel, context: ToolContext) -> BaseModel:
        request = WebSearchInput.model_validate(payload)
        raw_items = await self._search.search(
            query=request.query,
            limit=request.limit,
            freshness_days=request.freshness_days,
        )
        deduplicated: dict[str, object] = {}
        for item in raw_items:
            normalized_url = _normalize_url(item.url)
            if normalized_url and normalized_url not in deduplicated:
                deduplicated[normalized_url] = item
        items: list[WebSearchItem] = []
        evidence: list[EvidenceItem] = []
        async with self._sessions() as session:
            async with session_transaction(session):
                repository = EvidenceRepository(session)
                for normalized_url, raw in list(deduplicated.items())[: request.limit]:
                    from app.providers.search import SearchResultItem

                    source_item = SearchResultItem.model_validate(raw)
                    snippet = _clean(source_item.snippet, 1200)
                    title = _clean(source_item.title or "Untitled source", 300)
                    source = await repository.upsert_search_source(
                        run_id=context.run_id,
                        url=normalized_url,
                        url_hash=sha256(normalized_url.encode("utf-8")).hexdigest(),
                        content_hash=sha256(snippet.encode("utf-8")).hexdigest(),
                        title=title,
                        snippet=snippet,
                        source_type=source_item.source_type,
                        reliability=source_item.reliability,
                        provider=self._search.provider_name,
                        retrieved_at=source_item.retrieved_at,
                        provider_request_id=source_item.provider_request_id,
                        published_at=source_item.published_at,
                    )
                    items.append(
                        WebSearchItem(
                            source_id=source.id,
                            url=source.url,
                            title=source.title,
                            snippet=source.snippet,
                            source_type=source.source_type,
                            reliability=float(source.reliability),
                            retrieved_at=source.retrieved_at,
                        )
                    )
                    evidence.append(
                        EvidenceItem(
                            kind="search_source",
                            id=source.id,
                            title=source.title or "Search source",
                            content=source.snippet,
                            reliability=float(source.reliability),
                        )
                    )
        return WebSearchOutput(items=items, evidence=evidence)


def _clean(value: str, limit: int) -> str:
    without_scripts = SCRIPT_BLOCK.sub("", value)
    cleaned = CONTROL_CHARACTERS.sub("", without_scripts)
    cleaned = " ".join(cleaned.split())
    return cleaned[:limit]


def _normalize_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    filtered_query = [
        (key, item)
        for key, item in parse_qsl(parsed.query, keep_blank_values=False)
        if not key.lower().startswith("utm_")
    ]
    hostname = parsed.hostname.lower() if parsed.hostname else ""
    port = parsed.port
    if port is not None and not (
        (parsed.scheme.lower() == "http" and port == 80)
        or (parsed.scheme.lower() == "https" and port == 443)
    ):
        hostname = f"{hostname}:{port}"
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit(
        (
            parsed.scheme.lower(),
            hostname,
            path,
            urlencode(sorted(filtered_query)),
            "",
        )
    )
