"""Goal clarification, deterministic sufficiency policy, and confirmation gate."""

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from hashlib import sha256
from http import HTTPStatus
from uuid import UUID

import httpx
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import session_transaction
from app.core.exceptions import AppError
from app.models.goal_brief import GoalBrief
from app.models.user_profile import UserProfile
from app.providers.goal_understanding import (
    GoalUnderstandingProvider,
    RuleGoalUnderstandingProvider,
)
from app.repositories.goal_briefs import GoalBriefRepository
from app.repositories.profiles import ProfileRepository
from app.schemas.agent_runs import AgentRunCreatedResponse
from app.schemas.enums import GoalBriefStatus, GoalType, RunStatus
from app.schemas.goal_briefs import (
    GoalBriefConfirmResponse,
    GoalBriefCreateRequest,
    GoalBriefRefineRequest,
    GoalBriefResponse,
    GoalExtraction,
)
from app.services.agent_runs import AgentRunService

GOAL_LABELS = {
    GoalType.AI_BACKEND.value: "AI 后端工程师",
    GoalType.AGENT_APP.value: "Agent 应用工程师",
    GoalType.BACKEND_JAVA.value: "Java 后端工程师",
    GoalType.DATA_ENGINEER.value: "数据工程师",
    GoalType.FULLSTACK.value: "全栈工程师",
}


