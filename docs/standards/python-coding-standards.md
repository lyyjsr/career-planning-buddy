# Python / FastAPI 编码规范

状态：本轮实现。

English summary: Coding standards for the FastAPI monolith — layer-by-layer constraints, Pydantic rules, async patterns, import boundaries enforced by import-linter.

---

## 0. 总则

- Python 3.11+，类型注解强制（schemas/services 层 `mypy --strict`）。
- `ruff` + `black` 格式化；`ruff check` 与 `mypy` 进 CI 硬阻断。
- 命名：模块/函数/变量 `snake_case`；类 `PascalCase`；常量 `UPPER_SNAKE`。
- 所有公开函数、类、Pydantic 模型有 docstring。
- 禁止 `print` 调试进提交（用 `structlog` 结构化日志）。

---

## 1. 六层分层约束（机械可校验）

六层定义见 [architecture/tdd.md §3](../architecture/tdd.md)；约束由 `import-linter` 守护（`.importlinter.toml`）。

### 1.1 允许依赖方向

```
app.api (L6)        可依赖 schemas / services / core
app.services (L4)   可依赖 schemas / repositories / core
app.agent (L5)      可依赖 schemas / tools / harness / providers（Protocol）
app.tools (L5)      可依赖 schemas / providers（Protocol）/ services（接口）
app.repositories (L3) 可依赖 models / schemas / core
app.providers (横切)   可依赖 schemas / core；禁止依赖 api/services/agent
app.models (L3 内部)   纯 SQLAlchemy，不依赖上层
app.schemas (L1)     最底层，不依赖其他业务层
app.core (L2)        配置层，不依赖业务
```

### 1.2 禁止（违反 = import-linter 失败）

| 禁止 | 规则 ID |
|---|---|
| `app.api` 依赖 `app.repositories` 或 `app.models` | R-Layer1 |
| `app.agent` 依赖 `app.models`（ORM 越层） | R-Layer1 |
| `app.providers` 依赖 `app.api`/`app.services`/`app.agent` | R-Layer3 |
| Tool 在执行函数里创建 DB 连接 | R-Layer2 |
| `app.schemas` 依赖任何业务层 | R-Layer3 |

### 1.3 `.importlinter.toml` 关键契约

```toml
[importlinter:contract:six-layers]
name = 六层依赖
type = layers
layers =
    app.api
    app.services
    app.agent
    app.tools
    app.repositories
    app.schemas
    app.core

[importlinter:contract:providers-isolation]
name = Providers 不向上暴露厂商对象
type = forbidden
source_modules = app.providers
forbidden_modules = app.api, app.services, app.agent
```

---

## 2. 代码风格

- `ruff` 配置（pyproject.toml）：

```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "ASYNC", "RUF"]
```

- `black` 行宽 100。
- 导入顺序：标准库 → 第三方 → 本项目（ruff isort 自动整理）。
- 禁止 `from x import *`。

---

## 3. Pydantic Schema 规则（L1）

- 所有对外 Schema 继承 `BaseModel`，显式 `model_config = ConfigDict(extra="forbid")`；确需放行时显式 `extra="allow"`。
- 必填字段用 `Field(...)`；可选用 `Field(default=None)` 或 `Field(default=...)`。
- 字段加约束：`Field(..., max_length=2000)`、`Field(..., ge=0, le=1)`。
- 枚举用 `enum.StrEnum`（Python 3.11+）。
- LLM Structured Output 必须有对应 Pydantic 模型，并复用 `model_json_schema()` 生成给模型的 schema。

示例：

```python
from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field

class IntentType(StrEnum):
    CREATE_PLAN = "create_plan"
    REPLAN = "replan"
    QUERY_PLAN = "query_plan"
    HIGH_RISK = "high_risk"

class IntentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent: IntentType
    confidence: float = Field(..., ge=0.0, le=1.0)
    missing_slots: list[str] = Field(default_factory=list, max_length=3)
    needs_clarification: bool
```

---

## 4. 配置层（L2）

- 用 `pydantic-settings` 的 `BaseSettings`，从环境变量 / `.env` 加载。
- 配置分环境：`Settings`（基类）→ `LocalSettings` / `ProdSettings`。
- 禁止把业务规则写进配置；配置只承载数值（超时、预算、URL、Flag）。

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str
    llm_api_key: str
    plan_run_budget_cny: float = 0.2
