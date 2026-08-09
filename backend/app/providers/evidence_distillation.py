"""Structured LLM adapter used only for best-effort evidence distillation."""

import json
from collections.abc import Mapping
from typing import Protocol

import httpx

from app.agent.errors import ProviderUnavailableError
from app.core.config import Settings
from app.models.evidence import SearchSource


class EvidenceDistillationProvider(Protocol):
    async def distill(self, *, goal_type: str, sources: list[SearchSource]) -> object: ...

    async def repair(self, *, raw_output: object) -> object: ...


class MockEvidenceDistillationProvider:
    async def distill(self, *, goal_type: str, sources: list[SearchSource]) -> object:
        del goal_type
        return {
            "candidates": [
                {
                    "title": (source.title or "搜索证据")[:200],
                    "content": source.snippet[:300],
                    "source_ids": [str(source.id)],
                    "evidence_excerpt": source.snippet[:300],
                    "confidence": float(source.reliability),
                }
                for source in sources[:3]
                if source.snippet.strip()
            ]
        }

    async def repair(self, *, raw_output: object) -> object:
        return raw_output


class OpenAICompatibleEvidenceDistillationProvider:
    def __init__(self, settings: Settings) -> None:
        assert settings.llm_api_key and settings.llm_base_url and settings.llm_model
        self._key = settings.llm_api_key.get_secret_value()
        self._url = str(settings.llm_base_url).rstrip("/") + "/chat/completions"
        self._model = settings.llm_model
        self._client = httpx.AsyncClient(timeout=60)

    async def distill(self, *, goal_type: str, sources: list[SearchSource]) -> object:
        source_payload = [
            {"id": str(item.id), "title": item.title, "content": item.snippet[:1200]}
            for item in sources
        ]
        prompt = (
            "Return JSON only: {candidates:[{title,content,source_ids,evidence_excerpt,"
            "confidence}]}. At most 3 atomic reusable career facts. content and excerpt <=300; "
            "excerpt must be verbatim in a supplied content; never infer private facts. "
            f"goal_type={goal_type}; sources={json.dumps(source_payload, ensure_ascii=False)}"
        )
        return await self._complete(prompt)

    async def repair(self, *, raw_output: object) -> object:
        return await self._complete(
            "Repair this into the exact requested JSON schema without adding facts: "
            + json.dumps(raw_output, ensure_ascii=False, default=str)[:6000]
        )

    async def _complete(self, prompt: str) -> object:
        try:
            response = await self._client.post(
                self._url,
                headers={"Authorization": f"Bearer {self._key}"},
                json={
                    "model": self._model,
                    "messages": [{"role": "user", "content": prompt}],
                    "response_format": {"type": "json_object"},
                    "temperature": 0,
                },
            )
            response.raise_for_status()
            body: Mapping[str, object] = response.json()
            choices = body.get("choices")
            if not isinstance(choices, list) or not choices:
                raise ValueError
            message = choices[0].get("message") if isinstance(choices[0], Mapping) else None
            content = message.get("content") if isinstance(message, Mapping) else None
            if not isinstance(content, str):
                raise ValueError
            return json.loads(content)
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
            raise ProviderUnavailableError("Evidence distillation Provider failed") from exc

    async def aclose(self) -> None:
        await self._client.aclose()


def build_evidence_distillation_provider(settings: Settings) -> EvidenceDistillationProvider:
    if settings.llm_provider == "mock":
        return MockEvidenceDistillationProvider()
    return OpenAICompatibleEvidenceDistillationProvider(settings)
