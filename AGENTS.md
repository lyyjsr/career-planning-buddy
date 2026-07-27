# AGENTS.md

| Version | v1.0 |
|---|---|
| Status | Active |
| Purpose | Entry point for AI agents (Cursor / Claude Code / Codex) working in this repository. Concise rules + reading paths; load exact docs for the task before changing code. |
| Precedence | Higher than any single conversation instruction. On conflict, this file wins. |

Chinese mirror: [AGENTS.zh-CN.md](./AGENTS.zh-CN.md). Full prose constitution (deeper commentary): [docs/governance/AGENTS.md](./docs/governance/AGENTS.md).

## Project Snapshot

`Dazi` is an **AI job-planning companion for computer-science students**: a single-core Agent (CareerPlanningAgent) + controlled workflow nodes + six-layer Harness + evidence-driven planning + execution-feedback loop. Stack: FastAPI monolith + React SPA + PostgreSQL 16 + pgvector + DeepSeek V4 + LangGraph.

This is **not**: a multi-agent system (only 1 real Agent), a Java business system, a chatbot, or a demo.

Current status and next step: root [README.md](./README.md) is authoritative; stage numbering is defined in [stage-delivery-definition.md](./docs/governance/stage-delivery-definition.md).

## Required Reading Paths

Load these docs before implementation or review:

| Development or review scenario | Required docs |
|---|---|
| What the project is | [product-overview.md](./docs/overview/product-overview.md) |
| Architecture decisions | [adr.md](./docs/architecture/adr.md) |
| Technical design & six-layer architecture | [tdd.md](./docs/architecture/tdd.md) |
| API & data contracts | [api-and-data-contracts.md](./docs/architecture/api-and-data-contracts.md) |
| Tech decision matrix (build now / defer / never) | [technology-decision-matrix.md](./docs/architecture/technology-decision-matrix.md) |
| Python / FastAPI coding standards | [python-coding-standards.md](./docs/standards/python-coding-standards.md) |
| How to write an Agent-node / API spec | [spec-writing-guide.md](./docs/standards/spec-writing-guide.md) |
| Layer dependency boundaries & import-linter | [tdd.md §3](./docs/architecture/tdd.md), [python-coding-standards.md §1](./docs/standards/python-coding-standards.md) |
| Provider protocols & external integrations | [adr.md §ADR-005](./docs/architecture/adr.md) |
| Database & state machines | [api-and-data-contracts.md](./docs/architecture/api-and-data-contracts.md) |
| Security, audit & compliance | [security-and-compliance.md](./docs/standards/security-and-compliance.md) |
| Testing & TDD | [testing-and-tdd.md](./docs/standards/testing-and-tdd.md) |
| Per-node design spec (construction-level, sync authoritative) | [docs/model-design/agent-nodes/](./docs/model-design/agent-nodes/README.md) (11 node specs, 7 elements each) |
| Per-table data model (construction-level) | [docs/model-design/data-models/](./docs/model-design/data-models/README.md) (10 tables + ER diagram) |
| Per-endpoint API spec (construction-level) | [docs/model-design/api-spec/](./docs/model-design/api-spec/README.md) (7 endpoints) |
| State machines (single source) | [docs/model-design/state-machines/](./docs/model-design/state-machines/README.md) (4 mermaid + transition matrices) |
| Prompt standards (Agent-specific) | [docs/standards/prompts/](./docs/standards/prompts/README.md) |
| Error handling & fallback | [docs/standards/error-handling-standard.md](./docs/standards/error-handling-standard.md) |
| Contract rules (Pydantic + OpenAPI) | [docs/standards/contract-standard.md](./docs/standards/contract-standard.md) |
| Spec-Driven workflow (clarify → plan → tasks) | [spec-driven-workflow.md](./docs/governance/spec-driven-workflow.md) |
| Dev workflow (vertical slice, module placement) | [development-workflow.md](./docs/governance/development-workflow.md) |
| New use-case Checklist | [use-case-development-checklist.md](./docs/governance/use-case-development-checklist.md) |
| Verification & review | [verification-and-review.md](./docs/governance/verification-and-review.md) |
| Gate scripts | [check-scripts-spec.md](./docs/governance/check-scripts-spec.md) |
| Stage gate & exit criteria | [stage-delivery-definition.md](./docs/governance/stage-delivery-definition.md) |
| Progressive AI loading strategy | [ai-reading-guide.md](./docs/governance/ai-reading-guide.md) |

For the full categorized index see [docs/README.md](./docs/README.md).

## Non-Negotiable Rules (keywords per BCP 14 / RFC 2119)

### Six-layer dependency boundaries
- **R-Layer1**: `import-linter` MUST enforce layer direction. `app.api` MUST NOT import `app.repositories` or `app.models`; `app.agent` MUST NOT import `app.models`. Enforced-by: `import-linter` → `scripts/check-architecture.sh`.
- **R-Layer2**: Tools MUST depend only on Protocol / Service interfaces; a tool executor MUST NOT open DB connections. Enforced-by: import-linter + manual review.
- **R-Layer3**: `schemas` and `models` MUST stay separate; API responses MUST NOT return ORM objects directly; `app.providers` MUST NOT leak vendor-specific response objects upward. Enforced-by: import-linter + `check-contracts.sh`.

