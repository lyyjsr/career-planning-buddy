"""Batch 1 immutable resume-version and job-target API contracts."""

import re
from datetime import datetime
from typing import Literal, TypedDict
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.schemas.base import StrictModel

ClaimVerdict = Literal[
    "supported", "partially_supported", "unsupported", "insufficient_evidence"
]
RewriteDecisionStatus = Literal["accepted", "rejected", "applied"]
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


class ResumeRequirementMatch(StrictModel):
    claim_id: str = Field(pattern=r"^claim_[0-9a-f]{16}$")
    requirement_id: str = Field(pattern=r"^req_[0-9a-f]{16}$")
    lexical_score: float = Field(ge=0, le=1)
    semantic_score: float = Field(ge=0, le=1)
    final_score: float = Field(ge=0, le=1)
    rationale: str = Field(min_length=1, max_length=500)


class ResumeContextCandidate(StrictModel):
    context_item_id: str = Field(pattern=r"^ctx_[0-9a-f]{16}$")
    source_type: Literal["resume_claim", "job_requirement", "interview_turn"]
    source_id: str = Field(min_length=1, max_length=64)
    source_version: int = Field(ge=1)
    content_preview: str = Field(min_length=1, max_length=1000)
    relevance_score: float = Field(ge=0, le=1)
    reliability_score: float = Field(ge=0, le=1)
    recency_score: float = Field(ge=0, le=1)
    final_score: float = Field(ge=0, le=1)
    selected: bool
    selection_reason: str | None = Field(default=None, max_length=300)
    exclusion_reason: str | None = Field(default=None, max_length=300)
    original_token_count: int = Field(ge=0)
    final_token_count: int = Field(ge=0)
    compression_method: Literal["none", "truncate", "excluded"]
    evidence_ref: str = Field(min_length=1, max_length=80)


class ResumeContextManifest(StrictModel):
    query_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    algorithm_version: str = "resume-context-hybrid-mmr-v1"
    token_budget: int = Field(ge=100, le=12000)
    used_tokens: int = Field(ge=0)
    candidates: list[ResumeContextCandidate] = Field(max_length=240)
    selected_evidence_refs: list[str] = Field(max_length=80)
    prompt_injection_filtered_count: int = Field(ge=0)


class ResumeOptimizationCandidate(StrictModel):
    claims: list[ResumeClaimFinding] = Field(min_length=1, max_length=80)
    limitations: list[str] = Field(default_factory=list, max_length=5)


class ResumeOptimizationInputSnapshot(StrictModel):
    resume_version_id: UUID
    resume_label: str
    resume_text: str = Field(min_length=20, max_length=50_000)
    resume_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    job_target_id: UUID
    job_title: str
    company: str | None
    jd_text: str = Field(min_length=20, max_length=50_000)
    jd_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    interview_session_id: UUID
    claims: list[ResumeClaim] = Field(min_length=1, max_length=80)
    requirements: list[JobRequirement] = Field(min_length=1, max_length=80)
    evidence_turns: list[dict[str, object]] = Field(min_length=1, max_length=40)
    context_manifest: ResumeContextManifest
    requirement_matches: list[ResumeRequirementMatch] = Field(max_length=240)


class ResumeOptimizationState(TypedDict, total=False):
    run_id: UUID
    user_id: UUID
    interview_session_id: UUID
    replay_of_run_id: UUID | None
    replay_fixture_only: bool
    input_snapshot: ResumeOptimizationInputSnapshot
    candidate: ResumeOptimizationCandidate


class ResumeAssessmentCreateRequest(StrictModel):
    resume_version_id: UUID
    job_target_id: UUID
    interview_session_id: UUID


class ResumeRewriteDecisionRequest(StrictModel):
    status: Literal["accepted", "rejected"]
    rewrite_text: str | None = Field(default=None, min_length=1, max_length=1000)

    @model_validator(mode="after")
    def validate_rewrite(self) -> "ResumeRewriteDecisionRequest":
        if self.status == "accepted" and not (self.rewrite_text or "").strip():
            raise ValueError("accepted rewrite requires rewrite_text")
        if self.status == "rejected" and self.rewrite_text is not None:
            raise ValueError("rejected rewrite must not include rewrite_text")
        return self


class ResumeRewriteDecisionResponse(StrictModel):
    assessment_id: UUID
    claim_id: str = Field(pattern=r"^claim_[0-9a-f]{16}$")
    status: RewriteDecisionStatus
    original_suggestion: str = Field(min_length=1, max_length=1000)
    rewrite_text: str | None = Field(default=None, max_length=1000)
    applied_resume_version_id: UUID | None
    decided_at: datetime
    applied_at: datetime | None


class ResumeAssessmentResponse(StrictModel):
    assessment_id: UUID
    resume_version_id: UUID
    job_target_id: UUID
    interview_session_id: UUID
    claims: list[ResumeClaimFinding] = Field(min_length=1, max_length=80)
    rewrite_decisions: list[ResumeRewriteDecisionResponse] = Field(default_factory=list)
    source_run_id: UUID | None = None
    context_manifest: ResumeContextManifest | None = None
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


class ResumeRewriteApplyResponse(StrictModel):
    decision: ResumeRewriteDecisionResponse
    resume_version: ResumeVersionResponse


class ResumeRewriteBatchApplyRequest(StrictModel):
    claim_ids: list[str] = Field(min_length=1, max_length=20)

    @field_validator("claim_ids")
    @classmethod
    def validate_claim_ids(cls, value: list[str]) -> list[str]:
        unique = list(dict.fromkeys(value))
        malformed = any(
            not re.fullmatch(r"claim_[0-9a-f]{16}", item) for item in value
        )
        if len(unique) != len(value) or malformed:
            raise ValueError("claim_ids must be unique stable claim ids")
        return value


class ResumeRewriteBatchApplyResponse(StrictModel):
    decisions: list[ResumeRewriteDecisionResponse]
    resume_version: ResumeVersionResponse


class ResumeOptimizationRunResponse(StrictModel):
    run_id: UUID
    status: Literal["pending"] = "pending"
    events_url: str


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
