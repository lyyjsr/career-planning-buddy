"""Fixed Stage 4 planning/replanning graph topology and node orchestration."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langsmith import tracing_context
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agent.errors import StructuredOutputError
from app.agent.finalizer import AgentRunFinalizer
from app.agent.node_runner import NodeOutput, NodeRunner, NodeTelemetry
from app.agent.nodes import (
    build_clarification,
    build_companion,
    build_planning_context,
    build_safe_response,
    fallback_candidate,
    risk_gate,
    route_intent,
    validate_candidate,
)
from app.core.database import session_transaction
from app.harness.budget import BudgetGuard
from app.harness.snapshots import SnapshotService
from app.models.agent_run import AgentRun
from app.models.plan import Plan
from app.models.review import Review
from app.models.user_profile import UserProfile
from app.providers.llm import PlanningProvider
from app.repositories.evidence import EvidenceRepository
from app.repositories.plans import PlanRepository
from app.repositories.reviews import ReviewRepository
from app.schemas.agent_runs import (
    AgentTurnResponse,
    EvidenceCatalogItem,
    MemoryContext,
    PlanCandidate,
    PlanContext,
    PlanFocusContext,
    PlanningContext,
    PlanningState,
    ProfileContext,
    ProviderPlanResponse,
    ProviderUsage,
    ReviewContext,
    RunInputSnapshot,
    TaskContext,
)
from app.schemas.enums import PlanStatus, RunIntent, TaskStatus
from app.tools.contracts import ToolContext
from app.tools.registry import ToolRegistry


class FixedPlanningGraph:
    """Explicit, bounded topology matching the Stage 2 runtime specification."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        provider: PlanningProvider,
        node_runner: NodeRunner,
        finalizer: AgentRunFinalizer,
        budget: BudgetGuard,
        tool_registry: ToolRegistry,
    ) -> None:
        self._session_factory = session_factory
        self._provider = provider
        self._nodes = node_runner
        self._finalizer = finalizer
        self._budget = budget
        self._tool_registry = tool_registry
        self._graph = self._build_graph()

    async def execute(self, state: PlanningState) -> None:
        with tracing_context(enabled=False):
            await self._graph.ainvoke(state)

    def _build_graph(
        self,
    ) -> CompiledStateGraph[PlanningState, None, PlanningState, PlanningState]:
        builder = StateGraph(PlanningState)
        builder.add_node("risk_gate", self._risk_node)
        builder.add_node("safe_response", self._safe_response_node)
        builder.add_node("intent_router", self._intent_node)
        builder.add_node("clarification", self._clarification_node)
        builder.add_node("context_builder", self._context_node)
        builder.add_node("career_planning_agent", self._agent_node)
        builder.add_node("rule_validator", self._validator_node)
        builder.add_node("revise_or_fallback", self._revise_node)
        builder.add_node("companion_response", self._companion_node)
        builder.add_node("persist", self._persist_node)
        builder.add_edge(START, "risk_gate")
        builder.add_conditional_edges(
            "risk_gate",
            self._after_risk,
            {"high": "safe_response", "safe": "intent_router"},
        )
        builder.add_edge("safe_response", END)
        builder.add_conditional_edges(
            "intent_router",
            self._after_intent,
            {"clarification": "clarification", "ready": "context_builder"},
        )
        builder.add_edge("clarification", END)
        builder.add_edge("context_builder", "career_planning_agent")
        builder.add_edge("career_planning_agent", "rule_validator")
        builder.add_conditional_edges(
            "rule_validator",
            self._after_validation,
            {"passed": "companion_response", "repair": "revise_or_fallback"},
        )
        builder.add_edge("revise_or_fallback", "rule_validator")
        builder.add_edge("companion_response", "persist")
        builder.add_edge("persist", END)
        return builder.compile()

    async def _risk_node(self, state: PlanningState) -> dict[str, object]:
        run_id = state["run_id"]
        request = state["request"]
        risk = await self._nodes.run(
            run_id,
            "risk_gate",
            lambda: self._immediate(
                risk_gate(request.message),
                {"method": "rule"},
            ),
        )
        await self._update_run(run_id, risk_category=risk.category)
        return {"risk": risk}

    async def _safe_response_node(self, state: PlanningState) -> dict[str, object]:
        risk = state["risk"]
        safe = await self._nodes.run(
            state["run_id"],
            "safe_response",
            lambda: self._immediate(build_safe_response(), {"category": risk.category}),
        )
        await self._finalizer.finalize_degraded(
            run_id=state["run_id"],
            result_kind="safe_response",
            result=safe,
            fallback_reason="high_risk_routed",
        )
        return {}

    async def _intent_node(self, state: PlanningState) -> dict[str, object]:
        run_id = state["run_id"]
        request = state["request"]
        source_plan_exists = request.source_plan_id is not None
        intent = await self._nodes.run(
            run_id,
            "intent_router",
            lambda: self._immediate(
                route_intent(
                    message=request.message,
                    hint_intent=request.hint_intent,
                    profile=state["profile"],
                    source_plan_exists=source_plan_exists,
                    forced_replan_mode=state.get("server_replan_mode"),
                ),
                {"method": "rule"},
            ),
        )
        await self._update_run(
            run_id,
            resolved_intent=intent.intent.value,
            replan_mode=intent.replan_mode.value,
            requested_horizon_weeks=intent.requested_horizon_weeks,
        )
        return {"intent": intent}

    async def _clarification_node(self, state: PlanningState) -> dict[str, object]:
        intent = state["intent"]
        clarification = await self._nodes.run(
            state["run_id"],
            "clarification",
            lambda: self._immediate(
                build_clarification(intent),
                {"reason": "profile_incomplete" if intent.missing_slots else "unsupported"},
            ),
        )
        await self._finalizer.finalize_degraded(
            run_id=state["run_id"],
            result_kind="clarification",
            result=clarification,
            fallback_reason=clarification.reason,
        )
        return {}

    async def _context_node(self, state: PlanningState) -> dict[str, object]:
        context, evidence_catalog = await self._nodes.run(
            state["run_id"],
            "context_builder",
            lambda: self._build_context(state),
        )
        return {
            "planning_context": context,
            "evidence_catalog": evidence_catalog,
            "tool_round": 0,
            "tool_call_count": 0,
        }

    async def _agent_node(self, state: PlanningState) -> dict[str, object]:
        candidate, evidence_catalog, tool_round, tool_call_count = await self._nodes.run_with_step(
            state["run_id"],
            "career_planning_agent",
            lambda step_id: self._generate_candidate(state, step_id),
        )
        result: dict[str, object] = {
            "candidate_plan": candidate,
            "evidence_catalog": evidence_catalog,
            "tool_round": tool_round,
            "tool_call_count": tool_call_count,
        }
        if state.get("fallback_reason") is not None:
            result["fallback_reason"] = state["fallback_reason"]
        return result

    async def _validator_node(self, state: PlanningState) -> dict[str, object]:
        attempt = state.get("validation_attempt", 0) + 1
        validation = await self._nodes.run(
            state["run_id"],
            "rule_validator",
            lambda: self._immediate(
                validate_candidate(
                    state["candidate_plan"],
                    state["planning_context"],
                    state.get("evidence_catalog", []),
                ),
                {"check_count": 13, "attempt": attempt},
            ),
            attempt=attempt,
        )
        return {
            "validation_report": validation,
            "validation_attempt": attempt,
        }

    async def _revise_node(self, state: PlanningState) -> dict[str, object]:
        candidate, fallback_reason = await self._nodes.run(
            state["run_id"],
            "revise_or_fallback",
            lambda: self._revise_or_fallback(state),
            attempt=state.get("repair_count", 0) + 1,
        )
        return {
            "candidate_plan": candidate,
            "fallback_reason": fallback_reason,
            "repair_count": state.get("repair_count", 0) + 1,
        }

    async def _companion_node(self, state: PlanningState) -> dict[str, object]:
        companion = await self._nodes.run(
            state["run_id"],
            "companion_response",
            lambda: self._immediate(
                build_companion(state["candidate_plan"]),
                {"template_version": "plan_ready_v1"},
            ),
        )
        return {"companion": companion}

    async def _persist_node(self, state: PlanningState) -> dict[str, object]:
        run_id = state["run_id"]
        persist_step = await self._nodes.start_step(run_id, "persist")
        await self._finalizer.finalize_plan(
            run_id=run_id,
            user_id=state["user_id"],
            candidate=state["candidate_plan"],
            companion=state["companion"],
            persist_step_id=persist_step.id,
            fallback_reason=state.get("fallback_reason"),
            simulate_failure="[mock:persist-failure]" in state["request"].message,
        )
        return {}

    @staticmethod
    def _after_risk(state: PlanningState) -> str:
        return "high" if state["risk"].level == "high" else "safe"

    @staticmethod
    def _after_intent(state: PlanningState) -> str:
        intent = state["intent"]
        if intent.intent == RunIntent.UNSUPPORTED or intent.missing_slots:
            return "clarification"
        return "ready"

    @staticmethod
    def _after_validation(state: PlanningState) -> str:
        if state["validation_report"].passed or state.get("fallback_reason") is not None:
            return "passed"
        return "repair"

    async def _build_context(
        self, state: PlanningState
    ) -> NodeOutput[tuple[PlanningContext, list[EvidenceCatalogItem]]]:
        profile = state["profile"]
        intent = state["intent"]
        if profile is None or intent.effective_goal_type is None:
            raise StructuredOutputError("planning context requires a complete profile")
        source_plan: Plan | None = None
        source_review: Review | None = None
        recent_tasks: list[TaskContext] = []
        recent_reviews: list[ReviewContext] = []
        completed_facts: list[str] = []
        blockers: list[str] = []
        pinned_memories: list[MemoryContext] = []
        async with self._session_factory() as session:
            async with session_transaction(session):
                plans = PlanRepository(session)
                memory_rows = await EvidenceRepository(session).pinned_memories(
                    state["user_id"], limit=3
                )
                pinned_memories = [
                    MemoryContext(
                        memory_id=memory.id,
                        version=memory.version,
                        memory_type=memory.memory_type,
                        summary=memory.summary,
                    )
                    for memory in memory_rows
                ]
                if state["request"].source_plan_id is not None:
                    source_plan = await plans.get_for_user(
                        state["request"].source_plan_id,
                        state["user_id"],
                    )
                reviews = ReviewRepository(session)
                if state["request"].source_review_id is not None:
                    source_review = await reviews.get_for_user(
                        state["request"].source_review_id,
                        state["user_id"],
                    )
                    if (
                        source_review is None
                        or source_plan is None
                        or source_review.plan_id != source_plan.id
                    ):
                        raise StructuredOutputError(
                            "source Review and source Plan must belong to the Run user"
                        )
                task_rows = await plans.recent_tasks(state["user_id"], limit=30)
                recent_tasks = [
                    TaskContext(
                        task_id=task.id,
                        state=TaskStatus(task.state),
                        title=task.title,
                        deliverable=task.deliverable,
                        scheduled_date=task.scheduled_date,
                        abandoned_reason=task.abandoned_reason,
                        abandoned_reason_text=task.abandoned_reason_text,
                    )
                    for task in task_rows
                ]
                completed_facts = [
                    task.deliverable for task in task_rows if task.state == "completed"
                ][:20]
                blockers = [
                    task.abandoned_reason_text or task.deliverable
                    for task in task_rows
                    if task.state == "abandoned"
                ][:10]
                if source_plan is not None:
                    review_rows = await reviews.recent_for_plan(
                        state["user_id"],
                        source_plan.id,
                        limit=7,
                    )
                    recent_reviews = [self._review_context(item) for item in review_rows]
                if source_review is not None and source_review.blockers:
                    blockers.insert(0, source_review.blockers)
                    blockers = list(dict.fromkeys(blockers))[:10]
        plan_context = self._plan_context(source_plan) if source_plan else None
        review_context = self._review_context(source_review) if source_review else None
        planning_date = None
        if source_review is not None:
            planning_date = max(
                datetime.now(UTC).date(),
                source_review.review_date + timedelta(days=1),
            )
        context = build_planning_context(
            profile=profile,
            requested_horizon_weeks=intent.requested_horizon_weeks,
            source_plan_id=source_plan.id if source_plan else None,
            source_plan_version=source_plan.version if source_plan else None,
            source_plan=plan_context,
            source_review=review_context,
            recent_tasks=recent_tasks,
            recent_reviews=recent_reviews,
            completed_facts=completed_facts,
            blockers=blockers,
            planning_date=planning_date,
        )
        context = context.model_copy(update={"pinned_memories": pinned_memories})
        evidence_catalog = [
            EvidenceCatalogItem(
                kind="memory",
                id=memory.memory_id,
                title=memory.memory_type,
                content=memory.summary,
                reliability=0.9,
            )
            for memory in pinned_memories
        ]
        snapshot = RunInputSnapshot(
            profile=profile,
            planning_window=context.planning_window,
            source_plan_id=context.source_plan_id,
            source_plan_version=context.source_plan_version,
            source_plan=context.source_plan,
            source_review=context.source_review,
            recent_tasks=context.recent_tasks,
            recent_reviews=context.recent_reviews,
            completed_facts=context.completed_facts,
            blockers=context.blockers,
            pinned_memories=context.pinned_memories,
            recent_task_ids=[task.task_id for task in context.recent_tasks],
            recent_review_ids=[review.review_id for review in context.recent_reviews],
            memory_versions={
                str(memory.memory_id): memory.version for memory in context.pinned_memories
            },
            timezone=context.timezone,
            time_budget_minutes=context.time_budget_minutes,
        )
        async with self._session_factory() as session:
            async with session_transaction(session):
                await SnapshotService.write_input_once(session, state["run_id"], snapshot)
        return NodeOutput(
            (context, evidence_catalog),
            NodeTelemetry(
                trace_data={
                    "token_estimate": context.token_estimate,
                    "horizon_weeks": context.planning_window.horizon_weeks,
                }
            ),
        )

    @staticmethod
    def _plan_context(plan: Plan) -> PlanContext:
        return PlanContext(
            plan_id=plan.id,
            version=plan.version,
            status=PlanStatus(plan.status),
            plan_date=plan.plan_date,
            horizon_start=plan.horizon_start,
            horizon_end=plan.horizon_end,
            overall_direction=plan.overall_direction,
            weekly_focus=[PlanFocusContext.model_validate(item) for item in plan.weekly_focus_json],
        )

    @staticmethod
    def _review_context(review: Review) -> ReviewContext:
        return ReviewContext(
            review_id=review.id,
            review_date=review.review_date,
            blockers=review.blockers,
            adjustment_request=review.adjustment_request,
            free_text=review.free_text,
            replan_reason=review.replan_reason,
        )

    async def _generate_candidate(
        self,
        state: PlanningState,
        step_id: UUID,
    ) -> NodeOutput[tuple[PlanCandidate, list[EvidenceCatalogItem], int, int]]:
        context = state["planning_context"]
        mode = state["intent"].replan_mode
        evidence_catalog = list(state.get("evidence_catalog", []))
        tool_round = state.get("tool_round", 0)
        tool_call_count = state.get("tool_call_count", 0)
        total_usage: ProviderUsage | None = None
        prompt_version = state["runtime_config"].prompt_versions["career_planning"]
        for _turn in range(3):
            force_final = (
                tool_round >= state["runtime_config"].max_tool_rounds
                or tool_call_count >= state["runtime_config"].max_tool_calls
            )
            available_tools = self._tool_registry.available_specs(
                intent=state["intent"].intent,
                requires_fresh_information=state["intent"].requires_fresh_information,
            )
            if force_final:
                available_tools = []
            raw = await self._provider.generate_agent_turn(
                message=state["request"].message,
                context=context,
                replan_mode=mode,
                available_tools=available_tools,
                evidence_catalog=evidence_catalog,
                force_final=force_final,
            )
            usage = self._extract_usage(raw)
            self._budget.record_llm_call(usage.tokens_in, usage.tokens_out)
            total_usage = usage if total_usage is None else self._combine_usage(total_usage, usage)
            try:
                turn = AgentTurnResponse.model_validate(raw)
            except ValidationError:
                self._budget.claim_format_repair()
                repaired = await self._provider.repair_format(
                    raw_output=raw,
                    context=context,
                    replan_mode=mode,
                )
                repair_usage = self._extract_usage(repaired)
                self._budget.record_llm_call(
                    repair_usage.tokens_in,
                    repair_usage.tokens_out,
                )
                total_usage = self._combine_usage(total_usage, repair_usage)
                prompt_version = state["runtime_config"].prompt_versions["format_repair"]
                try:
                    response = ProviderPlanResponse.model_validate(repaired)
                except ValidationError:
                    state["fallback_reason"] = "format_repair_failed"
                    fallback = fallback_candidate(context, mode)
                    return NodeOutput(
                        (fallback, evidence_catalog, tool_round, tool_call_count),
                        self._telemetry(total_usage, prompt_version),
                    )
                return NodeOutput(
                    (response.candidate, evidence_catalog, tool_round, tool_call_count),
                    self._telemetry(total_usage, prompt_version),
                )
            if turn.final is not None:
                return NodeOutput(
                    (turn.final, evidence_catalog, tool_round, tool_call_count),
                    self._telemetry(total_usage, prompt_version),
                )
            if force_final:
                raise StructuredOutputError("Tool requested after Tool budget was exhausted")
            tool_round += 1
            for call in turn.tool_calls:
                if tool_call_count >= state["runtime_config"].max_tool_calls:
                    break
                tool_call_count += 1
                execution = await self._tool_registry.execute(
                    tool_name=call.name,
                    arguments=call.arguments,
                    context=ToolContext(
                        run_id=state["run_id"],
                        user_id=state["user_id"],
                        goal_type=context.profile.goal_type,
                        intent=state["intent"].intent,
                        requires_fresh_information=(
                            state["intent"].requires_fresh_information
                        ),
                        remaining_deadline_ms=int(self._budget.remaining_seconds() * 1000),
                    ),
                    step_id=step_id,
                    round_number=tool_round,
                )
                if execution.success:
                    for item in execution.result.evidence:
                        catalog_item = EvidenceCatalogItem.model_validate(
                            item.model_dump(mode="json")
                        )
                        if all(
                            existing.kind != catalog_item.kind or existing.id != catalog_item.id
                            for existing in evidence_catalog
                        ):
                            evidence_catalog.append(catalog_item)
        if total_usage is None:
            raise StructuredOutputError("Agent produced no turn")
        state["fallback_reason"] = "tool_round_exhausted"
        fallback = fallback_candidate(context, mode)
        return NodeOutput(
            (fallback, evidence_catalog, tool_round, tool_call_count),
            self._telemetry(total_usage, prompt_version),
        )

    async def _revise_or_fallback(
        self, state: PlanningState
    ) -> NodeOutput[tuple[PlanCandidate, str | None]]:
        context = state["planning_context"]
        validation = state["validation_report"]
        if not self._budget.claim_business_repair():
            fallback = fallback_candidate(context, state["intent"].replan_mode)
            return NodeOutput((fallback, "business_repair_exhausted"))
        raw = await self._provider.repair_business_rules(
            candidate=state["candidate_plan"],
            context=context,
            repair_instructions=validation.repair_instructions,
            message=state["request"].message,
            replan_mode=state["intent"].replan_mode,
        )
        usage = self._extract_usage(raw)
        self._budget.record_llm_call(usage.tokens_in, usage.tokens_out)
        try:
            response = ProviderPlanResponse.model_validate(raw)
        except ValidationError:
            fallback = fallback_candidate(context, state["intent"].replan_mode)
            return NodeOutput(
                (fallback, "business_repair_invalid"),
                self._telemetry(
                    usage,
                    state["runtime_config"].prompt_versions["business_repair"],
                ),
            )
        return NodeOutput(
            (response.candidate, None),
            self._telemetry(
                usage,
                state["runtime_config"].prompt_versions["business_repair"],
            ),
        )

    async def _update_run(self, run_id: UUID, **values: object) -> None:
        async with self._session_factory() as session:
            async with session_transaction(session):
                run = await session.scalar(
                    select(AgentRun).where(AgentRun.id == run_id).with_for_update()
                )
                if run is None:
                    raise RuntimeError("Run not found")
                for key, value in values.items():
                    setattr(run, key, value)
                await session.flush()

    @staticmethod
    async def _immediate[T](value: T, trace: dict[str, object]) -> NodeOutput[T]:
        return NodeOutput(value, NodeTelemetry(trace_data=trace))

    @staticmethod
    def _extract_usage(raw: object) -> ProviderUsage:
        if not isinstance(raw, dict):
            raise StructuredOutputError
        try:
            return ProviderUsage.model_validate(raw.get("usage"))
        except ValidationError as exc:
            raise StructuredOutputError from exc

    @staticmethod
    def _combine_usage(first: ProviderUsage, second: ProviderUsage) -> ProviderUsage:
        return ProviderUsage(
            model_id=second.model_id,
            provider=second.provider,
            request_id=second.request_id,
            raw_output_hash=second.raw_output_hash,
            tokens_in=first.tokens_in + second.tokens_in,
            tokens_out=first.tokens_out + second.tokens_out,
            latency_ms=first.latency_ms + second.latency_ms,
            cost_cny=first.cost_cny + second.cost_cny,
        )

    @staticmethod
    def _telemetry(usage: ProviderUsage, prompt_version: str) -> NodeTelemetry:
        trace_data: dict[str, object] = {
            "latency_ms": usage.latency_ms,
            "provider": usage.provider,
        }
        if usage.request_id is not None:
            trace_data["request_id"] = usage.request_id
        if usage.raw_output_hash is not None:
            trace_data["raw_output_hash"] = usage.raw_output_hash
        return NodeTelemetry(
            trace_data=trace_data,
            tokens_in=usage.tokens_in,
            tokens_out=usage.tokens_out,
            cost_cny=usage.cost_cny,
            model_id=usage.model_id,
            prompt_version=prompt_version,
        )


class GraphFactory:
    """Build the fixed Stage 4 graph with an explicit Tool registry."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        provider: PlanningProvider,
        tool_registry: ToolRegistry | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._provider = provider
        self._tool_registry = tool_registry or ToolRegistry()

    def build(
        self,
        *,
        node_runner: NodeRunner,
        finalizer: AgentRunFinalizer,
        budget: BudgetGuard,
    ) -> FixedPlanningGraph:
        return FixedPlanningGraph(
            session_factory=self._session_factory,
            provider=self._provider,
            node_runner=node_runner,
            finalizer=finalizer,
            budget=budget,
            tool_registry=self._tool_registry,
        )


async def load_profile(
    session_factory: async_sessionmaker[AsyncSession], user_id: UUID
) -> ProfileContext | None:
    async with session_factory() as session:
        async with session_transaction(session):
            profile = await session.get(UserProfile, user_id)
            if profile is None:
                return None
            return ProfileContext.model_validate(profile, from_attributes=True)
