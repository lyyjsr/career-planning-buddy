"""Provider-neutral LLM client compatibility and telemetry tests."""

import json

import httpx
import pytest

from app.core.telemetry import bind_telemetry_context
from app.providers.llm_client import OpenAIChatLLMClient
from app.providers.llm_contracts import (
    LLMCallTelemetry,
    LLMMessage,
    LLMProviderProfile,
    LLMRequest,
)
from app.providers.llm_profiles import resolve_provider_profile


class CapturingTelemetry:
    def __init__(self) -> None:
        self.events: list[LLMCallTelemetry] = []

    def emit(self, event: LLMCallTelemetry) -> None:
        self.events.append(event)


@pytest.mark.asyncio
async def test_glm_profile_maps_reasoning_and_normalizes_usage() -> None:
    captured: dict[str, object] = {}
    telemetry = CapturingTelemetry()

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            request=request,
            headers={"x-request-id": "glm-request-1"},
            json={
                "id": "glm-completion-1",
                "model": "glm-4.7",
                "choices": [
                    {"finish_reason": "stop", "message": {"content": '{"ok":true}'}}
                ],
                "usage": {
                    "prompt_tokens": 21,
                    "completion_tokens": 13,
                    "completion_tokens_details": {"reasoning_tokens": 8},
                },
            },
        )

    profile = resolve_provider_profile(
        configured_name="auto", base_url="https://open.bigmodel.cn/api/paas/v4"
    )
    client = OpenAIChatLLMClient(
        api_key="test-only",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        profile=profile,
        timeout_seconds=5,
        transport=httpx.MockTransport(handler),
        telemetry=telemetry,
    )
    with bind_telemetry_context(trace_id="trace-1", run_id="run-1"):
        response = await client.complete(
            LLMRequest(
                operation="goal_understanding",
                model="glm-4.7",
                messages=[LLMMessage(role="user", content="extract")],
                structured_output="json_object",
                reasoning="off",
                temperature=0,
                max_output_tokens=700,
            )
        )
    await client.aclose()

    assert profile.provider_id == "zhipu"
    assert captured["thinking"] == {"type": "disabled"}
    assert captured["response_format"] == {"type": "json_object"}
    assert response.usage.input_tokens == 21
    assert response.usage.output_tokens == 13
    assert response.usage.reasoning_tokens == 8
    assert telemetry.events[0].trace_id == "trace-1"
    assert telemetry.events[0].run_id == "run-1"
    assert telemetry.events[0].request_id == "glm-request-1"


def test_generic_compatible_profile_does_not_guess_vendor_parameters() -> None:
    profile = resolve_provider_profile(
        configured_name="auto", base_url="https://gateway.example.test/v1"
    )

    assert profile == LLMProviderProfile(provider_id="openai_compatible")
    assert profile.supports_reasoning_control is False
