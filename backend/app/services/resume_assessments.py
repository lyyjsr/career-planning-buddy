"""Evidence-bounded Resume Claim Validation use case."""

import json
import re
from hashlib import sha256
from http import HTTPStatus
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import session_transaction
from app.core.exceptions import AppError
from app.harness.events import EventRecorder
from app.models.agent_run import AgentRun
from app.models.interview import InterviewTurn
from app.models.resume import ResumeAssessment
from app.repositories.interviews import InterviewRepository
from app.repositories.resumes import ResumeRepository
from app.schemas.interviews import TurnAnalysis
from app.schemas.resumes import (
    JobRequirement,
    ResumeAssessmentCreateRequest,
    ResumeAssessmentResponse,
    ResumeClaim,
    ResumeClaimFinding,
)
from app.services.resumes import stable_text_items


class ResumeAssessmentService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._materials = ResumeRepository(session)
        self._interviews = InterviewRepository(session)

    async def create(
        self,
        *,
        user_id: UUID,
        payload: ResumeAssessmentCreateRequest,
        idempotency_key: str,
    ) -> ResumeAssessmentResponse:
        request_hash = _hash(payload.model_dump(mode="json"))
        async with session_transaction(self._session):
            existing = await self._materials.assessment_by_key(user_id, idempotency_key)
            if existing is not None:
                if existing.request_hash != request_hash:
                    raise AppError(
                        code="STATE_IDEMPOTENCY_KEY_REUSED",
                        message="Idempotency-Key was already used with another request",
                        status_code=HTTPStatus.CONFLICT,
                    )
                return _response(existing)
            resume = await self._materials.get_resume(
                payload.resume_version_id, user_id, include_deleted=True
            )
            target = await self._materials.get_job_target(
                payload.job_target_id, user_id, include_deleted=True
            )
            interview = await self._interviews.get_session(
                payload.interview_session_id, user_id
            )
            if resume is None or target is None or interview is None:
                raise _not_found()
            if (
                interview.resume_version_id != resume.id
                or interview.job_target_id != target.id
                or interview.report_status != "ready"
            ):
                raise AppError(
                    code="STATE_RESUME_ASSESSMENT_INVALID",
                    message="assessment requires the completed interview for this Resume/JD pair",
                    status_code=HTTPStatus.CONFLICT,
                )
            turns = [
                turn
                for turn in await self._interviews.list_turns(interview.id, user_id)
                if turn.answer_status == "submitted"
            ]
            if not turns:
                raise AppError(
                    code="STATE_RESUME_ASSESSMENT_INVALID",
                    message="assessment requires at least one submitted interview answer",
                    status_code=HTTPStatus.CONFLICT,
                )
            claims = _claims(resume.structured_json, resume.source_text)
            requirements = _requirements(target.requirements_json, target.jd_text)
            findings = [_finding(claim, requirements, turns) for claim in claims]
            row = await self._materials.create_assessment(
                ResumeAssessment(
                    user_id=user_id,
                    resume_version_id=resume.id,
                    job_target_id=target.id,
                    interview_session_id=interview.id,
                    findings_json=[item.model_dump(mode="json") for item in findings],
                    limitations_json=[
                        "结论只依据所选简历、JD 与该场面试原回答，不代表背景调查。",
                        "insufficient_evidence 表示当前证据不足，不等同于主张错误。",
                    ],
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                )
            )
            run = AgentRun(
                user_id=user_id,
                run_kind="resume_assessment",
                interview_session_id=interview.id,
                idempotency_key=f"resume-assessment-{row.id}"[:64],
                request_text="Validate Resume claims against saved interview evidence",
                hint_intent="resume_assessment",
                resolved_intent="resume_assessment",
                status="completed",
                result_kind="resume_assessment",
                result_payload_json={
                    "assessment_id": str(row.id),
                    "claim_count": len(findings),
                },
                graph_version="career-coach-v2-batch3-sync",
                config_snapshot_json={
                    "execution": "deterministic_evidence_validation",
                    "provider_calls": 0,
                },
                deadline_at=row.created_at,
                finished_at=row.created_at,
            )
            self._session.add(run)
            await self._session.flush()
            await EventRecorder(self._session).record(
                run.id,
                "run.completed",
                {
                    "status": "completed",
                    "result_kind": "resume_assessment",
                    "assessment_id": str(row.id),
                },
                allow_terminal_run=True,
            )
            return _response(row)

    async def get(self, assessment_id: UUID, user_id: UUID) -> ResumeAssessmentResponse:
        async with session_transaction(self._session):
            row = await self._materials.get_assessment(assessment_id, user_id)
            if row is None:
                raise _not_found()
            return _response(row)


