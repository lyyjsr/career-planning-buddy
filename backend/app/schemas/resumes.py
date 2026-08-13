"""Batch 1 immutable resume-version and job-target API contracts."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.schemas.base import StrictModel

ClaimVerdict = Literal[
    "supported", "partially_supported", "unsupported", "insufficient_evidence"
]
ResumeDocumentMediaType = Literal[
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
]


class ResumeClaim(StrictModel):
    claim_id: str = Field(pattern=r"^claim_[0-9a-f]{16}$")
    text: str = Field(min_length=1, max_length=1000)
    section: str | None = Field(default=None, max_length=120)


class JobRequirement(StrictModel):
    requirement_id: str = Field(pattern=r"^req_[0-9a-f]{16}$")
    text: str = Field(min_length=1, max_length=1000)


class ResumeClaimFinding(StrictModel):
    claim_id: str = Field(pattern=r"^claim_[0-9a-f]{16}$")
    claim_text: str = Field(min_length=1, max_length=1000)
    verdict: ClaimVerdict
    rationale: str = Field(min_length=1, max_length=1000)
    requirement_ids: list[str] = Field(default_factory=list, max_length=5)
    evidence_turn_ids: list[UUID] = Field(min_length=1, max_length=6)
    suggested_rewrite: str | None = Field(default=None, max_length=1000)


class ResumeAssessmentCreateRequest(StrictModel):
    resume_version_id: UUID
    job_target_id: UUID
    interview_session_id: UUID


class ResumeAssessmentResponse(StrictModel):
    assessment_id: UUID
    resume_version_id: UUID
    job_target_id: UUID
    interview_session_id: UUID
    claims: list[ResumeClaimFinding] = Field(min_length=1, max_length=80)
    limitations: list[str] = Field(default_factory=list, max_length=5)
    created_at: datetime


class ResumeAssessmentResultSummary(StrictModel):
    assessment_id: UUID
    claim_count: int = Field(ge=1, le=80)


class ResumeVersionCreateRequest(StrictModel):
    label: str = Field(min_length=1, max_length=120)
    source_text: str = Field(min_length=20, max_length=50_000)
    source_type: Literal["pasted_text", "uploaded_file"] = "pasted_text"
    source_filename: str | None = Field(default=None, min_length=1, max_length=255)
    source_media_type: ResumeDocumentMediaType | None = None
    parent_version_id: UUID | None = None

    @model_validator(mode="after")
    def validate_source_metadata(self) -> "ResumeVersionCreateRequest":
        has_file_metadata = self.source_filename is not None or self.source_media_type is not None
        if self.source_type == "uploaded_file" and (
            self.source_filename is None or self.source_media_type is None
        ):
            raise ValueError("uploaded_file requires source_filename and source_media_type")
        if self.source_type == "pasted_text" and has_file_metadata:
            raise ValueError("pasted_text must not include file metadata")
        if self.source_filename is not None and self.source_media_type is not None:
            suffix = self.source_filename.replace("\\", "/").rsplit("/", 1)[-1].casefold()
            expected_suffix = {
                "application/pdf": ".pdf",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
                "text/plain": ".txt",
            }[self.source_media_type]
            if not suffix.endswith(expected_suffix):
                raise ValueError("source_filename must match source_media_type")
        return self


class ResumeDocumentExtractResponse(StrictModel):
    filename: str = Field(min_length=1, max_length=255)
    media_type: ResumeDocumentMediaType
    character_count: int = Field(ge=20, le=50_000)
    source_text: str = Field(min_length=20, max_length=50_000)


class ResumeVersionResponse(StrictModel):
    resume_version_id: UUID
    label: str
    source_type: Literal["pasted_text", "uploaded_file"]
    source_text: str
    structured: dict[str, object]
    content_hash: str
    parent_version_id: UUID | None
    created_at: datetime


class ResumeVersionListResponse(StrictModel):
    items: list[ResumeVersionResponse]


class JobTargetCreateRequest(StrictModel):
    title: str = Field(min_length=1, max_length=160)
    company: str | None = Field(default=None, max_length=160)
    jd_text: str = Field(min_length=20, max_length=50_000)


class JobTargetResponse(StrictModel):
    job_target_id: UUID
    title: str
    company: str | None
    jd_text: str
    requirements: dict[str, object]
    content_hash: str
    created_at: datetime


class JobTargetListResponse(StrictModel):
    items: list[JobTargetResponse]
