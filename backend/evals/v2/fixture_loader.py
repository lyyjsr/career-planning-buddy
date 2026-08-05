"""Per-Trial fixture seeding for the V2 TrialRunner.

Revision #1 forbids "run a create Trial first to feed replan". Instead the
FixtureLoader seeds the source Plan / Tasks / Review directly as ORM rows
inside the Trial's own transaction. It also seeds isolated Memory fixtures for
the ``memory_lookup`` / ``rag_retrieve`` smoke cases so Evidence ownership can
be asserted per user.

The seeded source Plan relies on a stub terminal ``AgentRun`` (``completed`` /
``result_kind='plan'``) so the ``Plan.source_run_id`` foreign key and the
``uq_plans_one_active_per_user`` partial index both resolve. The stub Run is
already terminal, so it never collides with the ``pending``/``running`` active
Run uniqueness constraint, and the real replan Run's ``finalize_plan`` will
archive the seeded active Plan exactly as in production.
"""

from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.harness.events import EventRecorder
from app.harness.snapshots import SnapshotService
from app.models.agent_run import AgentRun
from app.models.plan import Plan
from app.models.review import Review
from app.repositories.plans import PlanRepository
from app.repositories.reviews import ReviewRepository
from app.services.auth import AuthService
from app.services.profiles import ProfileService
from evals.v2.contracts import EvalScenario
from evals.v2.profile_mapping import scenario_to_profile_payload

PLANNING_DATE = date(2026, 8, 1)
PLAN_HORIZON_START = date(2026, 8, 1)
PLAN_HORIZON_END = date(2026, 8, 29)


