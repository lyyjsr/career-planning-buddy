# Harness 工程结构实施总图

| 版本 | v1.0 |
|---|---|
| 日期 | 2026-07-24 |
| 状态 | 草稿 |
| 目的 | Stage 0-5 写代码时的施工蓝本：把 [harness-overview.md](./harness-overview.md) 的"24 模块概念映射"翻译为"具体文件、依赖、入口、生命周期" |

---

## 1. 一句话定位

> **`harness/` 与 `evals/` 是包裹 Agent 的"反馈层"——不是业务功能目录，是横切关注点层。**
>
> - `backend/app/harness/` = 运行时反馈层（L5 Runtime 横切，每次 plan_run 在线同步执行）
> - `backend/app/evals/` = 离线反馈层（L6 外部工具链，CI / dev 手动批量）
>
> **两者并列独立，不嵌套。**（详见 [harness-overview.md §5](./harness-overview.md) 决策与依据）

---

## 2. 设计原则（先于代码）

| 原则 | 落地表现 |
|---|---|
| **与六层架构对齐** | `harness/` 与 `evals/` 都纳入 import-linter 分层守卫；禁止反向依赖 ORM |
| **横切不直入业务** | 节点只 import `app.harness.trace` / `app.harness.budget`；harness 不依赖 `app.models` / `app.repositories` |
| **Schema 先行** | 所有 Pydantic 在 `harness/contracts.py` 与 `evals/contracts.py`，harness 内部只持有 Protocol |
| **Mock 优先** | 每个 Provider / Executor 都有 mock 实现；Mock 链路先稳定，再接真实模型 |
| **运行时 vs 离线物理分离** | 运行时反馈（trace/budget/checkpoint/replay）跑在 plan_run 内；离线反馈（eval/grader/bad_case）跑在 CI / dev 入口 |
| **dev-only 强制** | Replay / Eval 的 API 在 production env 启动 assert fail |

---

## 3. 完整目录树（backend/ + scripts/ 全量）

