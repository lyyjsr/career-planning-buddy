"""Immutable ResumeVersion and JobTarget HTTP resources."""

from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Header, UploadFile

from app.api.dependencies import (
    get_current_user,
    get_resume_document_service,
    get_resume_service,
)
from app.core.security import AuthenticatedUser
from app.schemas.resumes import (
    JobTargetCreateRequest,
    JobTargetListResponse,
    JobTargetResponse,
    ResumeDocumentExtractResponse,
    ResumeVersionCreateRequest,
    ResumeVersionListResponse,
    ResumeVersionResponse,
)
from app.services.resume_documents import MAX_RESUME_FILE_BYTES, ResumeDocumentService
from app.services.resumes import ResumeService

resume_router = APIRouter(prefix="/resume-versions", tags=["resume-versions"])
job_target_router = APIRouter(prefix="/job-targets", tags=["job-targets"])


@resume_router.post("/extract", response_model=ResumeDocumentExtractResponse)
async def extract_resume_document(
    file: Annotated[UploadFile, File()],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[ResumeDocumentService, Depends(get_resume_document_service)],
) -> ResumeDocumentExtractResponse:
    _ = current_user
    filename = file.filename or ""
    media_type = file.content_type or "application/octet-stream"
    try:
        content = await file.read(MAX_RESUME_FILE_BYTES + 1)
    finally:
        await file.close()
    return service.extract(filename=filename, media_type=media_type, content=content)


@resume_router.post("", status_code=HTTPStatus.CREATED, response_model=ResumeVersionResponse)
async def create_resume_version(
    payload: ResumeVersionCreateRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[ResumeService, Depends(get_resume_service)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=64)],
) -> ResumeVersionResponse:
    return await service.create_resume(
        user_id=current_user.id,
        payload=payload,
        idempotency_key=idempotency_key,
    )


@resume_router.get("", response_model=ResumeVersionListResponse)
async def list_resume_versions(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[ResumeService, Depends(get_resume_service)],
) -> ResumeVersionListResponse:
    return ResumeVersionListResponse(items=await service.list_resumes(current_user.id))


@resume_router.delete("/{resume_id}", status_code=HTTPStatus.NO_CONTENT)
async def delete_resume_version(
    resume_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[ResumeService, Depends(get_resume_service)],
) -> None:
    await service.delete_resume(resume_id, current_user.id)


@job_target_router.post("", status_code=HTTPStatus.CREATED, response_model=JobTargetResponse)
async def create_job_target(
    payload: JobTargetCreateRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[ResumeService, Depends(get_resume_service)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=64)],
) -> JobTargetResponse:
    return await service.create_job_target(
        user_id=current_user.id,
        payload=payload,
        idempotency_key=idempotency_key,
    )


@job_target_router.get("", response_model=JobTargetListResponse)
async def list_job_targets(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[ResumeService, Depends(get_resume_service)],
) -> JobTargetListResponse:
    return JobTargetListResponse(items=await service.list_job_targets(current_user.id))


@job_target_router.delete("/{target_id}", status_code=HTTPStatus.NO_CONTENT)
async def delete_job_target(
    target_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[ResumeService, Depends(get_resume_service)],
) -> None:
    await service.delete_job_target(target_id, current_user.id)
