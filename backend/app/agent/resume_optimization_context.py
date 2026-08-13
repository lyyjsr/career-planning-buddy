"""Build and freeze Resume optimization inputs from user-owned resources."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agent.resume_context_selection import (
    build_resume_context_manifest,
    requirement_matches,
)
from app.core.database import session_transaction
from app.repositories.interviews import InterviewRepository
from app.repositories.resumes import ResumeRepository
from app.schemas.resumes import (
    JobRequirement,
    ResumeClaim,
    ResumeOptimizationInputSnapshot,
)
from app.services.resumes import stable_text_items


async def build_resume_optimization_context(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    run_id: UUID,
    user_id: UUID,
    interview_session_id: UUID,
    frozen_snapshot: dict[str, object] | None = None,
) -> ResumeOptimizationInputSnapshot:
    if frozen_snapshot is not None:
        return ResumeOptimizationInputSnapshot.model_validate(frozen_snapshot)
    async with session_factory() as session:
        async with session_transaction(session):
            interviews = InterviewRepository(session)
            materials = ResumeRepository(session)
            interview = await interviews.get_session(interview_session_id, user_id)
            if interview is None or interview.report_status != "ready":
                raise ValueError("resume optimization requires a completed interview")
            resume = await materials.get_resume(
                interview.resume_version_id, user_id, include_deleted=True
            )
            target = await materials.get_job_target(
                interview.job_target_id, user_id, include_deleted=True
            )
            if resume is None or target is None:
                raise ValueError("frozen Resume or JobTarget is missing")
            turns = [
                item for item in await interviews.list_turns(interview.id, user_id)
                if item.answer_status == "submitted" and item.answer_text
            ]
            if not turns:
                raise ValueError("resume optimization requires submitted answers")
            claims = [
                ResumeClaim.model_validate(item)
                for item in resume.structured_json.get(
                    "claims", stable_text_items(resume.source_text, prefix="claim")
                )
                if isinstance(item, dict)
            ]
            requirements = [
                JobRequirement.model_validate(item)
                for item in target.requirements_json.get(
                    "requirements", stable_text_items(target.jd_text, prefix="req")
                )
                if isinstance(item, dict)
            ]
            evidence_turns = [
                {
                    "turn_id": str(item.id),
                    "question_text": item.question_text,
                    "answer_text": item.answer_text,
                    "analysis_json": item.analysis_json,
                    "answered_at": item.answered_at.isoformat() if item.answered_at else None,
                }
                for item in turns
            ]
            matches = requirement_matches(claims, requirements)
            manifest = build_resume_context_manifest(
                claims=claims,
                requirements=requirements,
                evidence_turns=evidence_turns,
                matches=matches,
            )
            snapshot = ResumeOptimizationInputSnapshot(
                resume_version_id=resume.id,
                resume_label=resume.label,
                resume_text=resume.source_text,
                resume_hash=resume.content_hash,
                job_target_id=target.id,
                job_title=target.title,
                company=target.company,
                jd_text=target.jd_text,
                jd_hash=target.content_hash,
                interview_session_id=interview.id,
                claims=claims,
                requirements=requirements,
                evidence_turns=evidence_turns,
                context_manifest=manifest,
                requirement_matches=matches,
            )
            from app.harness.snapshots import SnapshotService

            await SnapshotService.write_interview_input_once(
                session, run_id, snapshot.model_dump(mode="json")
            )
            return snapshot