### Contract first
- **R-Contract1**: OpenAPI / Pydantic schemas / state machines / Alembic migrations MUST be defined before implementing Router / Service / Prompt. Reverse-engineering contracts from pages or ORM is FORBIDDEN. Enforced-by: manual review.
- **R-Contract2**: Any breaking API change MUST explicitly update the OpenAPI snapshot. Enforced-by: `scripts/check-contracts.sh`.

### Single-Agent stance (critical)
- **R-Agent1**: There is exactly ONE real Agent — `CareerPlanningAgent`. `risk_gate` / `intent_router` / `rule_validator` / `quality_reviewer` / `distill_evidence` are NODES, not Agents. Enforced-by: manual review.
- **R-Agent2**: Node classes MUST NOT be named `<X>Agent`. Lesson: AIGOV antipattern P-05 — naming something an Agent without a Harness. Enforced-by: manual review.

### Single source of truth
- **R-Data1**: PostgreSQL is the ONLY authoritative business fact source. In-process caches MUST hold only rebuildable ephemeral data. Enforced-by: manual review.
- **R-Data2**: Redis / Celery / K8s MUST NOT be introduced in MVP unless an ADR-001 evolution trigger fires. Enforced-by: manual review.

### Read/write separation
- **R-IO1**: The Agent MAY only call read-only tools (`web_search` / `rag_retrieve` / `memory_lookup`). Enforced-by: manual review.
- **R-IO2**: Every write MUST go through the `persist` node + a Service transaction. The Agent MUST NOT write business tables directly. Enforced-by: manual review.

### Explicit failure
- **R-Fail1**: Silent error swallowing is FORBIDDEN. Downgrades MUST carry `fallback_reason`. Half-baked results MUST NOT be persisted. Enforced-by: manual review + tests.

### Prompts are files, not code
- **R-Prompt1**: Prompt templates MUST live in `prompts/{goal_type}/*.py`, with version numbers (`v1`, `v2`). Enforced-by: manual review.
- **R-Prompt2**: Editing a prompt MUST create a new version number, never edit the old one (for Replay diff). Enforced-by: manual review.

### Content safety
- **R-Safety1**: High-risk triage (keyword list + LLM classifier) → fixed script + 12356 hotline → END; MUST NOT enter long-term memory. Enforced-by: manual review.
- **R-Safety2**: LLM output MUST be reviewed before sending (keyword list + LLM classifier). Enforced-by: manual review.

### Spec-Driven pre-step
- **R-Plan1**: Before non-trivial code (>30 lines or >2 files), AI MUST first run Clarify; if any persistence condition holds (cross-module / state-machine change / new API / new table / new node / ≥3 business files or >50 lines / architectural), AI MUST persist `docs/requirements/<feature>/plan.md`, and §3 of that file MUST contain a mermaid interaction diagram. Enforced-by: `scripts/check-plan.sh` + manual review.
- **R-Plan2**: Bug fixes <30 lines + single module + no state-machine/schema/API impact MAY skip persistence, but MUST get a one-line verbal clarification first. Enforced-by: manual review.

## Code Style

- Python: `ruff` + `black` + `mypy --strict` (schemas & services). snake_case for funcs/vars, PascalCase for classes.
- TypeScript (frontend): `eslint` + `prettier`, camelCase.
- All public functions / classes / Pydantic models have docstrings.
- All Pydantic models declare `model_config = ConfigDict(extra="forbid")` or explicit `extra="allow"`.

## Forbidden Behaviors

| Forbidden | Why |
|---|---|
| Invent troubleshooting cases in prompts | Use the fixed eval dataset |
| Change schema without updating OpenAPI snapshot | Breaks contract tests |
| Implement a feature without tests | Tests travel with code |
| Silent error swallow | Failures must be explicit |
| Let the LLM write business tables directly | Agent is read-only |
| Name a node `<X>Agent` | Antipattern P-05 |
| Introduce Redis/Celery/K8s in MVP | Evolution trigger required |
| Introduce a Java backend | Evolution trigger required |
| Mix mock data into real stats | Mocks must carry `data_origin: "mock"` |

## Verification Commands (do not invent commands)

- Full gate: `bash scripts/check.sh`
- Python tests: `pytest`
- Architecture test: `import-linter --config backend/.importlinter.toml`
- Build/run/deploy commands not present in this file or `scripts/` MUST NOT be invented.

## Documentation Rules

- `docs/` is categorized under `overview/`, `architecture/`, `model-design/`, `requirements/`, `standards/`, `governance/`, `third-party-integration/`, `design-input/`. Files use semantic names. Each top-level folder has its own `README.md`. Full index: [docs/README.md](./docs/README.md).
- `design-input/` is raw archive, NOT a source of truth.
- Every formal doc MUST declare a status line (`定稿` / `本轮实现` / `规划中` / `已废弃`); `design-input/` and `third-party-integration/` are exempt.
