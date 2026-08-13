"""Bounded Resume optimization graph using persisted nodes and domain tools."""

from collections.abc import Mapping
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agent.errors import StructuredOutputError
from app.agent.finalizer import AgentRunFinalizer
from app.agent.node_runner import NodeOutput, NodeRunner, NodeTelemetry
from app.agent.resume_optimization_context import build_resume_optimization_context
from app.agent.resume_optimization_nodes import validate_faithfulness
from app.harness.budget import BudgetGuard
from app.providers.resume_optimization import ResumeOptimizationProvider
from app.schemas.agent_runs import ProviderUsage
from app.schemas.enums import GoalType, RunIntent
from app.schemas.resumes import (
    ResumeOptimizationCandidate,
    ResumeOptimizationInputSnapshot,
    ResumeOptimizationState,
)
from app.tools.contracts import ToolContext
from app.tools.registry import ToolRegistry


class ResumeOptimizationGraph:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        provider: ResumeOptimizationProvider,
        tool_registry: ToolRegistry,
        node_runner: NodeRunner,
        finalizer: AgentRunFinalizer,
        budget: BudgetGuard,
    ) -> None:
        self._sessions = session_factory
        self._provider = provider
        self._tools = tool_registry
        self._nodes = node_runner
        self._finalizer = finalizer
        self._budget = budget

    async def execute(self, state: ResumeOptimizationState) -> None:
        snapshot = await self._nodes.run(
            state["run_id"],
            "resume_context_builder",
            lambda: self._context(state),
        )
        state["input_snapshot"] = snapshot
        await self._nodes.run_with_step(
            state["run_id"],
            "resume_domain_tools",
            lambda step_id: self._domain_tools(state, snapshot, step_id),
        )
        candidate = await self._nodes.run(
            state["run_id"],
            "resume_rewrite_generator",
            lambda: self._generate(snapshot),
        )
        state["candidate"] = candidate
        validated = await self._nodes.run(
            state["run_id"],
            "resume_faithfulness_validator",
            lambda: self._validate_with_repair(candidate, snapshot),
        )
        persist_step = await self._nodes.start_step(
            state["run_id"], "resume_candidate_persist"
        )
        await self._finalizer.finalize_resume_optimization(
            run_id=state["run_id"],
            candidate=validated,
            snapshot=snapshot,
            persist_step_id=persist_step.id,
        )

    async def _context(
        self, state: ResumeOptimizationState
    ) -> NodeOutput[ResumeOptimizationInputSnapshot]:
        snapshot = await build_resume_optimization_context(
            self._sessions,
            run_id=state["run_id"],
            user_id=state["user_id"],
            interview_session_id=state["interview_session_id"],
            frozen_snapshot=(state.get("input_snapshot") or None),
        )
        manifest = snapshot.context_manifest
        return NodeOutput(
            snapshot,
            NodeTelemetry(
                trace_data={
                    "algorithm_version": manifest.algorithm_version,
                    "candidate_count": len(manifest.candidates),
                    "selected_count": len(manifest.selected_evidence_refs),
                    "used_tokens": manifest.used_tokens,
                    "token_budget": manifest.token_budget,
                    "prompt_injection_filtered_count": manifest.prompt_injection_filtered_count,
                    "selection_manifest": manifest.model_dump(mode="json"),
                }
            ),
        )

    async def _domain_tools(
        self,
        state: ResumeOptimizationState,
        snapshot: ResumeOptimizationInputSnapshot,
        step_id: UUID,
    ) -> NodeOutput[None]:
        context = ToolContext(
            run_id=state["run_id"], user_id=state["user_id"],
            goal_type=GoalType.AGENT_APP, intent=RunIntent.RESUME_OPTIMIZATION,
            remaining_deadline_ms=max(int(self._budget.remaining_seconds() * 1000), 1),
            replay_fixture_run_id=state.get("replay_of_run_id"),
            fixture_only=state.get("replay_fixture_only", False),
        )
        selected_claims = snapshot.claims[: min(2, len(snapshot.claims))]
        calls: list[dict[str, object]] = []
        gap = await self._tools.execute(
            tool_name="resume_gap_analyze",
            arguments={
                "resume_version_id": str(snapshot.resume_version_id),
                "job_target_id": str(snapshot.job_target_id),
                "claim_ids": [item.claim_id for item in selected_claims],
            },
            context=context, step_id=step_id, round_number=1,
        )
        calls.append({"tool": "resume_gap_analyze", "success": gap.success, "reused": gap.reused})
        if selected_claims:
            evidence = await self._tools.execute(
                tool_name="interview_evidence_retrieve",
                arguments={
                    "interview_session_id": str(snapshot.interview_session_id),
                    "claim_id": selected_claims[0].claim_id,
                    "claim_text": selected_claims[0].text,
                    "limit": 5,
                },
                context=context, step_id=step_id, round_number=1,
            )
            calls.append(
                {
                    "tool": "interview_evidence_retrieve",
                    "success": evidence.success,
                    "reused": evidence.reused,
                }
            )
        if not all(bool(item["success"]) for item in calls):
            raise StructuredOutputError("required Resume domain tool failed")
        return NodeOutput(None, NodeTelemetry(trace_data={"tool_calls": calls}))

    async def _generate(
        self, snapshot: ResumeOptimizationInputSnapshot
    ) -> NodeOutput[ResumeOptimizationCandidate]:
        raw = await self._provider.generate(snapshot)
        try:
            candidate, usage = self._parse(raw)
            self._budget.record_llm_call(usage.tokens_in, usage.tokens_out)
        except (ValidationError, ValueError) as exc:
            self._budget.claim_format_repair()
            repaired = await self._provider.repair(snapshot, raw, str(exc))
            candidate, usage = self._parse(repaired)
            self._budget.record_llm_call(usage.tokens_in, usage.tokens_out)
        return NodeOutput(
            candidate,
            NodeTelemetry(
                trace_data={"operation": "resume_optimization"},
                tokens_in=usage.tokens_in, tokens_out=usage.tokens_out,
                cost_cny=usage.cost_cny, model_id=usage.model_id,
                prompt_version="resume-optimization-evidence-v1",
            ),
        )

    async def _validate_with_repair(
        self,
        candidate: ResumeOptimizationCandidate,
        snapshot: ResumeOptimizationInputSnapshot,
    ) -> NodeOutput[ResumeOptimizationCandidate]:
        try:
            value = validate_faithfulness(candidate, snapshot)
            return NodeOutput(value, NodeTelemetry(trace_data={"faithfulness_valid": True}))
        except StructuredOutputError as exc:
            if not self._budget.claim_business_repair():
                raise
            repaired = await self._provider.repair(snapshot, candidate, str(exc))
            value, usage = self._parse(repaired)
            self._budget.record_llm_call(usage.tokens_in, usage.tokens_out)
            validated = validate_faithfulness(value, snapshot)
            return NodeOutput(
                validated,
                NodeTelemetry(
                    trace_data={"faithfulness_valid": True, "business_repair": True},
                    tokens_in=usage.tokens_in, tokens_out=usage.tokens_out,
                    cost_cny=usage.cost_cny, model_id=usage.model_id,
                    prompt_version="resume-optimization-evidence-v1",
                ),
            )

    @staticmethod
    def _parse(raw: Mapping[str, object]) -> tuple[ResumeOptimizationCandidate, ProviderUsage]:
        usage = ProviderUsage.model_validate(raw.get("usage"))
        payload = {key: value for key, value in raw.items() if key != "usage"}
        return ResumeOptimizationCandidate.model_validate(payload), usage
