"""Resume Claim Validation HTTP resources."""

from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header

from app.api.dependencies import get_current_user, get_resume_assessment_service
from app.core.security import AuthenticatedUser
from app.schemas.resumes import ResumeAssessmentCreateRequest, ResumeAssessmentResponse
from app.services.resume_assessments import ResumeAssessmentService

router = APIRouter(prefix="/resume-assessments", tags=["resume-assessments"])


@router.post("", status_code=HTTPStatus.CREATED, response_model=ResumeAssessmentResponse)
async def create_resume_assessment(
    payload: ResumeAssessmentCreateRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[ResumeAssessmentService, Depends(get_resume_assessment_service)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=64)],
) -> ResumeAssessmentResponse:
    return await service.create(
        user_id=current_user.id, payload=payload, idempotency_key=idempotency_key
    )


@router.get("/{assessment_id}", response_model=ResumeAssessmentResponse)
async def get_resume_assessment(
    assessment_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[ResumeAssessmentService, Depends(get_resume_assessment_service)],
) -> ResumeAssessmentResponse:
    return await service.get(assessment_id, current_user.id)