```
backend/
├── app/
│   ├── main.py                            # FastAPI app 装配（dev 路由注册 + 启动 assert）
│   │
│   ├── core/                              # L2 config + logging + security
│   │   ├── config.py                      # pydantic-settings；含 DEFAULT_PROMPT_VERSIONS、BUDGET_*
│   │   ├── logging.py                     # structlog JSON
│   │   └── security.py
│   │
│   ├── schemas/                           # L1 API / Agent contracts（被 harness/evals 借用）
│   │   ├── agent_run.py                   # CreateRunRequest / RunDetailResponse
│   │   ├── validation.py                  # ValidationReport / ReviewResult / ReviseDecision
│   │   └── ...
│   │
│   ├── models/                            # SQLAlchemy ORM
│   │   ├── agent_run.py                   # AgentRun / AgentStep / ToolCall
│   │   ├── replay.py                      # ReplayRun
│   │   ├── eval.py                        # EvalDataset / EvalCase / EvalRun / EvalCasesVerdict
│   │   └── ...（业务表详见 data-models/）
│   │
│   ├── db/                                # session + Alembic
│   │   ├── session.py                     # AsyncSession / sessionmaker
│   │   └── migrations/versions/           # Alembic 迁移（Stage 1 起累积）
│   │
│   ├── repositories/                      # L3 持久化适配
│   │   ├── agent_run.py                   # 写 agent_runs/steps/tool_calls（trace 写入入口）
│   │   ├── replay.py
│   │   ├── eval.py
│   │   └── ...（业务表 repository 略）
│   │
│   ├── services/                          # L4 业务用例 + 状态机校验
│   │   ├── agent_run.py                   # AgentRunService（包装 LangGraph invoke + lifecycle）
│   │   ├── replay.py                      # ReplayService
│   │   ├── eval.py                        # EvalService（调 evals/runner）
│   │   └── ...
│   │
│   ├── agent/                             # L5 编排层
│   │   ├── graph.py                       # LangGraph PlanRunGraph 装配（注入 checkpointer + ToolRegistry）
│   │   ├── state.py                       # PlanState TypedDict（[TDD §4.4](../../architecture/tdd.md)）
│   │   ├── routing.py                     # 条件边函数（INTENT 路由到 plan / replan / safe_response / other）
│   │   └── nodes/                         # 11 节点实现，每个 @with_harness 装饰
│   │       ├── risk_gate.py               # 程序节点
│   │       ├── intent_router.py           # LLM 单次
│   │       ├── context_builder.py         # 程序节点
│   │       ├── career_planning_agent.py   # 唯一真 Agent（ReAct 循环 ≤2 轮 4 工具）
│   │       ├── rule_validator.py          # 程序节点（5 维程序评分 dim 1/2/3/5）
│   │       ├── quality_reviewer.py        # LLM Judge（dim 4）
│   │       ├── revise_or_fallback.py      # 路由节点（rewrite ≤2 / fallback）
│   │       ├── companion_response.py      # LLM 单次
│   │       ├── safe_response.py           # 程序（安全兜底）
│   │       ├── clarification.py           # 程序节点
│   │       └── persist.py                 # 事务节点（唯一可写持久化的节点）
│   │
│   ├── tools/                             # L5 执行层
│   │   ├── specs.py                       # ToolSpec 强类型声明（args/result schema Pydantic）
│   │   ├── registry.py                    # 运行时 ToolRegistry（按 plan_run 注入）
│   │   ├── middleware.py                  # Tool 执行中间件：超时 / 重试 / 审计 / 只读强制
│   │   └── executors/
│   │       ├── base.py                    # ToolExecutor Protocol
│   │       ├── web_search.py
│   │       ├── rag_retrieve.py
│   │       ├── memory_lookup.py
│   │       └── context_summarize.py
│   │
│   ├── providers/                         # 五类 Provider 横切
│   │   ├── base.py                        # LLMProvider / SearchProvider / Embedding / Cache / Storage Protocol
│   │   ├── llm/{base,mock,deepseek}.py
│   │   ├── search/{base,mock,tavily}.py
│   │   ├── embedding/{base,mock,bge}.py
│   │   ├── cache/{base,memory}.py
│   │   └── storage/{base,s3}.py
│   │
│   ├── prompts/                           # 记忆层-版本化（按 goal_type 分目录，对齐 TDD §3.3）
│   │   └── {ai_backend,agent_app,backend_java,data_engineer,fullstack,other}/
│   │       ├── intent_router_system_v1.py
│   │       ├── career_planning_agent_task_v1.py
│   │       ├── quality_reviewer_rubric_v1.py
│   │       └── ...
│   │
│   ├── api/                               # L6 路由
│   │   ├── v1/
│   │   │   ├── agent_runs.py              # 生产用户路由 POST/GET /agent-runs
│   │   │   ├── auth.py
│   │   │   ├── memories.py
│   │   │   ├── tasks.py
│   │   │   └── ...
│   │   └── _dev_guard.py                  # 启动 assert env != production（dev 路由注册前置）
│   │
│   ├── harness/                           # ⭐ 运行时反馈层（E1~E3, D3）
│   │   ├── __init__.py                    # 导出 trace / budget / checkpoint / replay / middleware / lifecycle
│   │   ├── contracts.py                   # TraceRecord / StepRecord / ToolRecord / BudgetSpec / LifeCycleHook
│   │   ├── lifecycle.py                   # run/step/tool 三级生命周期钩子（见 §6.4）
│   │   ├── middleware.py                  # ⭐ 协调器：@with_harness 装饰器（见 §6.5）
│   │   │
│   │   ├── trace/                         # E1: 结构化事件流（run/step/tool 三级）
│   │   │   ├── __init__.py
│   │   │   ├── writer.py                  # TraceWriter：异步批量写 + sync fallback
│   │   │   ├── reader.py                  # TraceReader：按 run_id/step_id 查询 spans
│   │   │   └── decorators.py              # @trace_step / @trace_tool 装饰器
│   │   │
│   │   ├── budget/                        # D3: 预算守门
│   │   │   ├── __init__.py
│   │   │   ├── policy.py                  # BudgetPolicy（不可变 dataclass）
│   │   │   ├── tracker.py                 # 运行时累加 + 阈值检查
│   │   │   └── exceptions.py              # BudgetExceeded
│   │   │
│   │   ├── checkpoint/                    # E2: LangGraph Checkpointer 适配
│   │   │   ├── __init__.py
│   │   │   └── postgres_checkpointer.py   # 包装 langgraph PostgresSaver；thread_id = session_id
│   │   │
│   │   └── replay/                        # E3: Replay 引擎
│   │       ├── __init__.py
│   │       ├── snapshot.py                # rebuild_replay_input(run_id) → ReplayInput
│   │       ├── engine.py                  # ReplayEngine.invoke(input) → ReplayResult
│   │       ├── diff.py                    # 结构化 diff：hash 短路 + changed_fields
│   │       └── fixtures/                  # 工件库：{tool_name}/{args_hash}.json
│   │           └── README.md              # 说明 fixture 维护规则
│   │
│   └── evals/                             # ⭐ 离线反馈层（F2/F3/F4）—— 与 harness/ 并列
│       ├── __init__.py
│       ├── contracts.py                   # EvalCase / EvalCaseInput / EvalCaseExpected / GraderResult / CaseVerdict
│       │
│       ├── datasets/                      # 固定数据集（YAML，自包含）
│       │   ├── default_v1.yaml            # 30 case 初始集（Stage 3-5 渐进补齐）
│       │   └── README.md                  # case 编写规则
│       │
│       ├── graders/                       # 评分器（实现 Grader Protocol）
│       │   ├── base.py                    # Grader Protocol + GraderResult
│       │   ├── status_grader.py           # run.status vs expected_status
│       │   ├── intent_grader.py           # intent 对比
│       │   ├── task_structure_grader.py   # task_count / keywords / 单 task ≤60min
│       │   ├── dimensions_grader.py       # 五维程序评分（rule_validator 重跑）
│       │   ├── safety_grader.py           # safety routing + 12356 校验
│       │   └── output_grader.py           # LLM Judge grader（仅 fail 时触发）
│       │
│       ├── runner.py                      # EvalRunner：批量跑 case + 写 eval_runs/verdicts
│       ├── judge.py                       # verdict(eval_run, baseline) → Diff（CI 退出码语义）
│       ├── bad_case.py                    # source_run → EvalCase transform
│       └── cli.py                         # python -m app.evals.cli run --dataset=default
│
├── api/v1/dev/                            # dev-only 路由（生产 fail-fast）
│   ├── __init__.py
│   ├── replays.py                         # POST/GET /api/v1/dev/replays
│   ├── eval_runs.py                       # /api/v1/dev/eval/runs
│   ├── bad_cases.py                       # /api/v1/dev/eval/bad-cases
│   └── traces.py                          # /api/v1/dev/traces
│
├── tests/
│   ├── unit/                              # 单测：节点 / grader / budget
│   ├── integration/                       # 端到端 plan_run（含 trace 写入验证）
│   ├── contract/                          # OpenAPI snapshot + Provider 契约
│   ├── fixtures/                          # 真实 trace 样本 / prompt fixture
│   ├── eval/                              # 等价 pytest tests/eval/（grader 单测）
│   └── fault_injection/                   # 故障注入（LLM 超时 / Tool 失败 / DB 死锁）
│
├── contracts/
│   └── openapi_snapshot.json              # 真理源（[check-contracts.sh](../../governance/check-scripts-spec.md) 对照）
│
├── pyproject.toml                         # 依赖 + ruff/mypy/pytest 配置
└── .importlinter.toml                     # 六层 + harness + evals 分层守卫

scripts/
├── check.sh                               # 总入口
├── check-architecture.sh                  # import-linter
├── check-contracts.sh                     # OpenAPI snapshot 对比
├── check-doc-status.sh                    # 文档状态字段
├── check-doc-links.sh                     # 相对链接有效性
├── check-eval.sh                          # 调 evals.cli + 判 pass_rate ≥85%
├── seed-experience-atoms.py               # 经验原子导入（Stage 4）
├── seed-eval-dataset.py                   # Eval dataset 导入（Stage 5）
├── show-trace.sh <run_id>                 # 调 /api/v1/dev/traces/{id}
└── replay.sh <run_id>                     # 调 /api/v1/dev/replays
```