class FixtureLoader:
    """Seeds an isolated user and scenario-specific fixture rows."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    async def prepare_user(self, scenario: EvalScenario) -> UUID:
        """Create an isolated guest user and seed the V2 profile when present."""

        from app.core.security import TokenService

        auth = AuthService(self._session, TokenService(self._settings))
        login = await auth.login_guest(None)
        user_id = login.user.id
        if scenario.profile is not None:
            await ProfileService(self._session).put(
                user_id=user_id,
                payload=scenario_to_profile_payload(scenario),
                idempotency_key=f"eval-profile-{user_id}",
            )
        await self._seed_memory_if_requested(scenario, user_id)
        return user_id

    async def seed_source_plan_for_continue(self, user_id: UUID) -> Plan:
        """Seed an ``active`` source Plan + Tasks for ``replan`` with continue."""

        result = await self._seed_plan(user_id, review=None)
        assert isinstance(result, Plan)
        return result

    async def seed_source_plan_for_adjust(
        self, user_id: UUID, *, adjustment_request: str, blockers: str
    ) -> tuple[Plan, Review]:
        """Seed an ``active`` Plan + a Review carrying the adjustment request."""

        review = _ReviewSeed(
            adjustment_request=adjustment_request,
            blockers=blockers,
        )
        result = await self._seed_plan(user_id, review=review)
        assert isinstance(result, tuple)
        return result

    async def _seed_plan(
        self, user_id: UUID, review: "_ReviewSeed | None"
    ) -> tuple[Plan, Review] | Plan:
        plans = PlanRepository(self._session)
        config = SnapshotService.build_config(self._settings)
        # Stub terminal Run: already in a degraded terminal state. It satisfies
        # ``Plan.source_run_id`` (unique, NOT NULL) without polluting the active
        # Run uniqueness index (which only covers pending/running). Note:
        # ``status='completed'`` would force ``final_plan_id IS NOT NULL`` via
        # ``ck_agent_runs_completed_result``, but the Plan that should reference
        # this Run is seeded next, so we use ``degraded`` (terminal, no Plan
        # dependency) and supply the required fallback_reason.
        stub_run_id = uuid4()
        run_values: dict[str, object] = {
            "id": stub_run_id,
            "user_id": user_id,
            "idempotency_key": f"eval-fixture-run-{stub_run_id}",
            "request_text": "[fixture] seeded source plan",
            "hint_intent": "create_plan",
            "resolved_intent": "create_plan",
            "status": "degraded",
            "result_kind": "clarification",
            "fallback_reason": "FIXTURE_STUB",
            "graph_version": config.graph_version,
            "config_snapshot_json": config.model_dump(mode="json"),
            "deadline_at": datetime.now(UTC) - timedelta(minutes=1),
            "model_id": "mock-career-planner-v1",
            "finished_at": datetime.now(UTC),
        }
        self._session.add(AgentRun(**run_values))
        await self._session.flush()
        plan_values: dict[str, object] = {
            "user_id": user_id,
            "source_run_id": stub_run_id,
            "status": "active",
            "plan_date": PLANNING_DATE,
            "horizon_start": PLAN_HORIZON_START,
            "horizon_end": PLAN_HORIZON_END,
            "overall_direction": "fixture-seeded direction for replan",
            # PlanContext.weekly_focus requires >= 1 entry; provide one so the
            # context_builder node can build a PlanContext from this seed.
            "weekly_focus_json": [
                {
                    "week_index": 1,
                    "focus": "fixture focus for seeded source plan",
                    "success_signal": "fixture success signal",
                }
            ],
            "summary": "fixture seeded source plan",
            "rationale": "seeded by FixtureLoader to back a replan Trial",
            "evidence_refs_json": [],
            "metadata_json": {"seed": True},
        }
        plan = await plans.create_plan(plan_values)
        candidates = [
            {
                "title": "fixture learning task",
                "task_type": "learning",
                "scheduled_date": PLANNING_DATE,
                "state": "completed",
                "starter_action": "Review fixture notes",
                "deliverable": "fixture notes reviewed",
                "estimated_minutes": 30,
                "actual_minutes": 25,
            },
            {
                "title": "fixture project task",
                "task_type": "project",
                "scheduled_date": PLANNING_DATE + timedelta(days=1),
                "state": "pending",
                "starter_action": "Open fixture repo",
                "deliverable": "fixture commit opened",
                "estimated_minutes": 45,
            },
        ]
        await plans.create_tasks(
            plan_id=plan.id, user_id=user_id, candidates=candidates
        )
        await EventRecorder(self._session).record(
            stub_run_id,
            "run.degraded",
            {"status": "degraded", "result_kind": "clarification"},
            allow_terminal_run=True,
        )
        if review is None:
            return plan
        review_row = await ReviewRepository(self._session).create(
            {
                "user_id": user_id,
                "plan_id": plan.id,
                "review_date": PLANNING_DATE,
                "mood": 4,
                "blockers": review.blockers,
                "adjustment_request": review.adjustment_request,
                "free_text": None,
                "completed_count": 1,
                "abandoned_count": 0,
                "suggested_replan": True,
                "replan_reason": "fixture adjustment",
                "idempotency_key": f"eval-fixture-review-{plan.id}",
                "next_plan_run_id": None,
            }
        )
        return plan, review_row

    async def _seed_memory_if_requested(self, scenario: EvalScenario, user_id: UUID) -> None:
        # PR-3 deliberately does NOT seed memories for tool-memory cases:
        # the Mock's ``[mock:tool-memory]`` branch only emits ``tool_calls``
        # when ``evidence_catalog`` is empty on the first turn, and
        # ``context_builder`` turns any active Memory into catalog evidence.
        # So seeding here would short-circuit Tool invocation entirely. The
        # Tool smoke assertions cover persistence of the call itself; PR-8
        # will seed contradicted / cross-user fixtures for ablation testing.
        del scenario, user_id


class _ReviewSeed:
    __slots__ = ("adjustment_request", "blockers")

    def __init__(self, *, adjustment_request: str, blockers: str) -> None:
        self.adjustment_request = adjustment_request
        self.blockers = blockers
