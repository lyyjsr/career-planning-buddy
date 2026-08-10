"""Provider protocol and deterministic Stage 4 planning adapter."""

import asyncio
import json
from collections.abc import Mapping
from datetime import timedelta
from hashlib import sha256
from time import monotonic
from typing import Protocol
from urllib.parse import urlparse

import httpx
from pydantic import ValidationError

from app.agent.errors import (
    ProviderAuthenticationError,
    ProviderConfigurationError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    parse_retry_after,
)
from app.core.config import Settings
from app.prompts.career_planning import (
    business_repair_messages,
    direct_baseline_messages,
    format_repair_messages,
    generation_messages,
)
from app.schemas.agent_runs import (
    AgentTurnResponse,
    EvidenceCatalogItem,
    PlanCandidate,
    PlanningContext,
    ProviderPlanResponse,
    ProviderToolCall,
    ProviderUsage,
    TaskCandidate,
    WeeklyFocusCandidate,
)
from app.schemas.enums import ReplanMode, TaskType
from app.tools.contracts import ModelToolSpec


class PlanningProvider(Protocol):
    async def generate_agent_turn(
        self,
        *,
        message: str,
        context: PlanningContext,
        replan_mode: ReplanMode,
        available_tools: list[ModelToolSpec],
        evidence_catalog: list[EvidenceCatalogItem],
        force_final: bool,
    ) -> Mapping[str, object]: ...

    async def generate_plan(
        self,
        *,
        message: str,
        context: PlanningContext,
        replan_mode: ReplanMode,
        evidence_catalog: list[EvidenceCatalogItem],
    ) -> Mapping[str, object]: ...

    async def repair_format(
        self,
        *,
        raw_output: Mapping[str, object],
        context: PlanningContext,
        replan_mode: ReplanMode,
        evidence_catalog: list[EvidenceCatalogItem],
    ) -> Mapping[str, object]: ...

    async def repair_business_rules(
        self,
        *,
        candidate: PlanCandidate,
        context: PlanningContext,
        repair_instructions: list[str],
        message: str,
        replan_mode: ReplanMode,
        evidence_catalog: list[EvidenceCatalogItem],
    ) -> Mapping[str, object]: ...