---

## 4. 子目录三要素表

| 子目录 | 职责 | 关键依赖 | 入口 |
|---|---|---|---|
| `harness/trace/` | 三级事件写入与查询 | `repositories.agent_run` + `schemas.agent_run` | `@trace_step` / `@trace_tool` |
| `harness/budget/` | token / cost / calls / time 累加 + 阈值 | `core.config` | `@budget(...)` / `BudgetPolicy.evaluate()` |
| `harness/checkpoint/` | LangGraph PostgresSaver 包装 | `langgraph.checkpoint.postgres` | `agent/graph.py` 装配时注入 |
| `harness/replay/` | 输入快照重建 + 重跑 + diff | `harness/trace` + `agent/graph` + `tools/executors` | `services.replay` → `ReplayEngine.invoke()` |
| `harness/middleware.py` | 协调器：trace + budget + lifecycle 串成中间件链 | 上述所有 | 节点装饰器 `@with_harness` |
| `harness/lifecycle.py` | run/step/tool 三级生命周期钩子 | `harness/trace` + `core.logging` | middleware 调用 |
| `evals/` | 离线 case 集 + grader + runner + judge | `agent/graph` + `harness/trace`（读 fixture） | `evals.cli` / `scripts/check-eval.sh` |
| `api/v1/dev/` | Replay / Eval / Trace HTTP 入口（dev-only） | `services.{replay, eval, agent_run}` | FastAPI 路由 |
| `tools/middleware.py` | 工具执行中间件（非 harness） | `providers` | `ToolRegistry.invoke()` |