class GoalBriefService:
    def __init__(
        self, session: AsyncSession, provider: GoalUnderstandingProvider, runs: AgentRunService
    ) -> None:
        self._session = session
        self._provider = provider
        self._runs_service = runs
        self._briefs = GoalBriefRepository(session)
        self._profiles = ProfileRepository(session)

    async def create(
        self, *, user_id: UUID, payload: GoalBriefCreateRequest, idempotency_key: str
    ) -> GoalBrief:
        request_hash = self._hash(payload.model_dump(mode="json"))
        async with session_transaction(self._session):
            existing = await self._briefs.get_by_idempotency(user_id, idempotency_key)
            if existing is not None:
                self._validate_idempotency(existing, request_hash)
                return existing
            profile = await self._profiles.get_for_user(user_id)
            if profile is None:
                raise AppError(
                    code="VALIDATION_PROFILE_REQUIRED",
                    message="complete the career profile before defining a plan",
                    status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                )
        extraction, method, model_id = await self._extract(payload.message)
        try:
            async with session_transaction(self._session):
                existing = await self._briefs.get_by_idempotency(user_id, idempotency_key)
                if existing is not None:
                    self._validate_idempotency(existing, request_hash)
                    return existing
                active = await self._briefs.get_active_for_user(user_id)
                if active is not None:
                    raise AppError(
                        code="STATE_GOAL_BRIEF_ALREADY_ACTIVE",
                        message="finish or cancel the current goal draft first",
                        status_code=HTTPStatus.CONFLICT,
                    )
                brief = GoalBrief(
                    user_id=user_id,
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    source_message=payload.message.strip(),
                    hint_intent=payload.hint_intent,
                    source_plan_id=payload.source_plan_id,
                    extraction_method=method,
                    model_id=model_id,
                    **self._complete(extraction.model_dump(), profile, payload.message),
                )
                await self._briefs.create(brief)
        except IntegrityError as exc:
            raise AppError(
                code="STATE_GOAL_BRIEF_ALREADY_ACTIVE",
                message="finish or cancel the current goal draft first",
                status_code=HTTPStatus.CONFLICT,
            ) from exc
        return brief

    async def get(self, brief_id: UUID, user_id: UUID) -> GoalBrief:
        brief = await self._briefs.get_for_user(brief_id, user_id)
        if brief is None:
            raise AppError(
                code="NOT_FOUND_GOAL_BRIEF",
                message="goal draft was not found",
                status_code=HTTPStatus.NOT_FOUND,
            )
        return brief

    async def refine(
        self, *, brief_id: UUID, user_id: UUID, payload: GoalBriefRefineRequest
    ) -> GoalBrief:
        extraction, method, model_id = await self._extract(payload.message)
        async with session_transaction(self._session):
            brief = await self._require_mutable(brief_id, user_id, payload.version)
            profile = await self._profiles.get_for_user(user_id)
            assert profile is not None
            current = {
                "target_role": extraction.target_role or brief.target_role,
                "project_goal": extraction.project_goal or brief.project_goal,
                "capability_focus": extraction.capability_focus or brief.capability_focus_json,
                "tech_stack": extraction.tech_stack or brief.tech_stack_json,
                "duration_weeks": extraction.duration_weeks or brief.duration_weeks,
                "deliverables": extraction.deliverables or brief.deliverables_json,
                "success_criteria": extraction.success_criteria or brief.success_criteria_json,
            }
            values = self._complete(
                current, profile, f"{brief.source_message}\n补充：{payload.message.strip()}"
            )
            brief.source_message = f"{brief.source_message}\n补充：{payload.message.strip()}"
            self._assign(brief, values)
            brief.extraction_method = method
            brief.model_id = model_id
            brief.version += 1
            brief.updated_at = datetime.now(UTC)
        return brief

    async def confirm(
        self, *, brief_id: UUID, user_id: UUID, version: int
    ) -> GoalBriefConfirmResponse:
        run = None
        should_schedule = False
        async with session_transaction(self._session):
            brief = await self._briefs.get_for_user(brief_id, user_id, for_update=True)
            if brief is None:
                raise AppError(
                    code="NOT_FOUND_GOAL_BRIEF",
                    message="goal draft was not found",
                    status_code=HTTPStatus.NOT_FOUND,
                )
            if brief.status == GoalBriefStatus.CONFIRMED.value:
                run = await self._runs_service.get_by_goal_brief(brief.id, user_id)
                if run is None:
                    raise AppError(
                        code="STATE_GOAL_BRIEF_RUN_MISSING",
                        message="confirmed goal has no Agent Run",
                        status_code=HTTPStatus.CONFLICT,
                    )
            else:
                self._check_version(brief, version)
                if brief.status != GoalBriefStatus.AWAITING_CONFIRMATION.value:
                    raise AppError(
                        code="STATE_GOAL_BRIEF_NOT_READY",
                        message="answer the remaining goal questions before confirmation",
                        status_code=HTTPStatus.CONFLICT,
                    )
                run = await self._runs_service.create(
                    user_id=user_id,
                    message=self._planning_message(brief),
                    hint_intent=brief.hint_intent,
                    goal_type_override=None,
                    source_plan_id=brief.source_plan_id,
                    idempotency_key=f"goal-{brief.id}",
                    goal_brief_id=brief.id,
                    schedule=False,
                )
                brief.status = GoalBriefStatus.CONFIRMED.value
                brief.confirmed_at = datetime.now(UTC)
                brief.updated_at = datetime.now(UTC)
                brief.version += 1
                should_schedule = True
        assert run is not None
        if should_schedule:
            self._runs_service.schedule(run.id)
        return GoalBriefConfirmResponse(
            goal_brief=self.to_response(brief),
            run=AgentRunCreatedResponse(
                run_id=run.id,
                status=RunStatus(run.status),
                events_url=f"/api/v1/agent-runs/{run.id}/events",
            ),
        )

    async def cancel(self, *, brief_id: UUID, user_id: UUID, version: int) -> GoalBrief:
        async with session_transaction(self._session):
            brief = await self._require_mutable(brief_id, user_id, version)
            brief.status = GoalBriefStatus.CANCELLED.value
            brief.cancelled_at = datetime.now(UTC)
            brief.updated_at = datetime.now(UTC)
            brief.version += 1
        return brief

    async def _extract(self, message: str) -> tuple[GoalExtraction, str, str]:
        try:
            result = await self._provider.extract(message)
            return result, self._provider.method, self._provider.model_id
        except (httpx.HTTPError, ValueError, KeyError, TypeError, ValidationError):
            fallback = RuleGoalUnderstandingProvider()
            return await fallback.extract(message), "rule_fallback", fallback.model_id

    @staticmethod
    def _complete(
        extracted: Mapping[str, object], profile: UserProfile, message: str
    ) -> dict[str, object]:
        assumptions: list[str] = []
        target = extracted.get("target_role") or GOAL_LABELS.get(profile.goal_type)
        extracted_goal = extracted.get("project_goal")
        goal = (
            extracted_goal.strip()
            if isinstance(extracted_goal, str) and extracted_goal.strip()
            else message.strip()
            if "项目" in message
            else None
        )
        duration = extracted.get("duration_weeks")
        if duration is None:
            duration = 4
            assumptions.append("未指定周期，暂按 4 周总体路线设计")
        capability = GoalBriefService._string_list(extracted.get("capability_focus"))
        if not capability:
            capability = ["岗位核心能力", "可展示的项目交付", "项目表达与复盘"]
            assumptions.append("能力重点按岗位能力、项目交付和表达复盘推荐")
        stack = GoalBriefService._string_list(extracted.get("tech_stack"))
        if not stack:
            stack = ["由系统根据目标岗位和现有能力推荐"]
            assumptions.append("技术栈未限定，将由计划阶段给出推荐")
        deliverables = GoalBriefService._string_list(extracted.get("deliverables"))
        if not deliverables:
            deliverables = ["可运行的项目成果", "README 与架构说明", "可用于简历的项目描述"]
            assumptions.append("交付物采用求职项目的标准组合")
        criteria = GoalBriefService._string_list(extracted.get("success_criteria"))
        if not criteria:
            criteria = ["核心流程可演示", "成果可被验证", "能够清楚说明关键设计取舍"]
        missing: list[str] = []
        questions: list[str] = []
        if not target:
            missing.append("target_role")
            questions.append("这个项目主要面向什么岗位或岗位方向？")
        if not goal:
            missing.append("project_goal")
            questions.append("你希望设计哪类项目，或它要解决什么具体问题？")
        return {
            "status": GoalBriefStatus.CLARIFICATION_REQUIRED.value
            if missing
            else GoalBriefStatus.AWAITING_CONFIRMATION.value,
            "target_role": target,
            "project_goal": goal,
            "capability_focus_json": capability,
            "tech_stack_json": stack,
            "duration_weeks": duration,
            "deliverables_json": deliverables,
            "success_criteria_json": criteria,
            "assumptions_json": assumptions,
            "missing_fields_json": missing,
            "questions_json": questions,
        }

    @staticmethod
    def _string_list(value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, str)]

    @staticmethod
    def _assign(brief: GoalBrief, values: dict[str, object]) -> None:
        for key, value in values.items():
            setattr(brief, key, value)

    async def _require_mutable(self, brief_id: UUID, user_id: UUID, version: int) -> GoalBrief:
        brief = await self._briefs.get_for_user(brief_id, user_id, for_update=True)
        if brief is None:
            raise AppError(
                code="NOT_FOUND_GOAL_BRIEF",
                message="goal draft was not found",
                status_code=HTTPStatus.NOT_FOUND,
            )
        self._check_version(brief, version)
        if brief.status not in {
            GoalBriefStatus.CLARIFICATION_REQUIRED.value,
            GoalBriefStatus.AWAITING_CONFIRMATION.value,
        }:
            raise AppError(
                code="STATE_GOAL_BRIEF_FINAL",
                message="goal draft is already final",
                status_code=HTTPStatus.CONFLICT,
            )
        return brief

    @staticmethod
    def _check_version(brief: GoalBrief, version: int) -> None:
        if brief.version != version:
            raise AppError(
                code="STATE_VERSION_CONFLICT",
                message="goal draft changed; refresh and retry",
                status_code=HTTPStatus.CONFLICT,
            )

    @staticmethod
    def _hash(payload: dict[str, object]) -> str:
        return sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    @staticmethod
    def _validate_idempotency(brief: GoalBrief, request_hash: str) -> None:
        if brief.request_hash != request_hash:
            raise AppError(
                code="STATE_IDEMPOTENCY_KEY_REUSED",
                message="Idempotency-Key was already used with another request",
                status_code=HTTPStatus.CONFLICT,
            )

    @staticmethod
    def _planning_message(brief: GoalBrief) -> str:
        capability_focus = "、".join(brief.capability_focus_json)
        tech_stack = "、".join(brief.tech_stack_json)
        deliverables = "、".join(brief.deliverables_json)
        success_criteria = "、".join(brief.success_criteria_json)
        return (
            f"已由用户确认的目标：面向{brief.target_role}，{brief.project_goal}。"
            f"总体周期 {brief.duration_weeks} 周；能力重点：{capability_focus}；"
            f"技术栈：{tech_stack}；交付物：{deliverables}；"
            f"成功标准：{success_criteria}。"
            "请生成总体路线，并展开从今天开始滚动未来 7 天的具体任务。"
        )

    @staticmethod
    def to_response(brief: GoalBrief) -> GoalBriefResponse:
        return GoalBriefResponse(
            goal_brief_id=brief.id,
            status=GoalBriefStatus(brief.status),
            source_message=brief.source_message,
            hint_intent=brief.hint_intent,
            source_plan_id=brief.source_plan_id,
            target_role=brief.target_role,
            project_goal=brief.project_goal,
            capability_focus=brief.capability_focus_json,
            tech_stack=brief.tech_stack_json,
            duration_weeks=brief.duration_weeks,
            deliverables=brief.deliverables_json,
            success_criteria=brief.success_criteria_json,
            assumptions=brief.assumptions_json,
            missing_fields=brief.missing_fields_json,
            questions=brief.questions_json,
            extraction_method=brief.extraction_method,
            model_id=brief.model_id,
            version=brief.version,
            created_at=brief.created_at,
            updated_at=brief.updated_at,
        )
