"""Optional LLM and deterministic adapters for goal-slot extraction."""

import json
import re
from typing import Protocol

import httpx

from app.core.config import Settings
from app.prompts.goal_understanding import goal_understanding_messages
from app.schemas.goal_briefs import GoalExtraction


class GoalUnderstandingProvider(Protocol):
    model_id: str
    method: str

    async def extract(self, message: str) -> GoalExtraction: ...


class RuleGoalUnderstandingProvider:
    model_id = "goal-rules-v1"
    method = "rule"

    async def extract(self, message: str) -> GoalExtraction:
        weeks_match = re.search(r"([1-8一二三四五六七八])\s*(?:周|星期)", message)
        week_map = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8}
        duration = None
        if weeks_match:
            raw = weeks_match.group(1)
            duration = int(raw) if raw.isdigit() else week_map[raw]
        roles = {
            "AI 后端": r"AI\s*后端|人工智能后端",
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
        project_signal = re.search(r"项目|作品|portfolio|系统|应用", message, re.I)
        return GoalExtraction(
            target_role=target,
            project_goal=message.strip() if project_signal else None,
            tech_stack=technologies,
            duration_weeks=duration,
        )


class OpenAICompatibleGoalUnderstandingProvider:
    method = "model"

    def __init__(self, *, api_key: str, base_url: str, model: str, timeout_seconds: float) -> None:
        self.model_id = model
        self._endpoint = f"{base_url.rstrip('/')}/chat/completions"
        self._timeout = timeout_seconds
        self._headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    async def extract(self, message: str) -> GoalExtraction:
        async with httpx.AsyncClient(timeout=self._timeout, headers=self._headers) as client:
            response = await client.post(
                self._endpoint,
                json={
                    "model": self.model_id,
                    "messages": goal_understanding_messages(message),
                    "temperature": 0,
                    "max_tokens": 700,
                    "response_format": {"type": "json_object"},
                },
            )
        response.raise_for_status()
        body = response.json()
        content = body["choices"][0]["message"]["content"]
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