---

## 5. import-linter 增强（更新 [check-scripts-spec.md](../../governance/check-scripts-spec.md) §1）

```toml
[importlinter]
root_package = app

# 原 six-layers 保留，新增 harness / evals
[importlinter:contract:six-layers]
name = 六层依赖
type = layers
layers =
    app.api,
    app.services,
    app.agent,
    app.tools,
    app.providers,
    app.repositories,
    app.schemas,
    app.core

# 新增：harness 横切层守卫
[importlinter:contract:harness-layer]
name = Harness 横切层方向
type = layers
layers =
    app.agent,        # 可调 harness（节点用 @with_harness）
    app.harness,      # 中间件层
    app.providers,    # harness 内 Provider 调用
    app.core

[importlinter:contract:harness-no-orm]
name = Harness 不依赖 ORM
type = forbidden
source_modules = app.harness
forbidden_modules = app.models, app.repositories

# 新增：evals 离线层守卫
[importlinter:contract:evals-isolation]
name = Evals 不进入运行时
type = forbidden
source_modules = app.agent, app.services.agent_run, app.api.v1.agent_runs
forbidden_modules = app.evals

[importlinter:contract:providers-isolation]
# 原规则保留
name = Providers 不向上暴露厂商对象
type = forbidden
source_modules = app.providers
forbidden_modules = app.api, app.services, app.agent
```

**守护意图**：

- `app.harness` 不能反向 import `app.models`/`app.repositories`（横切层必须经 repositories 写表，不经 ORM 直接改）
- `app.evals` **不能被运行时路径** import（防 evals 代码意外进 plan_run 主路径）
- Providers 不暴露 deepseek-sdk / tavily-sdk 原始响应

---

## 6. 关键模块专业语义对应

### 6.1 Trace 子层（E1）

| 业界术语（OTel / LangSmith） | 本项目实现 |
|---|---|
| **Trace** | `agent_runs` 一行 |
| **Span** | `agent_steps` 一行 |
| **Span event / sub-span** | `tool_calls` 一行 |
| **Exporter** | `TraceWriter.write_step` |
| **Sampler** | 全采（MVP 不抽样）|
| **Propagator** | run_id 透传上下文 |
| **Attribute** | `trace_data jsonb` |
| **Hash**（OTel 无对应） | `args_hash` / `result_hash` —— Replay 专利 |

### 6.2 Budget 子层（D3）

| 业界术语 | 本项目实现 |
|---|---|
| **Policy** | `BudgetPolicy` 不可变 dataclass |
| **Meter / Counter** | `BudgetTracker.consume()` |
| **Gate / Sentinel** | 节点入口的 `evaluate() → Continue / Halt` |
| **Quota** | `max_cost_cny / max_tool_calls` |
| **Deadline** | `deadline_at` datetime |
| **Admission control** | pre-step + per-step 双检查 |

