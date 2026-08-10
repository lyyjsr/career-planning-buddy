# Current System Overview

> Canonical current-state document as of 2026-08-09. Historical stage, PR and handoff
> documents explain how the system was built; this document and the repository code define
> what exists now.

## Product boundary

Career Planning Buddy is a single-user-facing, controlled-workflow career Agent and a
developer-facing evaluation workbench. The product route is:

```text
Guest Login → Onboarding/Profile → Plan → Today Tasks → Task feedback
→ Review → Replan → Memory review → Plan history/evidence
```

The frontend exposes `/today`, `/journey`, plan detail, `/reviews`, `/memories`, `/me`
and profile settings. A persisted `dev` role additionally reveals `/dev/runs` and
`/dev/evals`; hiding those links is UX only, while FastAPI authorization enforces the role.

## Runtime and persistence

FastAPI routers translate HTTP only. Services own use cases and state transitions;
repositories own SQLAlchemy persistence. A fixed LangGraph workflow performs risk gating,
intent routing, context construction, one tool-calling planning Agent, deterministic rule
validation, at most one controlled repair, fallback and terminal-aware persistence.

Each Agent Run persists input/config/output snapshots, steps, tool calls and events.
Events are committed before SSE delivery, snapshots are redacted/hash-oriented, and a Run
has exactly one terminal event which is last. Cancellation, deadline and budget are explicit
runtime states. Plans are versioned, so replanning archives rather than overwrites history.

PostgreSQL 16 with pgvector is the system of record. Alembic owns schema changes. Agent Run
dispatch is database-backed: workers claim pending rows with `SKIP LOCKED`, renew a lease by
heartbeat, and requeue expired leases up to a bounded attempt count. The local task registry
is only an execution handle. Row-locked recovery rechecks lease expiry, while worker id and
attempt count fence stale writers from node and terminal persistence. Retries are at-least-once and restart the controlled graph; they
reuse persisted Tool results but may repeat an LLM call. Eval executors remain process-local,
so the complete application is not yet horizontally scalable without deployment constraints.

## Three-layer memory

```text
L1 Working Memory
  current request/profile/plan/recent activity
  → deterministic history compression
  → PlanningContext + RunInputSnapshot

L2 Personal Episodic Memory
  Review → MemoryCandidate → user confirm/reject → Memory
  → embedding + user-isolated pgvector selection
  → later PlanningContext / evidence_refs / last_used_at

L3 Semantic Knowledge Memory
  Baidu Search → SearchSource → ExperienceAtomCandidate
  → developer approve/reject → ExperienceAtom
  → BGE embedding + pgvector → rag_retrieve / evidence_refs
```

L1 is Run-local. L2 is private to one user and consent-gated; unconfirmed or inactive
memories are excluded from prompt construction. L3 is global reviewed knowledge derived
from traceable search sources. L2 is never promoted into L3, and a search result is never
automatically treated as verified truth.

## Providers, Search and RAG

LLM, embedding and search access use protocols. Deterministic Mock providers are the safe
test/CI defaults. Real opt-ins are an OpenAI-compatible LLM, a pre-downloaded local BGE
embedding model and Baidu AI Search. Invalid real configuration or provider failure is
reported; it does not silently switch to Mock.

`web_search` is available only for create/replan requests classified as needing fresh
information. Results are normalized and URL-deduplicated into `search_sources`, then added
to the Run evidence catalog. Known-domain source classification uses normalized exact or
dot-separated subdomain matching and is only a reliability prior. `rag_retrieve` reads
approved active ExperienceAtoms; `memory_lookup` reads the current user's active L2 memory.

## Eval Harness V2

```text
Dataset/Case → Experiment → Trial → Agent Run → Evidence Projection
→ deterministic Grade → Report
```

New Experiments freeze one canonical runtime identity: Git commit, graph/stage, prompt,
model, tool contract, context, memory, search and Eval harness versions. Explicit
`APP_GIT_COMMIT` wins; local Git resolution is best-effort and records `unknown` on failure.
Historical snapshots and Experiments remain readable and are not rewritten.

Provider modes are Mock, frozen fixture replay/record and live. ProviderCall audit records
logical and physical attempts, latency, token/error metadata and hashes without credentials
or raw hidden reasoning. Live Eval alone applies bounded transient retry, exponential
backoff/jitter, `Retry-After`, pacing and concurrency control. Deadline and cancellation
interrupt waiting; authentication, schema and business-contract errors are not retried.
Reports distinguish model, transient provider, retry-exhausted, cancelled, configuration
and internal failures.

Pairwise compares baseline and candidate variants with position balancing and supports
human calibration. Until the configured genuine-human sample gate is met, its status is
`diagnostic_only`; no quality-superiority claim follows from the historical small live run.
The deterministic CLI smoke is part of CI and local check scripts.

## HTTP and frontend contracts

Pydantic strict schemas drive OpenAPI. A checked-in OpenAPI snapshot detects backend
contract drift. The frontend's shared API client adds the normal bearer token; developer
clients do not maintain a second JWT. Eval list/status projections include dataset,
baseline/variant and the full runtime identity required by `/dev/evals`.

The Eval browser console intentionally creates only small Mock/fixture runs. Paid live
evaluation remains an explicit CLI/API developer action. ExperienceAtom approval is a
developer-only CLI/use case rather than an automatic or guest-accessible promotion.

## Security and privacy boundaries

- Identity comes from JWT claims, never request `user_id`; dev endpoints also require the
  persisted dev role.
- There is no guest-accessible privilege-escalation endpoint, and SSE authorization is not
  placed in query strings.
- Provider keys are `SecretStr`, server-side only, absent from frontend variables, traces,
  snapshots and API errors.
- Search traces retain only necessary structured metadata/hashes; provider errors do not
  fabricate Mock evidence.
- L2 retrieval is user-isolated and consent-gated. L3 candidates require real Run sources
  and explicit developer review.

## Current known limits

- Agent Run supports PostgreSQL lease takeover and stale-attempt fencing, but has no node-level durable checkpoint and
  therefore does not claim exactly-once LLM execution.
- Eval and Pairwise executors remain process-local; multi-replica Eval is not supported.
- No Redis, Celery, Kubernetes, microservices, MCP or multi-agent framework.
- No arbitrary webpage crawler, hybrid BM25/vector RAG, reranker or online drift platform.
- Local BGE deployment has host/model-path cost and is not packaged as GPU Compose.
- Pairwise remains diagnostic without sufficient genuine human calibration.
- The historical real-provider run is a small reliability sample, not statistical proof of
  Agent quality; live E2E also depends on external credentials, network, quota and a local
  embedding model.

These are deliberate v1 scope limits. They do not alter deterministic offline correctness,
but they must be addressed before claiming large-scale production readiness.