```

---

## 5. Repository 层（L3）

- Repository 接口用 `Protocol`，实现注入。
- 查询走 SQLAlchemy 2.x async，禁止字符串拼 SQL（防注入）。
- 事务粒度：单次 plan_run 一个事务；Service 控制 `async with session.begin():`。
- Repository 只读 / 写自己所属逻辑模块的表。
- Alembic 迁移：已发布的迁移**不可修改**，只能新增。

```python
from typing import Protocol
from sqlalchemy.ext.asyncio import AsyncSession

class AgentRunRepository(Protocol):
    async def save(self, run: AgentRun, session: AsyncSession) -> AgentRun: ...
    async def get(self, run_id: str, session: AsyncSession) -> AgentRun | None: ...
```

---

## 6. Service 层（L4）

- 编排用例、状态机、事务边界。
- 不依赖 LangGraph、不依赖厂商 SDK、不拼 HTTP。
- 命令方法走 Service + Repository 事务；查询方法可轻量但不改状态。
- 状态转移必须通过显式校验函数（不允许非法迁移）。

```python
class AgentRunService:
    def __init__(self, repo: AgentRunRepository, graph: PlanningGraph): ...

    async def start_run(self, request: StartRunRequest) -> AgentRun:
        # 校验 → 持久化初始态 → 触发 graph → 返回 run_id
        ...
```

---

## 7. Agent / Runtime 层（L5）

- LangGraph 工作流定义在 `app/agent/graph.py`；节点在 `app/agent/nodes/<name>.py`。
- 每个节点的 spec 落 `docs/model-design/agent-nodes/<node>.spec.md`。
- Agent（CareerPlanningAgent）只能调注册的只读 Tool。
- 工具调用走 harness（超时/限流/Trace），结果包 `<evidence>` 标签防注入。
- 停止条件：信息足够 / 达到预算 / 不可恢复错误 / 高风险 / 需澄清。
- Prompt 在 `app/prompts/{goal_type}/<purpose>_v<n>.py`，改 Prompt 必须新增版本号。

---

## 8. API 层（L6）

- 路由在 `app/api/routers/<resource>.py`，用 `APIRouter`。
- Router 只做 HTTP、Pydantic 校验、状态码、错误映射。
- 不写业务规则，不直接调 Repository。
- SSE 推送：`StreamingResponse` + async generator。
- 错误响应统一格式（HTTP 状态码 + 业务 code）：
  - 业务码不独占 HTTP 状态码语义；前端读 body.code 区分。

```python
@router.post("/agent-runs", status_code=202)
async def start_run(
    req: StartRunRequest,
    svc: AgentRunService = Depends(get_agent_run_service),
) -> StartRunResponse:
    run = await svc.start_run(req)
    return StartRunResponse(run_id=run.id)
```

---

## 9. 异步与并发

- 全程 async：`async def`、`asyncpg`、`httpx.AsyncClient`。
- 工具并发：`asyncio.gather`（RAG + Search 同时跑）。
- 限流：每用户每分钟 plan_run ≤ 5 次（FastAPI middleware + DB 计数）。
- Agent 限流：单轮 ≤4 次、总计 ≤8 次工具调用；每工具超时 10s。
- Trace 写入 fire-and-forget，不阻塞主请求。

---

## 10. 日志与可观测

- 用 `structlog`，JSON 输出，含 `trace_id`/`run_id`/`user_id`。
- 禁止输出：API Key、完整 prompt、用户敏感原文、密码。
- 敏感字段 hash 后再记录。
- Trace 字段随 run 保存（prompt_version / model / tool_calls / token / cost）。

---

## 11. 禁止清单

| ❌ 禁止 | 理由 |
|---|---|
| `print()` 进提交 | 用 structlog |
| 字符串拼 SQL | 注入风险 |
| 把节点命名 `<X>Agent` | R-Agent2 |
| Agent 直接写业务表 | R-IO2 |
| 改 Prompt 不加版本号 | R-Prompt2 |
| 静默吞错（`except: pass`） | R-Fail1 |
| Router 直接调 Repository | R-Layer1 |
| Provider 暴露厂商对象给上层 | R-Layer3 |
| MVP 阶段引入 Redis/Celery/K8s | ADR-001 演进触发才引入 |

---

## 12. 参考实现顺序（纵切）

1. `schemas/agent_run.py` — Pydantic 模型
2. `models/agent_run.py` — SQLAlchemy ORM
3. `repositories/agent_run_repository.py` — Repository
4. `services/agent_run_service.py` — 用例 + 状态机
5. `agent/graph.py` + `agent/nodes/*.py` — LangGraph
6. `api/routers/agent_runs.py` — FastAPI Router
7. `tests/<同包>/` — 测试跟代码走