### 6.3 Checkpoint 子层（E2）

| 业界术语（LangGraph） | 本项目实现 |
|---|---|
| **Checkpointer** | `postgres_checkpointer.py::get_saver()` |
| **ThreadId** | `session_id`（非 `run_id`，多 run 一会话共享）|
| **Super-step** | LangGraph 节点边 |
| **TTL** | 7 天 cron 清理（Stage 7 落地） |
| **Resume** | `graph.ainvoke(state, config={"thread_id": ...})` |

### 6.4 Lifecycle 钩子（harness 协调器调度）

| 钩子 | 触发时机 | 行为 | 失败时 |
|---|---|---|---|
| `on_run_start` | AgentRunService.invoke 前 | 写 `agent_runs status=running` | 请求 500 |
| `on_run_end` | graph 返回或异常 | 更新 finished_at + status | 写 status=failed + fallback_reason |
| `on_step_start` | @with_harness 入口 | 写 `agent_steps`（pending 状态） | 节点不执行 |
| `on_step_end` | 节点正常返回 | 更新 tokens / cost / latency / output_hash | —— |
| `on_step_failure` | 节点抛异常 | 写 fallback_reason + error_class | —— |
| `on_tool_call` | tool 调用完成 | 写 `tool_calls` 子表一行 | 单工具失败不阻塞 run |
| `on_degraded` | 降级路径触发 | run status=degraded + fallback_reason | —— |

### 6.5 @with_harness 协调器（横切层落地标准做法）

```python
# harness/middleware.py — 节点用例（不实现，仅演示 API）
from app.harness import with_harness, BudgetSpec

@with_harness(
    node_name="intent_router",
    budget=BudgetSpec(max_cost_cny=0.01, timeout_s=3),
    trace_fields=["intent", "confidence"],
)
async def intent_router(state: PlanState) -> PlanState:
    # 业务代码只关心业务逻辑
    result = await llm_provider.invoke(...)
    state.intent_result = result
    return state
```

`@with_harness` 内部按顺序：

1. `lifecycle.on_step_start(run_id, node_name)` → 写 pending step
2. `budget.evaluate(policy, run_state)` → 不够则抛 BudgetExceeded
3. 业务函数执行
4. `budget.consume(usage)` → 累加
5. `lifecycle.on_step_end(...)` → 更新字段
6. `lifecycle.on_step_failure(...)` → 异常时写 error_class

**这把横切关注点收口**：节点代码只剩业务逻辑，trace / budget / lifecycle 不再散落。

### 6.6 Replay 引擎（E3）

| 业界术语 | 本项目实现 |
|---|---|
| **Snapshot** | `snapshot.py` 从 trace 表读 step[0..2] 重建输入 |
| **Replay** | `ReplayEngine.invoke(replay_input)` 只重跑 agent 节点起 |
| **Override** | prompt_versions / model / tool_mode 三档 |
| **Fixture registry** | `replay/fixtures/{tool}/{args_hash}.json` — property-based testing 同构 |
| **Property** | reproducibility（不依赖外部状态） |
| **Delta / Diff** | `diff.py::diff(before, after) → ChangedFields` |

### 6.7 Eval 子层（F2/F3/F4）

| 业界术语 | 本项目实现 |
|---|---|
| **Golden dataset** | `evals/datasets/default_v1.yaml`（30 case）|
| **Autograder** | `evals/graders/*.py`（6 个） |
| **Short-circuit** | grader 链短路 return（见 [eval-system.md §3.3](./eval-system.md)） |
| **Regression suite** | `scripts/check-eval.sh` 跑全 dataset |
| **Silent regression** | 已 pass case 翻 fail（不被允许，CI 阻断） |
| **Baseline diff** | `evals/judge.py::verdict(current, baseline)` |
| **Bad case loop** | `evals/bad_case.py::transform(run_id) → EvalCase` + dataset minor bump |

---

## 7. 入口与生命周期总图

