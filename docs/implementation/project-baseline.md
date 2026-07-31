# 项目实现基线

| 项目 | 决策 |
|---|---|
| 项目形态 | 独立 FastAPI 单体 + React SPA |
| 与 ClawAgent 关系 | 无代码依赖、无运行时依赖、无数据库依赖 |
| Agent | 1 个 `CareerPlanningAgent` + 受控节点 + 统一 Runtime/Harness |
| 数据库 | PostgreSQL 16 + pgvector |
| 异步执行 | MVP 单 Worker 进程内任务；状态和事件持久化到 PostgreSQL |
| SSE | `agent_events` 作为断线续传事实源；heartbeat 不持久化 |
| Provider | LLM / Search / Embedding 三类 Protocol |
| 运行时模型 | OpenAI-compatible，完全由环境变量配置 |
| 编码助手 | 使用 Codex；只参与开发，不写入运行时架构依赖 |
| 任务队列 | MVP 不引入 Redis/Celery；多 Worker 前必须升级 |
| 部署 | Docker Compose 单机 |

## 1. 核心用例

```text
Guest 登录 → 建档 → 创建 Agent Run → SSE 查看进度
→ 获得中期方向与今日任务 → 更新任务状态 → 提交复盘 → 生成次日 continue/adjust 计划
→ 系统建议重规划 → 用户确认 → 产生新计划版本
```

## 2. 后端分层

```text
api        HTTP、JWT、SSE、错误映射
schemas    Pydantic DTO、枚举
services   用例、事务、状态机、幂等
repositories SQLAlchemy 查询与持久化
agent      LangGraph、节点、状态对象
providers  LLM/Search/Embedding 外部适配
harness    Trace、预算、事件、Eval
core       配置、日志、数据库、通用异常
```

依赖方向：

```text
api → services → repositories
           └→ agent → providers
           └→ harness
```

Agent 节点不得直接依赖 ORM Model。

## 3. MVP Agent Graph

核心节点：

1. `risk_gate`
2. `intent_router`
3. `clarification`
4. `context_builder`
5. `career_planning_agent`
6. `rule_validator`
7. `revise_or_fallback`
8. `companion_response`
9. `persist`
10. `safe_response`（风险分支）

增强节点：

- `quality_reviewer`：Stage 5 再启用；
- `distill_evidence`：Stage 4 再启用。

## 4. 状态机

### AgentRunStatus

```text
pending → running → completed
                 ↘ degraded
                 ↘ failed
pending/running → cancelled
```

### PlanStatus

```text
generated → active → completed → archived
generated/active → archived
```

`adopted_at` 是时间字段，不是状态。用户首次开始任务时，计划从 generated 进入 active。

### TaskStatus

```text
pending → in_progress → completed
pending/in_progress → abandoned
pending → expired
```

## 5. 运行时限制

- 单用户同一时刻最多 1 个 pending/running Run；
- 主 Agent 最多 2 轮 Tool Calling、每轮最多 2 个、总 Tool 调用最多 4；
- Stage 2/3 单 Run最多 5 次 LLM；Stage 4 最多 7 次；Stage 5 仅在线 enforce reviewer 时最多 8 次；
- 单 Tool 默认超时 8 秒；
- 单 Run 默认截止时间 45 秒；
- 单 Run 默认总 Token 预算 16000，单次输入 6000、输出 1500（均可配置）；
- 结构化格式失败最多修复 1 次；业务规则失败最多使用专用 repair Prompt 修复 1 次；
- 计划包含 1~8 周方向与周重点；今日任务 1~3 个，总预计时长不得超过用户预算；
- 取消和超时必须通过统一 Finalizer 写唯一最终状态及事件；
- Run 冻结 graph/config snapshot，context_builder 后冻结 input snapshot；
- 终态 result_kind 仅为 plan/clarification/safe_response；failed/cancelled 无结果。

## 6. 数据表基线

业务表：

- users
- user_profiles
- plans
- tasks
- reviews
- memories
- memory_candidates
- search_sources
- experience_atoms
- companion_messages

运行表：

- agent_runs
- agent_steps
- tool_calls
- agent_events

Eval 第一版使用仓库内 JSONL 数据集；实验结果可写 `eval_experiments`，不是 Stage 1 阻塞项。

## 7. 环境变量

```env
APP_ENV=local
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/career_buddy
JWT_SECRET=change-me
JWT_EXPIRE_MINUTES=1440

LLM_PROVIDER=openai_compatible
LLM_BASE_URL=
LLM_API_KEY=
LLM_MODEL=
LLM_ROUTER_MODEL=

SEARCH_PROVIDER=mock
SEARCH_API_KEY=
EMBEDDING_PROVIDER=mock
EMBEDDING_MODEL=
EMBEDDING_DIM=1024

AGENT_GRAPH_VERSION=v1
AGENT_MAX_LLM_CALLS=7
AGENT_STAGE23_MAX_LLM_CALLS=5
AGENT_ONLINE_REVIEW_MAX_LLM_CALLS=8
AGENT_MAX_TOOL_ROUNDS=2
AGENT_MAX_TOOL_CALLS=4
AGENT_MAX_TOTAL_TOKENS=16000
AGENT_MAX_INPUT_TOKENS_PER_CALL=6000
AGENT_MAX_OUTPUT_TOKENS_PER_CALL=1500
QUALITY_REVIEW_ENFORCE=false
AGENT_DEADLINE_SECONDS=45
```

## 8. 明确不做

MVP 不做：

- 复用 ClawAgent；
- 多 Agent；
- MCP 工具市场；
- Redis/Celery/Kafka；
- 微服务拆分；
- 多 Worker 可靠调度；
- 复杂 OAuth；
- 主动消息推送；
- 生产级心理健康服务。
