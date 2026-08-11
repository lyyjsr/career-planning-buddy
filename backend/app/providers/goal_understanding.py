"""Optional LLM and deterministic adapters for goal-slot extraction."""

import json
import re
from collections.abc import Mapping
from typing import Protocol
from urllib.parse import urlparse

import httpx

from app.core.config import Settings
from app.prompts.goal_understanding import goal_understanding_messages
from app.schemas.enums import ObjectiveType
from app.schemas.goal_briefs import GoalExtraction

OBJECTIVE_PATTERNS: tuple[tuple[ObjectiveType, re.Pattern[str]], ...] = (
    (
        ObjectiveType.CAREER_PLAN,
        re.compile(r"求职|职业|岗位规划|秋招|春招|job search|career", re.I),
    ),
    (ObjectiveType.APPLICATION, re.compile(r"投递|申请|简历投递|application|apply", re.I)),
    (ObjectiveType.INTERVIEW, re.compile(r"面试|mock interview|interview", re.I)),
    (ObjectiveType.PROJECT, re.compile(r"项目|作品|portfolio|系统|应用", re.I)),
    (
        ObjectiveType.SKILL_TRANSITION,
        re.compile(r"技能|学习|转型|转行|skill|transition", re.I),
    ),
)


def classify_objective_type(message: str) -> ObjectiveType | None:
    return next(
        (
            objective_type
            for objective_type, pattern in OBJECTIVE_PATTERNS
            if pattern.search(message)
        ),
        None,
    )


def parse_duration_weeks(message: str) -> int | None:
    """Parse the bounded Chinese duration phrases supported by the product."""
    week_match = re.search(r"([1-8一二两三四五六七八])\s*(?:周|星期)", message)
    week_map = {
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
    }
    if week_match:
        raw = week_match.group(1)
        return int(raw) if raw.isdigit() else week_map[raw]
    if re.search(r"半个?月", message):
        return 2
    month_match = re.search(r"([12一二两])\s*个?月", message)
    if month_match:
        raw = month_match.group(1)
        months = int(raw) if raw.isdigit() else 1 if raw == "一" else 2
        return months * 4
    return None


class GoalUnderstandingProvider(Protocol):
    model_id: str
    method: str

    async def extract(self, message: str) -> GoalExtraction: ...


class RuleGoalUnderstandingProvider:
    model_id = "goal-rules-v2"
    method = "rule"

    async def extract(self, message: str) -> GoalExtraction:
        roles = {
            "AI 后端工程师": r"AI\s*后端|人工智能后端",
            "Agent 应用工程师": r"Agent|智能体",
            "Java 后端工程师": r"Java\s*后端",
            "数据工程师": r"数据工程师|数据开发",
            "全栈工程师": r"全栈",
        }
        target = next(
            (label for label, pattern in roles.items() if re.search(pattern, message, re.I)), None
        )
        technologies = [
            name
            for name in (
                "Python",
                "Java",
                "FastAPI",
                "Spring Boot",
                "React",
                "LangGraph",
                "Docker",
                "PostgreSQL",
            )
            if re.search(re.escape(name), message, re.I)
        ]
        objective_type = classify_objective_type(message)
        return GoalExtraction(
            objective_type=objective_type,
            target_role=target,
            objective=message.strip() if objective_type is not None else None,
            tech_stack=technologies,
            duration_weeks=parse_duration_weeks(message),
        )


class OpenAICompatibleGoalUnderstandingProvider:
    method = "model"

    def __init__(self, *, api_key: str, base_url: str, model: str, timeout_seconds: float) -> None:
        self.model_id = model
        self._endpoint = f"{base_url.rstrip('/')}/chat/completions"
        self._timeout = timeout_seconds
        provider_host = (urlparse(base_url).hostname or "").lower()
        self._supports_thinking_control = provider_host == "api.deepseek.com" or (
            provider_host.endswith(".deepseek.com")
        )
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def extract(self, message: str) -> GoalExtraction:
        request_body: dict[str, object] = {
            "model": self.model_id,
            "messages": goal_understanding_messages(message),
            "temperature": 0,
            "max_tokens": 700,
            "response_format": {"type": "json_object"},
        }
        if self._supports_thinking_control:
            request_body["thinking"] = {"type": "disabled"}
        async with httpx.AsyncClient(timeout=self._timeout, headers=self._headers) as client:
            response = await client.post(
                self._endpoint,
                json=request_body,
            )
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, Mapping):
            raise ValueError("goal Provider returned an invalid response")
        choices = body.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], Mapping):
            raise ValueError("goal Provider returned no choices")
        response_message = choices[0].get("message")
        if not isinstance(response_message, Mapping):
            raise ValueError("goal Provider returned no message")
        content = response_message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("goal Provider returned empty content")
        return GoalExtraction.model_validate(json.loads(content))


def build_goal_understanding_provider(settings: Settings) -> GoalUnderstandingProvider:
    if settings.llm_provider == "mock":
        return RuleGoalUnderstandingProvider()
    assert settings.llm_api_key is not None
    assert settings.llm_base_url is not None
    assert settings.llm_model is not None
    return OpenAICompatibleGoalUnderstandingProvider(
        api_key=settings.llm_api_key.get_secret_value(),
        base_url=str(settings.llm_base_url),
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
    )