```mermaid
flowchart TB
    REQ([HTTP POST /api/v1/agent-runs]) --> ROUTER[api/v1/agent_runs.py]
    ROUTER --> SVC[services/agent_run.py<br/>AgentRunService.invoke]
    SVC --> LC1[harness/lifecycle.on_run_start<br/>写 agent_runs status=running]
    LC1 --> GRAPH[agent/graph.py<br/>graph.ainvoke PlanState]
    GRAPH --> NODE[agent/nodes/&lt;N&gt;.py<br/>@with_harness 已装饰]
    NODE --> HW[harness/middleware @with_harness]
    HW --> LC2[lifecycle.on_step_start]
    HW --> BE[业务执行：LLM Tool ReAct]
    BE --> PROV[providers/*]
    BE --> TOOLS[tools/executors/*]
    HW --> LC3[lifecycle.on_step_end<br/>写 tokens/cost/latency]
    LC3 --> NEXT{下一步}
    NEXT -->|rewrite| NODE
    NEXT -->|end| LC4[lifecycle.on_run_end]
    LC4 --> RESP([HTTP Response + SSE plan_ready])
```

**关键纪律**：节点业务代码不直接调 `TraceWriter`；全部经 `@with_harness` 装饰器。这是横切层一致性的保证。

---

## 8. 与 Stage 退出的对齐

| Stage | 落地代码 | 退出条件相关 |
|---|---|---|
| 0 工程基线 | `main.py` + `core/` + `db/` + `scripts/check.sh` | `/health` 200 + Docker + Alembic + import-linter |
| 1 契约冻结 | `schemas/` + `models/` + `db/migrations/`（含 `agent_run / replay / eval` 表迁移） | Pydantic + Alembic + OpenAPI snapshot |
| 2 纵切 Mock | `agent/graph.py` + `agent/nodes/*` Mock + `harness/{trace, budget, lifecycle, middleware}` + `tests/integration` | LangGraph + Trace 表写满 + Dev Trace 页可见 |
| 3 真实模型 | `providers/llm/deepseek.py` + 真实节点替换 Mock + `harness/budget` 真实计数 | DeepSeek + 5 维评分 + 重写/降级全验 |
| 4 证据增强 | `tools/executors/{web_search, rag_retrieve}` + `prompts/{goal_type}/*` | Tavily + pgvector + 30-50 经验原子 |
| 5 Harness 完成 | `harness/replay/` + `evals/*` + `api/v1/dev/*` + `scripts/{check-eval.sh, replay.sh}` | Replay 页 + 30 case Eval + Bad Case 闭环 + 85% 通过率 |

---

## 9. 明确不做什么（防范围蔓延）

| 不做 | 理由 |
|---|---|
| OpenTelemetry / Jaeger 接入 | MVP 自建 trace 表够用；OTel 接演进触发（[ADR-001](../../architecture/adr.md)） |
| LangSmith / LangFuse 接入 | 同上 |
| 多 Agent / Sub-graph | ADR-002 否决多 Agent |
| Harness 自进化（论文 Meta-Evolution Loop） | F5 论文级，非 MVP |
| 运行时 Stop Hook（Anthropic 8 次反阻断规则） | 非 MVP；CI 级 hook 已覆盖 |
| 分布式 trace 跨服务 | 单体 FastAPI，演进触发 |
| `harness/eval/` 嵌套 | **方案 A 否决**（见 [harness-overview.md §5](./harness-overview.md) 决策） |

---

## 10. 关键文件速查表

