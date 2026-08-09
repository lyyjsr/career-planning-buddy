# Career Planning Buddy

Career Planning Buddy is a controlled-workflow career-planning Agent. It closes the loop from profile and planning through daily execution, review, replanning, three-layer memory, source-traceable online knowledge, and reproducible evaluation. It is a production-oriented portfolio / release-candidate system, not a claim of large-scale production validation.

Runtime model access always goes through Provider protocols. Codex is an engineering tool and is not the application runtime model. The MVP intentionally uses one backend worker because its Agent and Eval executors are in-process.

## Architecture

```text
React frontend
      ↓
FastAPI HTTP/SSE API
      ↓
Controlled LangGraph runtime
├─ L1 Working Memory: current Run and compressed planning context
├─ L2 Personal Episodic Memory: confirmed user-private execution memory
├─ L3 Semantic Knowledge Memory: reviewed, source-traceable career knowledge
├─ Tool Registry: memory_lookup / rag_retrieve / web_search
├─ OpenAI-compatible LLM or deterministic Mock
├─ Baidu Search or deterministic Mock Search
└─ PostgreSQL 16 + pgvector

Eval Harness V2
Case → Experiment → Trial → Run → Grade → Report
```

The backend is Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 Async and Alembic. The frontend is React, strict TypeScript, Vite, React Router and TanStack Query. The MVP has no Redis, Celery, MCP, multi-agent framework, microservices or object storage.

## Product flow and memory boundaries

The user flow is Guest Login → Profile → Plan → Today Tasks → Task feedback → Review → Replan → Memories → Plan history/evidence. Runs persist snapshots, steps, tool calls and SSE events before streaming; each Run has exactly one terminal event.

The three memory layers are deliberately different:

- L1 is the current Run working context: request, profile, plan, recent task/review history, deterministic compression, budgets and snapshots.
- L2 is user-private episodic memory: Review → MemoryCandidate → explicit confirm/reject → Memory → embedding/pgvector retrieval → later PlanningContext and evidence references. Unconfirmed or inactive items are excluded.
- L3 is shared semantic knowledge: Baidu Search → SearchSource → ExperienceAtomCandidate → developer review → ExperienceAtom → local BGE/pgvector → `rag_retrieve` and plan evidence. Search output is evidence, not automatically accepted truth, and L2 data never becomes global L3 data.

## Provider modes

Safe defaults use deterministic Mock LLM, embeddings and search. Real modes are explicit opt-ins:

- LLM: `openai_compatible`, including DeepSeek-compatible endpoints.
- Embedding: local BGE, with a pre-downloaded 1024-dimensional model directory.
- Search: `baidu`, using Baidu AI Search.
- Eval: `mock`, `fixture` or `live`; normal CI uses only free deterministic modes.

Missing or invalid real-provider configuration fails explicitly. Real-provider failures never silently fall back to Mock. Secrets must remain server-side and must never use browser-visible `VITE_` variables.

## Safe Mock mode with Docker

Requirements: Docker Desktop with Compose.

```powershell
Copy-Item .env.example .env
docker compose up --build -d
docker compose ps
Invoke-RestMethod http://127.0.0.1:8000/health
```

Open `http://localhost:5173`. Compose defaults to Mock providers, uses a named PostgreSQL volume, applies Alembic migrations, and starts exactly one Uvicorn worker.

Docker search has a real but explicit opt-in through `COMPOSE_SEARCH_PROVIDER` and the `COMPOSE_BAIDU_SEARCH_*` settings documented in `.env.example`. Host real-provider settings are not implicitly copied into the container. Local backend mode is recommended for a host-mounted BGE model; this release does not add GPU/CUDA container deployment.

## Local development and real providers

Requirements: Python 3.12, Node.js 20, npm and PostgreSQL 16 with pgvector. Start only the database if desired:

```powershell
docker compose up -d postgres
cd backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.lock
.\.venv\Scripts\python -m pip install --no-deps -e .
.\.venv\Scripts\python -m alembic upgrade head
.\.venv\Scripts\python -m uvicorn app.main:app --reload
```

In another terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Copy `.env.example` to the ignored root `.env` and select real providers there. Supply the LLM endpoint/model, a pre-downloaded local BGE path, and Baidu configuration only when using those modes. The application does not download model weights automatically. Never commit `.env` or credentials.

## Developer surfaces

After normal login, users whose persisted server-side role is `dev` see:

- `/dev/runs`: redacted snapshots and hashes, steps, tools, persisted events, cost/latency and terminal invariants.
- `/dev/evals`: a small Experiment list/create/status/progress/cancel/report console for Mock/fixture runs, including runtime identity, failure categories, token summary and calibration state.

Both pages reuse the normal access token. Backend `require_dev` authorization remains the security boundary; there is no HTTP privilege-escalation endpoint. Legacy replay is explicitly named `legacy_trace_clone` and is not presented as Graph re-execution.

## Eval Harness V2

V2 freezes Dataset, Git/Graph/Prompt/Model/Tool/Context/Memory/Search/Harness versions and executes the real Case → Experiment → Trial → Run → Grade → Report path. It supports fixture record/replay, per-physical-call Provider audit, token/error accounting, deterministic graders, baseline/agent variants, Pairwise Judge and human calibration.

Discover and run a deterministic one-case smoke:

```powershell
cd backend
.\.venv\Scripts\python -m evals.v2 --help
.\.venv\Scripts\python -m evals.v2 run --dataset runtime-smoke --cases runtime-tool-error-01 --provider-mode mock --trial-count 1
```

The legacy Stage 5/Stage 6 regression suite remains available:

```powershell
.\.venv\Scripts\python -m scripts.run_eval --no-persist
```

`live` Eval is an explicit developer/CLI operation. It applies bounded transient retry, exponential backoff with jitter, `Retry-After`, pacing, concurrency and deadline/cancellation limits; 401/403, schema and business-contract failures are not retried. Without enough completed paired trials and genuine human labels, Pairwise output remains `diagnostic_only`, not final quality truth. Historical small live samples do not prove the full Agent is better than the direct-LLM baseline.

## Verification

Canonical local verification:

```powershell
.\scripts\check.ps1
```

The check runs Ruff, Mypy, Alembic upgrade, Pytest, legacy deterministic Eval, an Eval V2 end-to-end smoke, frontend tests and the production frontend build. GitHub Actions uses Python 3.12, Node.js 20, PostgreSQL/pgvector, locked dependencies, `APP_GIT_COMMIT=${{ github.sha }}` and Mock providers only.

Useful endpoints:

- API docs: `http://127.0.0.1:8000/docs`
- OpenAPI: `http://127.0.0.1:8000/openapi.json`
- Health: `GET /health`

The current architecture and limits are maintained in `docs/architecture/current-system-overview.md`; release evidence is in `docs/review/v1-release-verification-2026-08-09.md`.
