# Career Planning Buddy

Career Planning Buddy is a single-user-facing career-planning Agent MVP. It turns a
profile and execution feedback into a versioned plan with startable daily tasks,
reviews, replanning, consent-based memory, and cited local RAG evidence.

The repository now implements Stages 0–5 and Stage 6A. Codex is used for engineering only; runtime
model access always goes through the project Provider protocols.

## Stack and boundaries

- Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 Async, Alembic
- PostgreSQL 16 with pgvector
- React, TypeScript strict, Vite, React Router, TanStack Query
- one controlled LangGraph runtime and one backend worker
- DeepSeek through the OpenAI-compatible Provider, or deterministic Mock
- local BGE embeddings (1024 dimensions), or deterministic Mock
- MockSearchProvider only; no real search API
- no Redis, Celery, MCP, multi-agent framework, microservices, or paid CI calls

## Quick start with Docker

```bash
cp .env.example .env
docker compose up --build -d
docker compose ps
curl http://localhost:8000/health
```

Open `http://localhost:5173`. Compose deliberately uses Mock LLM and Mock embeddings by
default so the complete stack starts without secrets or host model mounts. PostgreSQL
data is kept in the named `postgres_data` volume. The backend runs exactly one Uvicorn
worker, as required by the in-process Stage 5 executor.

Compose reads only the separately named `COMPOSE_LLM_*` variables. This prevents a
host-only real Provider credential from being copied into the default Mock container.

Apply migrations independently with:

```bash
cd backend
python -m alembic upgrade head
```

## Local development

Requirements: Python 3.12, Node.js 20, npm, and Docker.

```bash
docker compose up -d postgres
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.lock   # Windows
.venv/Scripts/python -m pip install --no-deps -e .
.venv/Scripts/python -m alembic upgrade head
.venv/Scripts/python -m uvicorn app.main:app --reload
```

On Linux/macOS, use `.venv/bin/python`. In another terminal:

```bash
cd frontend
npm ci
npm run dev
```

Copy `.env.example` to `.env`. Never commit `.env` or an API key. Browser-visible
`VITE_` variables must never contain secrets.

### Real DeepSeek and local BGE

Set these only in the ignored root `.env`:

```dotenv
LLM_PROVIDER=openai_compatible
LLM_API_KEY=
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL_PATH=
EMBEDDING_MODEL_NAME=BAAI/bge-large-zh-v1.5
EMBEDDING_DIM=1024
SEARCH_PROVIDER=mock
```

`EMBEDDING_MODEL_PATH` must point to an already downloaded local model. The application
does not auto-download weights. Missing or invalid real Provider configuration fails
explicitly; it never silently falls back to Mock.

## Product and developer flows

The API flow is:

1. `POST /api/v1/auth/guest`
2. `PUT /api/v1/profile`
3. `POST /api/v1/agent-runs`, then consume persisted SSE events
4. query the generated Plan and update Task state
5. `POST /api/v1/reviews`
6. `POST /api/v1/reviews/{id}/start-next-plan`
7. review the deterministic Memory candidates, then confirm or reject them
8. let later planning runs retrieve confirmed active memories by semantic relevance

The developer console is at `http://localhost:5173/dev/runs`. It requires a JWT for a
local user whose persisted role is `dev`. It displays redacted snapshots and hashes,
steps, Tool calls, durable events, costs/latency, Replay lineage, and the exactly-one,
terminal-last invariant. `POST /api/v1/dev/runs/{id}/replay` defaults to fixture-only
Mock replay and never mutates the source Run or Plan.

## Eval, Replay, and Bad Cases

Run the frozen 30-case Stage 5 suite and the 12-case Stage 6A memory/context suite offline:

```bash
cd backend
python -m scripts.run_eval
```

The runner executes the real deterministic risk, routing, Mock structured-output,
format-repair, business-rule validation/repair, and fallback code paths. It reports 12
graders and writes reports to `backend/evals/artifacts/`; failed cases are written as
JSONL to `backend/evals/bad_cases/`. Generated artifacts are ignored by Git. Replay and
CI never call DeepSeek, external embeddings, or search.

Stage 6A additionally verifies pinned/semantic memory selection, candidate consent
boundaries, user isolation, embedding text fallback, and at least 40% deterministic
compression on the large-history fixture. Planning context is rendered in stable,
explicitly untrusted sections instead of one undifferentiated JSON block.

Latest verified Stage 5 baseline (2026-08-01): 30/30 cases passed; 21 completed and 9
contractually degraded (four clarification, three safety, two controlled fallbacks).
All 12 grader pass rates were 1.0. These numbers come from `python -m scripts.run_eval`,
not from hand-authored results.

Run the full HTTP + database + configured Provider demonstration while a backend is
running:

```bash
cd backend
python -m scripts.e2e_demo --base-url http://127.0.0.1:8000
```

The verified real run used `deepseek-v4-flash` and `BAAI/bge-large-zh-v1.5`: create
plan produced a Schema-valid degraded fallback in 25.329 seconds (7,503 input / 1,361
output tokens), replan completed in 9.811 seconds (7,274 input / 710 output tokens),
and local RAG returned the seeded atom with cosine similarity 1.0 at 1024 dimensions.

## Checks

PowerShell:

```powershell
.\scripts\check.ps1
```

Git Bash, WSL, Linux, or macOS:

```bash
bash scripts/check.sh
```

Both run Ruff, Mypy, Alembic upgrade, Pytest, both offline Eval datasets, frontend tests,
and the production frontend build. GitHub Actions uses Python 3.12, Node.js 20,
PostgreSQL+pgvector, locked dependencies, and Mock Providers only.

## Delivery notes

- API schema is available at `/docs` and `/openapi.json`.
- Health probe: `GET /health`.
- All timestamps and deadlines use UTC.
- Agent events are persisted before SSE delivery; each Run has exactly one terminal
  event and it is last.
- Plans remain versioned; replan archives history instead of overwriting it.
- Real Web Search remains intentionally out of scope; fixed Mock evidence is labeled.
