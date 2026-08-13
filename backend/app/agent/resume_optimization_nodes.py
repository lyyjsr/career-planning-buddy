"""Deterministic candidate fallback and strict evidence-faithfulness validation."""

import re

from app.agent.errors import StructuredOutputError
from app.agent.resume_context_selection import lexical_similarity
from app.schemas.resumes import (
    ResumeClaimFinding,
    ResumeOptimizationCandidate,
    ResumeOptimizationInputSnapshot,
)

_NUMERIC = re.compile(r"(?<![\w])\d+(?:\.\d+)?\s*(?:%|ms|s|秒|分钟|万|k|m)?", re.I)
_OWNERSHIP = ("主导", "负责", "独立", "owner", "led", "architected")


def deterministic_candidate(
    snapshot: ResumeOptimizationInputSnapshot,
) -> ResumeOptimizationCandidate:
    findings: list[ResumeClaimFinding] = []
    selected_turns = [
        item for item in snapshot.evidence_turns
        if f"interview_turn:{item['turn_id']}" in snapshot.context_manifest.selected_evidence_refs
    ]
    # A low-relevance turn is still valid evidence of absence. Keep one frozen
    # turn so an insufficient-evidence finding remains auditable.
    evidence_pool = selected_turns or snapshot.evidence_turns
    for claim in snapshot.claims:
        linked = sorted(
            [item for item in snapshot.requirement_matches if item.claim_id == claim.claim_id],
            key=lambda item: -item.final_score,
        )
        ranked_turns = sorted(
            evidence_pool,
            key=lambda turn: -lexical_similarity(
                claim.text, f"{turn.get('question_text', '')} {turn.get('answer_text', '')}"
            ),
        )
        relevant = [
            turn for turn in ranked_turns
            if lexical_similarity(claim.text, str(turn.get("answer_text", ""))) >= 0.08
        ][:3]
        conflict = any(
            _explicit_conflict(claim.text, turn.get("analysis_json"))
            for turn in relevant
        )
        support = max(
            (lexical_similarity(claim.text, str(turn.get("answer_text", ""))) for turn in relevant),
            default=0.0,
        )
        if conflict:
            verdict, rationale = "unsupported", "面试分析中存在与该主张直接相关的冲突证据。"
        elif support >= 0.28 and linked and linked[0].final_score >= 0.12:
            verdict, rationale = "supported", "面试回答与目标要求共同提供了可回溯支持。"
        elif support >= 0.08:
            verdict, rationale = "partially_supported", "回答提供了相关行动，但细节或结果仍不完整。"
        else:
            verdict, rationale = "insufficient_evidence", "当前面试证据不足以验证该主张。"
        rewrite = None
        if verdict != "supported":
            rewrite = _conservative_rewrite(claim.text, verdict)
        findings.append(
            ResumeClaimFinding(
                claim_id=claim.claim_id, claim_text=claim.text, verdict=verdict,
                rationale=rationale,
                requirement_ids=[
                    item.requirement_id for item in linked if item.final_score >= 0.08
                ],
                evidence_turn_ids=[turn["turn_id"] for turn in (relevant or ranked_turns[:1])],
                suggested_rewrite=rewrite,
            )
        )
    return ResumeOptimizationCandidate(
        claims=findings,
        limitations=[
            "结论仅依据冻结的简历、JD 与所选面试证据。",
            "证据不足不等同于主张错误；候选改写不会自动覆盖原简历。",
        ],
    )


def validate_faithfulness(
    candidate: ResumeOptimizationCandidate,
    snapshot: ResumeOptimizationInputSnapshot,
) -> ResumeOptimizationCandidate:
    claim_map = {item.claim_id: item for item in snapshot.claims}
    turn_map = {str(item["turn_id"]): item for item in snapshot.evidence_turns}
    requirement_ids = {item.requirement_id for item in snapshot.requirements}
    if {item.claim_id for item in candidate.claims} != set(claim_map):
        raise StructuredOutputError("candidate must cover every frozen Resume claim exactly once")
    validated: list[ResumeClaimFinding] = []
    for finding in candidate.claims:
        original = claim_map[finding.claim_id].text
        if finding.claim_text != original:
            raise StructuredOutputError("candidate changed the frozen claim identity")
        if any(item not in requirement_ids for item in finding.requirement_ids):
            raise StructuredOutputError("candidate cited an unavailable requirement")
        evidence = [turn_map.get(str(item)) for item in finding.evidence_turn_ids]
        if not evidence or any(item is None for item in evidence):
            raise StructuredOutputError("candidate cited an unavailable interview turn")
        rewrite = finding.suggested_rewrite
        if rewrite:
            evidence_text = " ".join(str(item.get("answer_text", "")) for item in evidence if item)
            allowed_text = f"{original} {evidence_text}"
            invented_numbers = set(_NUMERIC.findall(rewrite)) - set(_NUMERIC.findall(allowed_text))
            if invented_numbers:
                raise StructuredOutputError("rewrite introduced unsupported numeric facts")
            for term in _OWNERSHIP:
                if (
                    term.casefold() in rewrite.casefold()
                    and term.casefold() not in allowed_text.casefold()
                ):
                    raise StructuredOutputError("rewrite escalated unsupported ownership")
            if finding.verdict == "insufficient_evidence" and rewrite != (
                _conservative_rewrite(original, finding.verdict)
            ):
                raise StructuredOutputError(
                    "insufficient evidence rewrite must preserve uncertainty"
                )
        validated.append(finding)
    return candidate.model_copy(update={"claims": validated})


def _conservative_rewrite(claim: str, verdict: str) -> str:
    if verdict == "unsupported":
        return f"参与相关工作：{claim}（仅保留可由现有材料验证的职责与结果）"
    return f"参与相关工作：{claim}（具体职责与结果待补充可验证证据）"


def _explicit_conflict(claim: str, analysis: object) -> bool:
    if not isinstance(analysis, dict):
        return False
    return any(
        isinstance(item, dict)
        and item.get("verdict") == "incorrect"
        and lexical_similarity(claim, str(item.get("claim", ""))) > 0
        for item in analysis.get("factual_findings", [])
    )