class OpenAICompatiblePlanningProvider:
    """OpenAI-compatible Chat Completions adapter with strict JSON output."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float = 30,
        max_output_tokens: int = 1500,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not api_key or not base_url or not model:
            raise ProviderConfigurationError(
                "openai_compatible requires API key, base URL, and model"
            )
        self._api_key = api_key
        self._endpoint = f"{base_url.rstrip('/')}/chat/completions"
        provider_host = urlparse(base_url).hostname
        self._supports_thinking_control = provider_host == "api.deepseek.com" or (
            provider_host is not None and provider_host.endswith(".deepseek.com")
        )
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._max_output_tokens = max_output_tokens
        self._transport = transport
        self._client = (
            httpx.AsyncClient(
                timeout=self._timeout_seconds,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
            )
            if transport is None
            else None
        )

    async def generate_plan(
        self,
        *,
        message: str,
        context: PlanningContext,
        replan_mode: ReplanMode,
        evidence_catalog: list[EvidenceCatalogItem],
    ) -> Mapping[str, object]:
        return await self._generate(
            generation_messages(
                message=message,
                context=context,
                replan_mode=replan_mode,
                evidence_catalog=evidence_catalog,
            )
        )

    async def generate_direct_plan(
        self,
        *,
        message: str,
        context: PlanningContext,
        replan_mode: ReplanMode,
    ) -> Mapping[str, object]:
        return await self._generate(
            direct_baseline_messages(
                message=message,
                context=context,
                replan_mode=replan_mode,
            )
        )

    async def generate_agent_turn(
        self,
        *,
        message: str,
        context: PlanningContext,
        replan_mode: ReplanMode,
        available_tools: list[ModelToolSpec],
        evidence_catalog: list[EvidenceCatalogItem],
        force_final: bool,
    ) -> Mapping[str, object]:
        messages = generation_messages(
            message=message,
            context=context,
            replan_mode=replan_mode,
            evidence_catalog=evidence_catalog,
        )
        request_body: dict[str, object] = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": self._max_output_tokens,
            "response_format": {"type": "json_object"},
        }
        self._apply_thinking_disabled(request_body)
        if available_tools and not force_final:
            request_body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.input_json_schema,
                        "strict": True,
                    },
                }
                for tool in available_tools
            ]
            request_body["tool_choice"] = "auto"
        response, latency_ms, response_text = await self._post(request_body)
        body = self._response_mapping(response)
        usage = self._usage(
            body=body,
            latency_ms=latency_ms,
            request_id=response.headers.get("x-request-id"),
            raw_output_hash=sha256(response_text.encode("utf-8")).hexdigest(),
        )
        message_object = self._message_mapping(body)
        tool_calls = self._tool_calls(message_object)
        content = message_object.get("content") if message_object is not None else None
        has_content = isinstance(content, str) and bool(content.strip())
        if tool_calls and has_content:
            return {
                "_raw_text": "mixed tool calls and final",
                "usage": usage.model_dump(mode="json"),
            }
        if tool_calls:
            return AgentTurnResponse(
                tool_calls=tool_calls,
                usage=usage,
            ).model_dump(mode="json")
        if isinstance(content, str) and content.strip():
            try:
                candidate_object: object = json.loads(content)
                candidate = PlanCandidate.model_validate(candidate_object)
            except (json.JSONDecodeError, ValidationError):
                return {"_raw_text": content[:12000], "usage": usage.model_dump(mode="json")}
            return AgentTurnResponse(final=candidate, usage=usage).model_dump(mode="json")
        return {"_raw_text": response_text[:12000], "usage": usage.model_dump(mode="json")}

    async def repair_format(
        self,
        *,
        raw_output: Mapping[str, object],
        context: PlanningContext,
        replan_mode: ReplanMode,
        evidence_catalog: list[EvidenceCatalogItem],
    ) -> Mapping[str, object]:
        return await self._generate(
            format_repair_messages(
                raw_output=raw_output,
                context=context,
                replan_mode=replan_mode,
                evidence_catalog=evidence_catalog,
            )
        )

    async def repair_business_rules(
        self,
        *,
        candidate: PlanCandidate,
        context: PlanningContext,
        repair_instructions: list[str],
        message: str,
        replan_mode: ReplanMode,
        evidence_catalog: list[EvidenceCatalogItem],
    ) -> Mapping[str, object]:
        return await self._generate(
            business_repair_messages(
                candidate=candidate,
                context=context,
                repair_instructions=repair_instructions,
                message=message,
                replan_mode=replan_mode,
                evidence_catalog=evidence_catalog,
            )
        )

    async def _generate(self, messages: list[dict[str, str]]) -> Mapping[str, object]:
        request_body: dict[str, object] = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": self._max_output_tokens,
            "response_format": {"type": "json_object"},
        }
        self._apply_thinking_disabled(request_body)
        response, latency_ms, response_text = await self._post(request_body)
        raw_output_hash = sha256(response_text.encode("utf-8")).hexdigest()
        body = self._response_mapping(response)
        usage = self._usage(
            body=body,
            latency_ms=latency_ms,
            request_id=response.headers.get("x-request-id"),
            raw_output_hash=raw_output_hash,
        )
        content = self._message_content(body)
        if content is None:
            return {
                "_raw_text": response_text[:12000],
                "usage": usage.model_dump(mode="json"),
            }
        try:
            candidate_object: object = json.loads(content)
        except json.JSONDecodeError:
            return {
                "_raw_text": content[:12000],
                "usage": usage.model_dump(mode="json"),
            }
        if not isinstance(candidate_object, Mapping):
            return {
                "_raw_text": content[:12000],
                "usage": usage.model_dump(mode="json"),
            }
        candidate = {str(key): value for key, value in candidate_object.items()}
        return {
            "candidate": candidate,
            "usage": usage.model_dump(mode="json"),
        }

    async def _post(self, request_body: dict[str, object]) -> tuple[httpx.Response, int, str]:
        started = monotonic()
        try:
            if self._client is not None:
                response = await self._client.post(self._endpoint, json=request_body)
            else:
                async with httpx.AsyncClient(
                    transport=self._transport,
                    timeout=self._timeout_seconds,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                ) as client:
                    response = await client.post(self._endpoint, json=request_body)
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                "LLM provider request timed out", retryable=True
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderUnavailableError(
                "LLM provider could not be reached", retryable=True
            ) from exc

        if response.status_code in {401, 403}:
            raise ProviderAuthenticationError("LLM provider rejected authentication")
        if response.status_code == 429:
            raise ProviderRateLimitError(
                "LLM provider rate limit was reached",
                retryable=True,
                retry_after_seconds=parse_retry_after(
                    response.headers.get("retry-after")
                ),
            )
        if response.status_code >= 500:
            raise ProviderUnavailableError(
                f"LLM provider returned HTTP {response.status_code}",
                retryable=True,
                retry_after_seconds=parse_retry_after(
                    response.headers.get("retry-after")
                ),
            )
        if response.status_code >= 400:
            raise ProviderUnavailableError(
                f"LLM provider returned HTTP {response.status_code}",
                retryable=False,
            )

        return response, int((monotonic() - started) * 1000), response.text

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()

    def _apply_thinking_disabled(self, request_body: dict[str, object]) -> None:
        """Disable reasoning only for the explicitly supported DeepSeek API."""
        if self._supports_thinking_control:
            request_body["thinking"] = {"type": "disabled"}


    @staticmethod
    def _response_mapping(response: httpx.Response) -> Mapping[object, object]:
        try:
            body: object = response.json()
        except ValueError:
            return {}
        return body if isinstance(body, Mapping) else {}

    @staticmethod
    def _message_content(body: Mapping[object, object]) -> str | None:
        choices = body.get("choices")
        if not isinstance(choices, list) or not choices:
            return None
        first = choices[0]
        if not isinstance(first, Mapping):
            return None
        message = first.get("message")
        if not isinstance(message, Mapping):
            return None
        content = message.get("content")
        if isinstance(content, str):
            return content
        if not isinstance(content, list):
            return None
        parts: list[str] = []
        for item in content:
            if not isinstance(item, Mapping):
                continue
            text = item.get("text")
            if isinstance(text, str):
                parts.append(text)
        return "".join(parts) or None

    @staticmethod
    def _message_mapping(body: Mapping[object, object]) -> Mapping[object, object] | None:
        choices = body.get("choices")
        if not isinstance(choices, list) or not choices:
            return None
        first = choices[0]
        if not isinstance(first, Mapping):
            return None
        message = first.get("message")
        return message if isinstance(message, Mapping) else None

    @staticmethod
    def _tool_calls(
        message: Mapping[object, object] | None,
    ) -> list[ProviderToolCall]:
        if message is None:
            return []
        raw_calls = message.get("tool_calls")
        if not isinstance(raw_calls, list):
            return []
        calls: list[ProviderToolCall] = []
        for index, raw_call in enumerate(raw_calls):
            if not isinstance(raw_call, Mapping):
                continue
            function = raw_call.get("function")
            if not isinstance(function, Mapping):
                continue
            name = function.get("name")
            raw_arguments = function.get("arguments")
            call_id = raw_call.get("id")
            if not isinstance(name, str) or not isinstance(raw_arguments, str):
                continue
            try:
                arguments_object: object = json.loads(raw_arguments)
            except json.JSONDecodeError:
                arguments_object = {}
            if not isinstance(arguments_object, Mapping):
                arguments_object = {}
            calls.append(
                ProviderToolCall(
                    call_id=call_id if isinstance(call_id, str) else f"call-{index}",
                    name=name,
                    arguments={str(key): value for key, value in arguments_object.items()},
                )
            )
        return calls

    def _usage(
        self,
        *,
        body: Mapping[object, object],
        latency_ms: int,
        request_id: str | None,
        raw_output_hash: str,
    ) -> ProviderUsage:
        usage_object = body.get("usage")
        usage = usage_object if isinstance(usage_object, Mapping) else {}
        model_object = body.get("model")
        response_id = body.get("id")
        return ProviderUsage(
            model_id=model_object if isinstance(model_object, str) else self._model,
            provider="openai_compatible",
            request_id=(
                request_id
                if request_id is not None
                else response_id
                if isinstance(response_id, str)
                else None
            ),
            raw_output_hash=raw_output_hash,
            tokens_in=self._nonnegative_int(usage.get("prompt_tokens")),
            tokens_out=self._nonnegative_int(usage.get("completion_tokens")),
            latency_ms=latency_ms,
        )

    @staticmethod
    def _nonnegative_int(value: object) -> int:
        return value if isinstance(value, int) and value >= 0 else 0


class DirectLLMPlanningProvider:
    """LLM-only Eval arm with no tool, memory, or evidence visibility."""

    def __init__(self, delegate: OpenAICompatiblePlanningProvider) -> None:
        self._delegate = delegate

    async def generate_agent_turn(
        self,
        *,
        message: str,
        context: PlanningContext,
        replan_mode: ReplanMode,
        available_tools: list[ModelToolSpec],
        evidence_catalog: list[EvidenceCatalogItem],
        force_final: bool,
    ) -> Mapping[str, object]:
        del available_tools, evidence_catalog, force_final
        raw = await self.generate_plan(
            message=message,
            context=context,
            replan_mode=replan_mode,
            evidence_catalog=[],
        )
        candidate = raw.get("candidate")
        usage = raw.get("usage")
        if candidate is None or usage is None:
            return raw
        return {"final": candidate, "tool_calls": [], "usage": usage}

    async def generate_plan(
        self,
        *,
        message: str,
        context: PlanningContext,
        replan_mode: ReplanMode,
        evidence_catalog: list[EvidenceCatalogItem],
    ) -> Mapping[str, object]:
        del evidence_catalog
        return await self._delegate.generate_direct_plan(
            message=message,
            context=context,
            replan_mode=replan_mode,
        )

    async def repair_format(
        self,
        *,
        raw_output: Mapping[str, object],
        context: PlanningContext,
        replan_mode: ReplanMode,
        evidence_catalog: list[EvidenceCatalogItem],
    ) -> Mapping[str, object]:
        del evidence_catalog
        return await self._delegate.repair_format(
            raw_output=raw_output,
            context=_direct_context(context),
            replan_mode=replan_mode,
            evidence_catalog=[],
        )

    async def repair_business_rules(
        self,
        *,
        candidate: PlanCandidate,
        context: PlanningContext,
        repair_instructions: list[str],
        message: str,
        replan_mode: ReplanMode,
        evidence_catalog: list[EvidenceCatalogItem],
    ) -> Mapping[str, object]:
        del evidence_catalog
        return await self._delegate.repair_business_rules(
            candidate=candidate,
            context=_direct_context(context),
            repair_instructions=repair_instructions,
            message=message,
            replan_mode=replan_mode,
            evidence_catalog=[],
        )


def _direct_context(context: PlanningContext) -> PlanningContext:
    return context.model_copy(
        update={
            "recent_tasks": [],
            "recent_reviews": [],
            "completed_facts": [],
            "blockers": [],
            "pinned_memories": [],
            "task_history_summary": None,
            "review_history_summary": None,
            "token_estimate": 0,
        }
    )


class MockPlanningProvider:
    """Deterministic provider whose scenarios are selected by test-safe message markers."""

    model_id = "mock-career-planner-v1"

    def __init__(self) -> None:
        self.plan_calls = 0
        self.format_repair_calls = 0
        self.business_repair_calls = 0

    async def generate_agent_turn(
        self,
        *,
        message: str,
        context: PlanningContext,
        replan_mode: ReplanMode,
        available_tools: list[ModelToolSpec],
        evidence_catalog: list[EvidenceCatalogItem],
        force_final: bool,
    ) -> Mapping[str, object]:
        self.plan_calls += 1
        if "[mock:timeout]" in message:
            await asyncio.sleep(60)
        candidate = self._candidate(context, replan_mode)
        if "[mock:invalid-schema]" in message or "[mock:invalid-schema-twice]" in message:
            invalid_payload = candidate.model_dump(mode="json")
            invalid_payload["tasks"] = []
            return {
                "candidate": invalid_payload,
                "usage": self._usage().model_dump(mode="json"),
                "_mock_scenario": (
                    "invalid-schema-twice"
                    if "[mock:invalid-schema-twice]" in message
                    else "invalid-schema"
                ),
            }
        if "[mock:rule-repair]" in message or "[mock:rule-fallback]" in message:
            invalid_candidate = self._over_budget_candidate(candidate, context)
            return AgentTurnResponse(
                final=invalid_candidate,
                usage=self._usage(),
            ).model_dump(mode="json")
        requested: list[str] = []
        if "[mock:tool-all]" in message:
            requested = ["memory_lookup", "rag_retrieve"]
        elif "[mock:tool-memory]" in message:
            requested = ["memory_lookup"]
        elif "[mock:tool-rag]" in message:
            requested = ["rag_retrieve"]
        elif "[mock:tool-search]" in message:
            requested = ["web_search"]
        elif "[mock:tool-unknown]" in message:
            requested = ["unregistered_tool"]
        if requested and not evidence_catalog and not force_final:
            calls: list[ProviderToolCall] = []
            for index, name in enumerate(requested):
                query = (
                    "[mock:search-timeout]"
                    if "[mock:search-timeout]" in message
                    else "[mock:search-error]"
                    if "[mock:search-error]" in message
                    else "[mock:embedding-error]"
                    if "[mock:embedding-error]" in message
                    else "Agent 工程求职证据"
                )
                arguments: dict[str, object] = {"query": query, "limit": 3}
                if name == "rag_retrieve":
                    arguments["goal_type"] = context.profile.goal_type.value
                if "[mock:tool-invalid]" in message:
                    arguments["unexpected"] = True
                calls.append(
                    ProviderToolCall(
                        call_id=f"mock-call-{index + 1}",
                        name=name,
                        arguments=arguments,
                    )
                )
            return AgentTurnResponse(
                tool_calls=calls,
                usage=self._usage(tokens_in=120, tokens_out=40),
            ).model_dump(mode="json")
        allowed_evidence = evidence_catalog[:10]
        if allowed_evidence:
            candidate_payload = candidate.model_dump(mode="python")
            candidate_payload["evidence_refs"] = [
                {"kind": item.kind, "id": item.id} for item in allowed_evidence
            ]
            candidate = PlanCandidate.model_validate(candidate_payload)
        if "[mock:forged-evidence]" in message:
            from uuid import UUID

            candidate_payload = candidate.model_dump(mode="python")
            candidate_payload["evidence_refs"] = [
                {
                    "kind": "memory",
                    "id": UUID("00000000-0000-0000-0000-000000000001"),
                }
            ]
            candidate = PlanCandidate.model_validate(candidate_payload)
        return AgentTurnResponse(
            final=PlanCandidate.model_validate(candidate),
            usage=self._usage(),
        ).model_dump(mode="json")

    async def generate_plan(
        self,
        *,
        message: str,
        context: PlanningContext,
        replan_mode: ReplanMode,
        evidence_catalog: list[EvidenceCatalogItem],
    ) -> Mapping[str, object]:
        self.plan_calls += 1
        if "[mock:timeout]" in message:
            await asyncio.sleep(60)
        candidate = self._candidate(context, replan_mode)
        if "[mock:invalid-schema]" in message or "[mock:invalid-schema-twice]" in message:
            invalid_payload = candidate.model_dump(mode="json")
            invalid_payload["tasks"] = []
            return {
                "candidate": invalid_payload,
                "usage": self._usage().model_dump(mode="json"),
                "_mock_scenario": (
                    "invalid-schema-twice"
                    if "[mock:invalid-schema-twice]" in message
                    else "invalid-schema"
                ),
            }
        if "[mock:rule-repair]" in message or "[mock:rule-fallback]" in message:
            invalid_candidate = self._over_budget_candidate(candidate, context)
            return ProviderPlanResponse(
                candidate=invalid_candidate, usage=self._usage()
            ).model_dump(mode="json")
        if evidence_catalog and "[mock:tool-" in message:
            payload = candidate.model_dump(mode="python")
            payload["evidence_refs"] = [
                {"kind": item.kind, "id": item.id} for item in evidence_catalog[:10]
            ]
            candidate = PlanCandidate.model_validate(payload)
        if "[mock:forged-evidence]" in message:
            from uuid import UUID

            payload = candidate.model_dump(mode="python")
            payload["evidence_refs"] = [
                {
                    "kind": "memory",
                    "id": UUID("00000000-0000-0000-0000-000000000001"),
                }
            ]
            candidate = PlanCandidate.model_validate(payload)
        return ProviderPlanResponse(candidate=candidate, usage=self._usage()).model_dump(
            mode="json"
        )

    async def repair_format(
        self,
        *,
        raw_output: Mapping[str, object],
        context: PlanningContext,
        replan_mode: ReplanMode,
        evidence_catalog: list[EvidenceCatalogItem],
    ) -> Mapping[str, object]:
        self.format_repair_calls += 1
        if raw_output.get("_mock_scenario") == "invalid-schema-twice":
            return raw_output
        return ProviderPlanResponse(
            candidate=self._candidate(context, replan_mode),
            usage=self._usage(tokens_in=180, tokens_out=320),
        ).model_dump(mode="json")

    async def repair_business_rules(
        self,
        *,
        candidate: PlanCandidate,
        context: PlanningContext,
        repair_instructions: list[str],
        message: str,
        replan_mode: ReplanMode,
        evidence_catalog: list[EvidenceCatalogItem],
    ) -> Mapping[str, object]:
        self.business_repair_calls += 1
        del candidate, repair_instructions, evidence_catalog
        repaired = self._candidate(context, replan_mode)
        if "[mock:rule-fallback]" in message:
            repaired = self._over_budget_candidate(repaired, context)
        return ProviderPlanResponse(
            candidate=repaired,
            usage=self._usage(tokens_in=250, tokens_out=400),
        ).model_dump(mode="json")

    def _candidate(
        self, context: PlanningContext, replan_mode: ReplanMode
    ) -> PlanCandidate:
        window = context.planning_window
        weekly_templates = [
            ("明确目标岗位与能力差距", "形成岗位要求与能力差距清单"),
            ("完成可展示的项目核心增量", "产出可运行、可验证的项目成果"),
            ("沉淀简历与项目表达材料", "形成可投递的简历项目描述"),
            ("开展模拟面试并验证准备效果", "完成复盘记录并修正薄弱点"),
            ("扩大岗位样本并校准投递方向", "形成目标岗位优先级列表"),
            ("强化高频面试专题与表达", "完成一轮专题问答演练"),
            ("集中投递并跟踪反馈", "形成投递与反馈跟踪表"),
            ("复盘结果并确定下一阶段策略", "形成下一阶段行动决策"),
        ]
        if replan_mode == ReplanMode.CONTINUE and context.source_plan is not None:
            source_weekly = [
                WeeklyFocusCandidate.model_validate(item.model_dump())
                for item in context.source_plan.weekly_focus[
                    : window.horizon_weeks
                ]
            ]
            weekly = (
                source_weekly
                if len(source_weekly) == window.horizon_weeks
                and len({item.focus for item in source_weekly}) == len(source_weekly)
                else [
                    WeeklyFocusCandidate(
                        week_index=index,
                        focus=weekly_templates[index - 1][0],
                        success_signal=weekly_templates[index - 1][1],
                    )
                    for index in range(1, window.horizon_weeks + 1)
                ]
            )
        else:
            weekly = [
                WeeklyFocusCandidate(
                    week_index=index,
                    focus=weekly_templates[index - 1][0],
                    success_signal=weekly_templates[index - 1][1],
                )
                for index in range(1, window.horizon_weeks + 1)
            ]
        daily_templates = [
            (
                "梳理目标岗位要求",
                TaskType.LEARNING,
                "1. 收集3份目标岗位JD；2. 标出重复的技能、项目和学历要求；3. 按出现次数排序",
                "岗位要求表，至少包含3份JD、10项要求及出现频次",
            ),
            (
                "盘点当前能力差距",
                TaskType.LEARNING,
                "1. 将要求分成已掌握、待补和可证明；2. 给待补项标优先级；3. 选出本周首要差距",
                "能力差距表，包含优先级、现有证据和本周首要补齐项",
            ),
            (
                "完成最小项目增量",
                TaskType.PROJECT,
                "1. 选择首要差距对应的项目功能；2. 先写验收用例；3. 实现最小闭环并提交",
                "一次代码提交，包含可运行功能、至少1个自动化测试和运行说明",
            ),
            (
                "验证并记录项目结果",
                TaskType.PROJECT,
                "1. 运行项目和测试；2. 保存关键输入输出；3. 记录失败原因、修复动作和最终结果",
                "验证记录，包含测试命令、通过结果以及截图或关键日志",
            ),
            (
                "整理简历项目表达",
                TaskType.RESUME,
                "1. 用背景、行动、结果重写项目经历；2. 补充技术取舍；3. 压缩成3至4条要点",
                "3至4条可直接放入简历的项目描述，每条包含动作和结果",
            ),
            (
                "演练项目面试问答",
                TaskType.INTERVIEW,
                "1. 准备架构、难点、取舍各1题；2. 每题限时2分钟口述；3. 重答含糊部分",
                "3组项目问答记录，每组包含首答问题和改进后的答案",
            ),
            (
                "复盘本周并安排下一步",
                TaskType.OTHER,
                "1. 汇总前6天产物；2. 标记完成、阻碍和欠账；3. 确定下周第一项可执行任务",
                "周复盘，包含完成清单、最多3个阻碍和下一步行动",
            ),
        ]
        minutes = max(5, min(45, context.time_budget_minutes))
        tasks = [
            TaskCandidate(
                title=title,
                task_type=task_type,
                scheduled_date=window.planning_date + timedelta(days=day_offset),
                starter_action=starter_action,
                deliverable=(
                    f"{(window.planning_date + timedelta(days=day_offset)).isoformat()} "
                    f"{deliverable}"
                ),
                estimated_minutes=minutes,
                rationale="结合当前目标、每日预算和近期执行事实推进下一项可验证成果",
            )
            for day_offset, (title, task_type, starter_action, deliverable) in enumerate(
                daily_templates
            )
        ]
        adjustment_reason = None
        if replan_mode == ReplanMode.ADJUST:
            review = context.source_review
            adjustment_reason = (
                review.adjustment_request
                if review and review.adjustment_request
                else review.replan_reason
                if review and review.replan_reason
                else review.blockers
                if review and review.blockers
                else "根据当前阻碍采用更小的行动步长"
            )
        return PlanCandidate(
            plan_date=window.planning_date,
            horizon_start=window.horizon_start,
            horizon_end=window.horizon_end,
            overall_direction=(
                context.source_plan.overall_direction
                if context.source_plan is not None
                else "在规划窗口内形成可展示项目证据并推进面试准备"
            ),
            weekly_focus=weekly,
            summary="七天内按定位、项目、表达和复盘逐步推进",
            rationale="每个日期只安排一个关键结果，并分别限制在每日时间预算内。",
            adjustment_reason=adjustment_reason,
            assumptions=["计划基于当前画像与每日时间预算"],
            tasks=tasks,
            evidence_refs=[],
        )

    @staticmethod
    def _over_budget_candidate(
        candidate: PlanCandidate,
        context: PlanningContext,
    ) -> PlanCandidate:
        if len(candidate.tasks) < 2:
            return candidate.model_copy(
                update={
                    "tasks": [
                        candidate.tasks[0].model_copy(
                            update={"estimated_minutes": context.time_budget_minutes + 1}
                        )
                    ]
                }
            )
        first_date = candidate.tasks[0].scheduled_date
        invalid = list(candidate.tasks)
        invalid[0] = invalid[0].model_copy(
            update={"estimated_minutes": context.time_budget_minutes}
        )
        invalid[1] = invalid[1].model_copy(
            update={
                "scheduled_date": first_date,
                "estimated_minutes": context.time_budget_minutes,
            }
        )
        return candidate.model_copy(update={"tasks": invalid})

    def _usage(self, *, tokens_in: int = 300, tokens_out: int = 450) -> ProviderUsage:
        return ProviderUsage(
            model_id=self.model_id,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=5,
        )


class PairSmokePlanningProvider(MockPlanningProvider):
    """Two deterministic, semantically-comparable fixture profiles used
    ONLY by Stage A pairwise smoke verification (PR-9c.2 Commit 3.4 / E′).

    Invariants (per reviewer-approved design):

    * same ``PlanningContext`` + same profile  → byte-identical output
    * same ``PlanningContext`` + diff profile  → byte-different output
    * no experiment-identity leakage (no UUID / baseline/candidate
      strings / "[candidate-variant]" markers / thread-local / global)
    * no ``PlanningContext`` mutation
    * safety/System/Tool-marker semantics unchanged vs MockPlanningProvider
    * no import of ``evals.*`` (provider layer stays below evals runtime)

    Two profiles:
      * ``compact_v1``  — single high-leverage task, terse summary,
                          aggressive horizon focus.
      * ``structured_v1``— three explicitly-staged tasks, verbose
                           summary anchoring the structure, longer
                           horizon narrative.

    Differences are REAL (actionability, clarity, decomposition), not
    numeric noise. Both summaries differ in wording so ``PLAN_PROJECTION``
    (which includes ``summary``) produces byte-different ``output_hash``
    via the loader's ``canonical_sha256({request, plan})`` formula.

    The profile choice is sourced from ``Settings.eval_pair_smoke_planning_profile``
    — the only construction-side input.
    """

    model_id = "pair-smoke-career-planner-v1"

    _ALLOWED_PROFILES = frozenset({"compact_v1", "structured_v1"})

    def __init__(self, profile: str) -> None:
        super().__init__()
        if profile not in self._ALLOWED_PROFILES:
            raise ValueError(
                f"PairSmokePlanningProvider: unknown profile {profile!r}; "
                f"expected one of {sorted(self._ALLOWED_PROFILES)}"
            )
        self._profile = profile

    def _candidate(
        self, context: PlanningContext, replan_mode: ReplanMode
    ) -> PlanCandidate:
        """Profile-specific candidate builder.

        Reuses the parent's weekly-focus + horizon scaffolding so the
        planner-side invariants (contiguous ``week_index``, identical
        ``plan_date`` / ``horizon_start`` / ``horizon_end`` across
        profiles) are preserved; only the profile-visible parts
        (``summary``, ``rationale``, ``tasks``) differ.
        """

        # Shared scaffolding (identical across profiles for comparability).
        window = context.planning_window
        if replan_mode == ReplanMode.CONTINUE and context.source_plan is not None:
            weekly = [
                WeeklyFocusCandidate.model_validate(item.model_dump())
                for item in context.source_plan.weekly_focus[
                    : window.horizon_weeks
                ]
            ]
            while len(weekly) < window.horizon_weeks:
                index = len(weekly) + 1
                weekly.append(
                    WeeklyFocusCandidate(
                        week_index=index,
                        focus=f"第 {index} 周继续推进可验证的求职准备成果",
                        success_signal=f"第 {index} 周产出可展示证据",
                    )
                )
        else:
            weekly = [
                WeeklyFocusCandidate(
                    week_index=index,
                    focus=f"第 {index} 周完成一个可验证的求职准备增量",
                    success_signal=f"第 {index} 周产出可展示证据",
                )
                for index in range(1, window.horizon_weeks + 1)
            ]

        # Replan adjustment reason (identical across profiles — keeps
        # safety/replan semantics neutral).
        adjustment_reason = None
        if replan_mode == ReplanMode.ADJUST:
            review = context.source_review
            adjustment_reason = (
                review.adjustment_request
                if review and review.adjustment_request
                else review.replan_reason
                if review and review.replan_reason
                else review.blockers
                if review and review.blockers
                else "根据当前阻碍采用更小的行动步长"
            )

        overall_direction = (
            context.source_plan.overall_direction
            if context.source_plan is not None
            else "在规划窗口内形成可展示项目证据并推进面试准备"
        )

        if self._profile == "compact_v1":
            tasks = [
                TaskCandidate(
                    title="闭环一个可展示求职准备增量",
                    task_type=TaskType.PROJECT,
                    scheduled_date=window.planning_date,
                    starter_action="选择一个能在今天闭环的小改动并执行",
                    deliverable="一个可运行且有测试结果的项目增量",
                    estimated_minutes=max(
                        5, min(30, context.time_budget_minutes)
                    ),
                    rationale="把准备动作压缩为最小可展示单位",
                )
            ]
            summary = (
                f"[compact_v1] 单任务版本:本周聚焦一次可闭环的项目增量,"
                f"在 {window.horizon_weeks} 周窗口内形成一条清晰的证据线"
            )
            rationale = (
                "compact_v1 用单一高杠杆任务压缩决策开销,"
                "牺牲分解粒度换取执行确定性"
            )
        else:  # structured_v1
            first_minutes = max(
                5, min(15, context.time_budget_minutes // 3)
            )
            second_minutes = max(
                5, min(15, context.time_budget_minutes // 3)
            )
            third_minutes = max(
                5,
                min(
                    15,
                    context.time_budget_minutes
                    - first_minutes
                    - second_minutes,
                ),
            )
            tasks = [
                TaskCandidate(
                    title="梳理目标岗位能力差距",
                    task_type=TaskType.LEARNING,
                    scheduled_date=window.planning_date,
                    starter_action="打开岗位描述并标出三个高频能力词",
                    deliverable="一份包含三个能力差距的清单",
                    estimated_minutes=first_minutes,
                    rationale="先明确可验证的准备重点",
                ),
                TaskCandidate(
                    title="完成最小项目增量",
                    task_type=TaskType.PROJECT,
                    scheduled_date=window.planning_date,
                    starter_action="选择一个能在今天闭环的小改动并执行",
                    deliverable="一个可运行且有测试结果的项目增量",
                    estimated_minutes=second_minutes,
                    rationale="把学习内容转成可展示证据",
                ),
                TaskCandidate(
                    title="复盘并产出可复用笔记",
                    task_type=TaskType.LEARNING,
                    scheduled_date=window.planning_date,
                    starter_action="把今天的进展写成可复用的复盘要点",
                    deliverable="一份三句话的可复用复盘笔记",
                    estimated_minutes=third_minutes,
                    rationale="为下一轮迭代沉淀明确输入",
                ),
            ]
            summary = (
                f"[structured_v1] 三任务分解版本:本周按学习→项目→复盘"
                f"的显式链条推进,在 {window.horizon_weeks} 周窗口内形成"
                "可追溯的多步证据链"
            )
            rationale = (
                "structured_v1 用三阶段任务链显式承担能力差距→证据"
                "→沉淀,换取清晰度但增加协调开销"
            )

        return PlanCandidate(
            plan_date=window.planning_date,
            horizon_start=window.horizon_start,
            horizon_end=window.horizon_end,
            overall_direction=overall_direction,
            weekly_focus=weekly,
            summary=summary,
            rationale=rationale,
            adjustment_reason=adjustment_reason,
            assumptions=[],
            tasks=tasks,
            evidence_refs=[],
        )


_AGENT_VARIANT_PROFILE_MAP: dict[str, str] = {
    "compact_execution_v1": "compact_v1",
    "structured_reasoning_v1": "structured_v1",
}


def build_planning_provider(
    settings: Settings,
    agent_variant: str | None = None,
) -> PlanningProvider:
    """Build exactly the configured Provider; never silently substitute Mock.

    Stage B-1a-lite (Commit 3.5): when ``agent_variant`` is set and
    ``llm_provider == "mock"``, select a variant-specific deterministic
    provider by mapping the variant name to a PairSmoke profile. This
    lets experiments carry their own variant identity rather than
    relying on the global ``Settings.eval_pair_smoke_planning_profile``.

    ``agent_variant=None`` (or an unrecognized variant under mock) falls
    through to the legacy ``MockPlanningProvider`` path.
    """
    if settings.llm_provider == "mock":
        if agent_variant is not None:
            profile = _AGENT_VARIANT_PROFILE_MAP.get(agent_variant)
            if profile is not None:
                return PairSmokePlanningProvider(profile)
        return MockPlanningProvider()
    if settings.llm_api_key is None or settings.llm_base_url is None or settings.llm_model is None:
        raise ProviderConfigurationError(
            "openai_compatible requires LLM_API_KEY, LLM_BASE_URL, and LLM_MODEL"
        )
    provider = OpenAICompatiblePlanningProvider(
        api_key=settings.llm_api_key.get_secret_value(),
        base_url=str(settings.llm_base_url),
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
        max_output_tokens=settings.agent_max_output_tokens_per_call,
    )
    if agent_variant == "direct_llm_v1":
        return DirectLLMPlanningProvider(provider)
    return provider
