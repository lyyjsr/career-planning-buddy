"""Versioned Eval Case execution control-plane models."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EvalExperiment(Base):
    """Immutable version combination evaluated against one versioned dataset."""

    __tablename__ = "eval_experiments"
    __table_args__ = (
        CheckConstraint(
            "execution_mode IN ('mock_provider','fixture_provider','live_provider')",
            name="ck_eval_experiments_execution_mode",
        ),
        CheckConstraint(
            "variant_role IN ('baseline','candidate')",
            name="ck_eval_experiments_variant_role",
        ),
        CheckConstraint(
            "status IN ('draft','running','completed','failed','cancelled')",
            name="ck_eval_experiments_status",
        ),
        CheckConstraint("trial_count > 0", name="ck_eval_experiments_trial_count"),
        CheckConstraint(
            "baseline_experiment_id IS NULL OR baseline_experiment_id <> id",
            name="ck_eval_experiments_not_self_baseline",
        ),
        CheckConstraint(
            "(variant_role = 'baseline' AND baseline_experiment_id IS NULL) OR "
            "(variant_role = 'candidate' AND baseline_experiment_id IS NOT NULL)",
            name="ck_eval_experiments_baseline_role",
        ),
        CheckConstraint(
            "dataset_id <> '' AND dataset_version <> '' AND graph_version <> '' "
            "AND prompt_version <> '' AND model_version <> '' AND tool_version <> '' "
            "AND context_version <> '' AND memory_version <> ''",
            name="ck_eval_experiments_versions_present",
        ),
        CheckConstraint(
            "dataset_hash ~ '^[0-9a-f]{64}$' AND frozen_config_hash ~ '^[0-9a-f]{64}$'",
            name="ck_eval_experiments_hashes",
        ),
        Index("ix_eval_experiments_dataset_created", "dataset_id", "dataset_version", "created_at"),
        Index("ix_eval_experiments_status_created", "status", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    dataset_id: Mapped[str] = mapped_column(String(64), nullable=False)
    dataset_version: Mapped[str] = mapped_column(String(128), nullable=False)
    dataset_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    git_commit: Mapped[str] = mapped_column(String(64), nullable=False)
    graph_version: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(128), nullable=False)
    model_version: Mapped[str] = mapped_column(String(128), nullable=False)
    tool_version: Mapped[str] = mapped_column(String(128), nullable=False)
    context_version: Mapped[str] = mapped_column(String(128), nullable=False)
    memory_version: Mapped[str] = mapped_column(String(128), nullable=False)
    frozen_config_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    execution_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    variant_role: Mapped[str] = mapped_column(String(16), nullable=False)
    baseline_experiment_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("eval_experiments.id", ondelete="RESTRICT"),
    )
    trial_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="draft")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EvalTrial(Base):
    """One isolated execution attempt for an Experiment Case."""

    __tablename__ = "eval_trials"
    __table_args__ = (
        # PR-8: enforce uniqueness for NULL-variant (legacy) and non-NULL
        # variant (paired counterfactual) Trials via PostgreSQL partial
        # unique indexes. UniqueConstraint does not accept postgresql_where,
        # so we model both as partial indexes; the legacy
        # ``uq_eval_trials_case_index`` name is preserved on the NULL arm.
        Index(
            "uq_eval_trials_case_index",
            "experiment_id",
            "case_id",
            "trial_index",
            unique=True,
            postgresql_where=text("variant IS NULL"),
        ),
        Index(
            "uq_eval_trials_case_index_variant",
            "experiment_id",
            "case_id",
            "variant",
            "trial_index",
            unique=True,
            postgresql_where=text("variant IS NOT NULL"),
        ),
        CheckConstraint("trial_index >= 0", name="ck_eval_trials_trial_index"),
        CheckConstraint("seed >= 0", name="ck_eval_trials_seed"),
        CheckConstraint(
            "run_type IN ('evaluation','fixture_replay','live_rerun','candidate_backtest')",
            name="ck_eval_trials_run_type",
        ),
        CheckConstraint(
            "status IN ('pending','running','completed','failed','timed_out','cancelled')",
            name="ck_eval_trials_status",
        ),
        CheckConstraint("tokens_in >= 0 AND tokens_out >= 0", name="ck_eval_trials_tokens"),
        CheckConstraint("latency_ms >= 0", name="ck_eval_trials_latency"),
        CheckConstraint("cost_amount >= 0", name="ck_eval_trials_cost"),
        CheckConstraint(
            "case_fixture_hash ~ '^[0-9a-f]{64}$'", name="ck_eval_trials_fixture_hash"
        ),
        CheckConstraint(
            "status <> 'completed' OR (run_id IS NOT NULL AND outcome_snapshot_json IS NOT NULL "
            "AND transcript_hash ~ '^[0-9a-f]{64}$')",
            name="ck_eval_trials_completed_outcome",
        ),
        Index("ix_eval_trials_experiment_status", "experiment_id", "status"),
        Index("ix_eval_trials_run_id", "run_id"),
        Index(
            "ix_eval_trials_group",
            "counterfactual_group_id",
            postgresql_where=text("counterfactual_group_id IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    experiment_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("eval_experiments.id", ondelete="CASCADE"),
        nullable=False,
    )
    case_id: Mapped[str] = mapped_column(String(128), nullable=False)
    case_fixture_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    trial_index: Mapped[int] = mapped_column(Integer, nullable=False)
    seed: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # PR-8: counterfactual pairing. ``variant`` identifies which ablation
    # arm the Trial represents within its group; ``counterfactual_group_id``
    # ties two or more variants together for paired-diff reporting. Both
    # are NULL for pre-PR-8 single-arm Trials, which preserves the legacy
    # uniqueness contract (uq_eval_trials_case_index).
    variant: Mapped[str | None] = mapped_column(String(64))
    counterfactual_group_id: Mapped[str | None] = mapped_column(String(64))
    run_type: Mapped[str] = mapped_column(String(32), nullable=False, server_default="evaluation")
    run_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("agent_runs.id", ondelete="RESTRICT")
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="pending")
    outcome_snapshot_json: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    transcript_hash: Mapped[str | None] = mapped_column(String(64))
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    cost_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 6), nullable=False, server_default="0"
    )
    cost_currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="CNY")
    pricing_version: Mapped[str | None] = mapped_column(String(64))
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EvalScore(Base):
    """Typed, evidence-bearing Grade result for one completed Trial."""

    __tablename__ = "eval_scores"
    __table_args__ = (
        UniqueConstraint(
            "trial_id", "grader_name", "grader_version", name="uq_eval_scores_grader_version"
        ),
        CheckConstraint(
            "domain IN ('task','behavioral','tool','model','system','safety')",
            name="ck_eval_scores_domain",
        ),
        CheckConstraint(
            "metric_type IN ('boolean','numeric','categorical')",
            name="ck_eval_scores_metric_type",
        ),
        CheckConstraint(
            "(metric_type = 'boolean' AND passed IS NOT NULL AND score IS NULL "
            "AND categorical_value IS NULL) OR "
            "(metric_type = 'numeric' AND score IS NOT NULL AND categorical_value IS NULL) OR "
            "(metric_type = 'categorical' AND score IS NULL AND categorical_value IS NOT NULL)",
            name="ck_eval_scores_typed_value",
        ),
        CheckConstraint("NOT hard_gate OR passed IS NOT NULL", name="ck_eval_scores_hard_gate"),
        CheckConstraint(
            "metric_type = 'numeric' OR threshold IS NULL",
            name="ck_eval_scores_threshold",
        ),
        Index("ix_eval_scores_trial_domain", "trial_id", "domain"),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    trial_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("eval_trials.id", ondelete="CASCADE"),
        nullable=False,
    )
    grader_name: Mapped[str] = mapped_column(String(128), nullable=False)
    grader_version: Mapped[str] = mapped_column(String(128), nullable=False)
    domain: Mapped[str] = mapped_column(String(16), nullable=False)
    metric_type: Mapped[str] = mapped_column(String(16), nullable=False)
    score: Mapped[float | None] = mapped_column(Float)
    passed: Mapped[bool | None] = mapped_column(Boolean)
    categorical_value: Mapped[str | None] = mapped_column(String(128))
    hard_gate: Mapped[bool] = mapped_column(Boolean, nullable=False)
    threshold: Mapped[float | None] = mapped_column(Float)
    evidence_item_ids: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    evidence_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class EvalEvidenceItem(Base):
    """One piece of frozen evidence fed to a V2 Grader.

    The (trial_id, kind, source_type, source_id) tuple is unique: if the
    underlying projection changed, the new content_hash must NOT silently
    overwrite the old row -- the collector inserts new rows whose ids differ
    from any prior Score's evidence_item_ids, forcing a re-grade.
    """

    __tablename__ = "eval_evidence_items"
    __table_args__ = (
        UniqueConstraint(
            "trial_id",
            "kind",
            "source_type",
            "source_id",
            name="uq_eval_evidence_items_trial_kind_source",
        ),
        CheckConstraint(
            "kind IN ('request_constraints','profile_projection',"
            "'expected_outcome','trajectory_policy','rubric',"
            "'plan_projection','task_projection','step_projection',"
            "'event_projection','tool_call_projection','tool_spec',"
            "'run_metrics','outcome_status','evidence_visible_refs',"
            "'transcript_hash','risk_signals','redacted_output',"
            "'cross_user_signal','tool_allowlist','repair_signal',"
            "'provider_call_projection','expected_citations_map')",
            name="ck_eval_evidence_items_kind",
        ),
        CheckConstraint(
            "sensitivity IN ('normal','sensitive')",
            name="ck_eval_evidence_items_sensitivity",
        ),
        CheckConstraint(
            "content_hash ~ '^[0-9a-f]{64}$'",
            name="ck_eval_evidence_items_content_hash",
        ),
        Index("ix_eval_evidence_items_trial_kind", "trial_id", "kind"),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    trial_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("eval_trials.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(128))
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    projection_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    sensitivity: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="normal"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