| 模块 | 文件 | 核心抽象 | 测试方式 |
|---|---|---|---|
| Trace 写入 | `harness/trace/writer.py` | `TraceWriter.write_step / write_tool_call` | 单测 + 集成测验证字段 |
| Trace 装饰器 | `harness/trace/decorators.py` | `@trace_step / @trace_tool` | 集成测验证节点装饰后字段齐全 |
| Budget | `harness/budget/*.py` | `BudgetPolicy + BudgetTracker` | 单测 + fault injection（超预算触发降级）|
| Checkpoint | `harness/checkpoint/postgres_checkpointer.py` | LangGraph PostgresSaver 包装 | 端到端：kill 进程后 resume |
| Replay 引擎 | `harness/replay/{snapshot,engine,diff}.py` | `ReplayEngine.invoke` | fixture-based 测 + hash diff 正确性 |
| 协调器 | `harness/middleware.py` | `@with_harness` | 集成测：每个节点都装饰、字段齐全 |
| 生命周期 | `harness/lifecycle.py` | 钩子 7 个 | 单测每个钩子独立 + 故障注入 |
| Eval Runner | `evals/runner.py` | `EvalRunner.run(dataset_id)` | 用 5 个 golden case 单测 |
| Grader 套件 | `evals/graders/*.py` | 6 个 `Grader` 实现 | 每个 case 独立测（pass + fail 各一） |
| Eval Judge | `evals/judge.py` | `Judge.verdict(eval_run, baseline)` | silent regression 检测单测 |
| Bad Case | `evals/bad_case.py` | `transform(run_id) → EvalCase` | 用真实 trace fixture 测 |
| Dev API | `api/v1/dev/*.py` + `_dev_guard.py` | FastAPI router + startup assert | 契约测 + 启动 assert 测 |
| Fixture 库 | `harness/replay/fixtures/` + `tests/fixtures/` | hash 化 JSON | schema validate + 加载正确性 |

---

## 11. 参考依据

| 来源 | 用于本文 § |
|---|---|
| [TDD §3.3 仓库结构](../../architecture/tdd.md) | §3 全部 |
| [TDD §3.2.1 Provider Protocol](../../architecture/tdd.md) | §3 providers/ |
| [TDD §4.4 PlanState](../../architecture/tdd.md) | §3 agent/state.py |
| [TDD §12 Harness](../../architecture/tdd.md) | §2 原则、§6 专业对应、§7 生命周期 |
| [ADR-001](../../architecture/adr.md) | §9 演进原则 |
| [ADR-002](../../architecture/adr.md) | §9 单 Agent 立场 |
| [ADR-005](../../architecture/adr.md) | §3 providers/ |
| [ADR-009](../../architecture/adr.md) | §3 langgraph 选型 |
| [trace-tables.md](../data-models/trace-tables.md) | §3 models/agent_run.py |
| [state-machines/run-status.mmd](../state-machines/run-status.mmd) | §6.4 on_run_*, on_degraded |
| [check-scripts-spec.md](../../governance/check-scripts-spec.md) | §5 import-linter 增强 |
| [stage-delivery-definition.md](../../governance/stage-delivery-definition.md) | §8 stage 对齐 |
| [prompt-versioning-standard.md](../../standards/prompts/prompt-versioning-standard.md) | §3 prompts/{goal_type}/ |
| [harness-overview.md](./harness-overview.md) | 全部概念映射依据 |
| [replay.md](./replay.md) | §3 replay/ + §6.6 |
| [eval-system.md](./eval-system.md) | §3 evals/ + §6.7 |
| 《Harness-engineering 开源工程分享》PDF | §6 专业术语对应 |
| OpenHands / LangSmith / Claude Code / Continue | §6 业界术语 |

---

## 12. 与现有 spec 的口径修正

本文件落定后，下列 spec 需对应同步（**未来 Stage 0 启动时一次性合入**，不阻塞当前评审）：

| 文件 | 修正点 |
|---|---|
| [tdd.md](../../architecture/tdd.md) §3.3 | 已含 `harness/ + evals/` 顶层，无需改 |
| [check-scripts-spec.md](../../governance/check-scripts-spec.md) §1 | `.importlinter.toml` 增 `harness-layer` / `harness-no-orm` / `evals-isolation` 三规则（见本文 §5） |
| [harness-overview.md](./harness-overview.md) §5 | 已同步：方案 A，evals/ 平级 |
| [eval-system.md](./eval-system.md) §1.1 | 已同步：明确属 `evals/` 目录 |
| [prompt-versioning-standard.md](../../standards/prompts/prompt-versioning-standard.md) §1 | 文件命名例子改为 `{goal_type}/<node>_system_v<n>.py`（与 TDD §3.3 一致） |
| [model-design/README.md](../README.md) | 登记本文档为 harness/ 文件清单之一 |

---

*本施工总图是 Stage 0+ 写代码时的导航；5 分钟入门见 [harness-overview.md §0](./harness-overview.md)，详细子能力见 [replay.md](./replay.md) / [eval-system.md](./eval-system.md) / [../ui-spec/developer-trace.md](../ui-spec/developer-trace.md)。*