def _claims(structured: dict[str, object], source_text: str) -> list[ResumeClaim]:
    raw = structured.get("claims")
    values = raw if isinstance(raw, list) else stable_text_items(source_text, prefix="claim")
    claims = [ResumeClaim.model_validate(value) for value in values if isinstance(value, dict)]
    if not claims:
        raise AppError(
            code="STATE_RESUME_ASSESSMENT_INVALID",
            message="resume contains no assessable claims",
            status_code=HTTPStatus.CONFLICT,
        )
    return claims


def _requirements(structured: dict[str, object], jd_text: str) -> list[JobRequirement]:
    raw = structured.get("requirements")
    values = raw if isinstance(raw, list) else stable_text_items(jd_text, prefix="req")
    return [JobRequirement.model_validate(value) for value in values if isinstance(value, dict)]


def _tokens(value: str) -> set[str]:
    return {
        token.casefold()
        for token in re.findall(r"[A-Za-z0-9+#.]{2,}|[\u4e00-\u9fff]{2,}", value)
    }


def _similarity(left: str, right: str) -> int:
    return len(_tokens(left) & _tokens(right))


def _finding(
    claim: ResumeClaim,
    requirements: list[JobRequirement],
    turns: list[InterviewTurn],
) -> ResumeClaimFinding:
    ranked_requirements = sorted(
        requirements, key=lambda item: _similarity(claim.text, item.text), reverse=True
    )
    linked_requirements = [
        item.requirement_id
        for item in ranked_requirements[:3]
        if _similarity(claim.text, item.text)
    ]
    ranked_turns = sorted(
        turns,
        key=lambda turn: _similarity(
            claim.text,
            f"{turn.question_text} {turn.answer_text or ''}",
        ),
        reverse=True,
    )
    relevant = [
        turn
        for turn in ranked_turns[:3]
        if _similarity(
            claim.text,
            f"{turn.question_text} {turn.answer_text or ''}",
        )
    ]
    evidence_turns = relevant or ranked_turns[:1]
    explicit_error = False
    for turn in evidence_turns:
        raw_analysis = turn.analysis_json
        if not isinstance(raw_analysis, dict):
            continue
        analysis = TurnAnalysis.model_validate(raw_analysis)
        explicit_error = explicit_error or any(
            finding.verdict == "incorrect"
            and (
                _similarity(claim.text, finding.claim) > 0
                or str(turn.id) in finding.evidence_refs
            )
            for finding in analysis.factual_findings
        )
    answer_support = max(
        (_similarity(claim.text, turn.answer_text or "") for turn in relevant),
        default=0,
    )
    if explicit_error:
        verdict = "unsupported"
        rationale = "面试逐题分析对该主张给出了可回溯的明确错误证据。"
    elif answer_support >= 2 and linked_requirements:
        verdict = "supported"
        rationale = "面试回答提供了与该主张及目标岗位要求一致的具体证据。"
    elif answer_support >= 1:
        verdict = "partially_supported"
        rationale = "面试回答触及该主张，但缺少足够细节或结果证据。"
    else:
        verdict = "insufficient_evidence"
        rationale = "该场面试没有提供足够证据验证此主张；这不表示主张错误。"
    rewrite = None
    if verdict != "supported":
        rewrite = f"{claim.text}（补充本人行动、技术取舍与可验证结果后再使用）"
    return ResumeClaimFinding(
        claim_id=claim.claim_id,
        claim_text=claim.text,
        verdict=verdict,
        rationale=rationale,
        requirement_ids=linked_requirements,
        evidence_turn_ids=[turn.id for turn in evidence_turns],
        suggested_rewrite=rewrite,
    )


def _response(row: ResumeAssessment) -> ResumeAssessmentResponse:
    return ResumeAssessmentResponse(
        assessment_id=row.id,
        resume_version_id=row.resume_version_id,
        job_target_id=row.job_target_id,
        interview_session_id=row.interview_session_id,
        claims=[ResumeClaimFinding.model_validate(item) for item in row.findings_json],
        limitations=list(row.limitations_json),
        created_at=row.created_at,
    )


def _hash(value: object) -> str:
    return sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _not_found() -> AppError:
    return AppError(
        code="NOT_FOUND_RESUME_ASSESSMENT",
        message="resume assessment resource was not found",
        status_code=HTTPStatus.NOT_FOUND,
    )
