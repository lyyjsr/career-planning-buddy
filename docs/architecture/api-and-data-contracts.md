# API 与数据契约 v1.0

| 项目 | 内容 |
|---|---|
| 文档版本 | v1.0 |
| 日期 | 2026-07-11 |
| 状态 | 定稿（可作为 AI 开发的 OpenAPI 建模与契约测试依据） |
| 关联 | [PRD v2.0](./../overview/product-overview.md)、[TDD v1.0](././tdd.md)、[ADR v2.0](././adr.md) |
| 来源 | 同伴方案 v1.0 主体（路径/Header/Schema/状态机/契约原则直接采纳）+ 我们的 4 个端到端 Payload 示例 + 单 Agent 模型调整 |
| 权威性 | **本协议是接口路径、请求响应字段、枚举、错误码、状态机与跨语言序列化的权威来源**；PRD/TDD 中的接口路径示例以本协议为准 |

---

## 0. 协议摘要

| 主题 | 正式约定 |
|---|---|
| 基路径 | 外部 `/api/v1`；开发者 `/api/v1/dev` |
| 格式 | `application/json; charset=utf-8`；字段 snake_case；时间 RFC 3339 UTC |
| 异步任务 | 创建 Agent Run 返回 202 + run_id；GET 状态为权威，SSE 只提供实时增强 |
| 一致性 | 非天然幂等写接口使用 `Idempotency-Key`；状态更新携带 `version` 乐观锁 |
| 业务写入 | Agent 不直接写业务表；候选计划必须经 Service 校验后保存 |
| 版本 | 兼容新增字段允许；删除/改名/类型变化属于破坏性变更 |
| Mock | Mock/合成数据必须带 `data_origin`，禁止混入真实统计 |
| 当前用户 | 不带 `/me/` 前缀（决策 1.x，详见 §4.1）；通过 JWT 推断 user_id，**不信任前端传入 user_id** |

---

## 1. 通用协议规范

### 1.1 基础约定

| 项 | 约定 |
|---|---|
| 传输 | HTTPS；JSON UTF-8 |
| 字段命名 | JSON / DB 字段 / 事件 data 全部 snake_case |
| ID | UUID 字符串 |
| 时间 | RFC 3339 UTC（如 `2026-07-10T07:30:00Z`） |
| 日期 | ISO 8601 date |
| 时长 | 整数分钟 `duration_minutes` 或毫秒 `latency_ms` |
| 布尔 | 只允许 true/false |
| 空值 | 缺省=未提供；null 仅协议明确允许清空时用 |
| 枚举 | 小写 snake_case；未知枚举不得静默映射 |
| Schema | 关键对象 `additionalProperties=false`；客户端忽略新增响应字段 |

### 1.2 Header

| Header | 方向 | 要求 |
|---|---|---|
| Authorization | 请求 | `Bearer <jwt>`（MVP 可用简化 token） |
| Content-Type | 请求 | `application/json` |
| Accept | 请求 | `application/json`；SSE 为 `text/event-stream` |
| X-Request-Id | 双向 | 客户端可传 UUID；缺省服务端生成并返回 |
| Idempotency-Key | 请求 | 创建 Run / 任务状态 / 复盘 / 内部保存等写接口必填 |
| If-Match-Version | 请求 | 可选 Header；优先使用 Body 中的 `version` |
| Last-Event-Id | SSE | 断线重连游标 |

---

## 2. 身份、权限与数据作用域

### 2.1 外部身份
- JWT，MVP 用简化登录签发；远期上线接微信 openid
- 用户只能访问 `/me/*` 资源；不信任前端传 user_id
- 管理员用独立 role 访问后台

### 2.2 敏感字段
- 密码、记忆敏感内容、Trace 输入摘要——返回时脱敏或哈希

---

## 3. 响应、错误、分页与幂等

### 3.1 成功响应
```json
{ "data": {...}, "meta": {"request_id": "...", "version": "1.0.0"} }
```

### 3.2 错误响应
```json
{
  "error": {
    "code": "PLAN_NOT_FOUND",
    "message": "可读的错误说明",
    "details": {...},
    "request_id": "..."
  }
}
```

### 3.3 错误码规范

| 前缀 | 含义 |
|---|---|
| `AUTH_*` | 鉴权失败（401 / 403） |
| `VALIDATION_*` | 字段校验失败（422） |
| `STATE_*` | 状态机违规（409） |
| `NOT_FOUND_*` | 资源不存在（404） |
| `RATE_LIMITED_*` | 限流（429） |
| `AGENT_*` | Agent 执行错误（500/503） |
| `FALLBACK_*` | 降级（200，body 带 `fallback_reason`） |

### 3.4 Cursor 分页
- `?cursor=xxx&limit=20`
- 响应 meta 含 `next_cursor`；null 表示无更多页

### 3.5 幂等
- `Idempotency-Key` 在 24h 内重复返回首次结果
- 所有写接口必填

---

## 4. API 总览

### 4.1 外部 API

> **路径前缀规则**（决策 1.x）：所有"当前用户资源"路径统一走 `/api/v1/<resource>`（**不带** `/me/`），依靠 JWT 推断 user_id（"不信任前端传入 user_id"，§2.1）。下表保留旧 `/me/*` 写法仅作历史参考，请以**新路径列**为准。

| 路径（新） | 旧路径 | 方法 | 用途 | 端点 spec |
|---|---|---|---|---|
| `/api/v1/auth/login` | — | POST | 登录获取 JWT | [auth.md](../model-design/api-spec/auth.md) |
| `/api/v1/profile` | `/me/profile` | GET/PUT/**PATCH** | 读取/upsert/部分更新画像 | [profile.md](../model-design/api-spec/profile.md) |
| `/api/v1/agent-runs` | — | POST | 创建规划运行（异步 202） | [agent-runs.md](../model-design/api-spec/agent-runs.md) |
| `/api/v1/agent-runs/{run_id}` | — | GET | 查询运行状态 | 同上 |
| `/api/v1/agent-runs/{run_id}/cancel` | — | POST | 取消运行 | 同上 |
| `/api/v1/agent-runs/{run_id}/events` | — | GET（SSE） | 订阅运行事件流 | 同上 |
| `/api/v1/plans` | `/me/plans` | GET | 我的规划历史（cursor 分页） | [plans.md](../model-design/api-spec/plans.md) |
| `/api/v1/plans/active` | `/me/plans/active` | GET | 当前活跃计划 | 同上 |
| `/api/v1/plans/{plan_id}` | — | GET | 计划详情 | 同上 |
| `/api/v1/plans/{plan_id}/sources` | — | GET | 计划关联来源 | 同上 |
| `/api/v1/tasks/today` | `/me/tasks/today` | GET | 今日任务（专用） | [tasks.md](../model-design/api-spec/tasks.md) |
| `/api/v1/tasks` | `/me/tasks` | GET | 任务列表（带筛选） | 同上 |
| `/api/v1/tasks/{task_id}` | `/tasks/{id}/transitions` | PATCH | 任务状态转换 | 同上 |
| `/api/v1/reviews` | `/me/reviews` | POST | 提交复盘 | [reviews.md](../model-design/api-spec/reviews.md) |
| `/api/v1/reviews` | `/me/reviews` | GET | 复盘列表 | 同上 |
| `/api/v1/reviews/{review_id}/accept-replan` | — | POST | 接受建议的 replan | 同上 |
| `/api/v1/memories` | `/me/memories` | GET | 记忆列表 | [memories.md](../model-design/api-spec/memories.md) |
| `/api/v1/memories/{memory_id}` | `/me/memories/{id}` | DELETE | 删除记忆 | 同上 |
| `/api/v1/memories/{memory_id}` | `/me/memories/{id}` | PATCH | 关闭/激活记忆 | 同上 |
| `/api/v1/memory-candidates` | `/me/memory-candidates` | GET | 候选列表 | 同上 |
| `/api/v1/memory-candidates/{id}/confirm` | `/me/memory-candidates/{id}/confirm` | POST | 确认敏感记忆候选 | 同上 |
| `/api/v1/memory-candidates/{id}/reject` | — | POST | 拒绝候选 | 同上 |
| `/api/v1/me` | — | GET | "次日续上"摘要（active plan + today tasks + 昨日 review 摘要） | [profile.md §me](../model-design/api-spec/profile.md) |

### 4.2 开发者 API

| 路径 | 方法 | 用途 |
|---|---|---|
| `/api/v1/dev/runs` | GET | Agent Run 列表 |
| `/api/v1/dev/runs/{run_id}` | GET | Run 详情（含 steps/tool_calls） |
| `/api/v1/dev/runs/{run_id}/replay` | POST | 使用同输入重跑 |
| `/api/v1/dev/evals/datasets` | GET/POST | 评测数据集 |
| `/api/v1/dev/evals/experiments` | POST | 启动评测实验 |

---

## 5. 核心数据 Schema

### 5.1 UserProfile（**响应视图**；存储表见 [user_profiles.md](../model-design/data-models/user_profiles.md)）

> **决策 7/8**：技能以 `skill_summary` 自由文本为单一入口；target_companies / preferences 等可演进字段折叠进 `profile_preferences jsonb`；deadline 单列入表（规划计算依赖）。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| user_id | UUID | ✅ | |
| goal_type | GoalType 枚举 | ✅ | `ai_backend / data_engineer / agent_app / fullstack / backend_java / other` |
| stage | `early / mid / late / unknown` | ✅ | 求职阶段（**决策 10 术语映射**：early=大三/研一，mid=大四/研二，late=临近 offer，unknown=未提供） |
| time_budget_minutes | int (15-480) | ✅ | 每日可用时间（PRD 别名 available_minutes，统一为 time_budget_minutes） |
| skill_level | `beginner / intermediate / advanced` | ✅ | |
| skill_summary | string (max 2000) | ❌ | 技能自由描述 |
| employment_status | `student_year_4 / fresher / working / gap` | ❌ | |
| deadline | date | ❌ | 截止日期 |
| target_companies | list[string] \| null | ❌ | 由 `profile_preferences.target_companies` 投影 |
| preferences | ProfilePreferences \| null | ❌ | 透传 `profile_preferences` jsonb |
| version | int | ✅ | 乐观锁 |
| updated_at | timestamp | ✅ | |

### 5.2 PlanDetail（**响应视图**；存储表见 [plans.md](../model-design/data-models/plans.md)）

> **决策 3**：plan 实体的存储模型为 `plans.id/user_id/version/status/content_json`（一个 jsonb 字段）；此处的多字段 PlanDetail 是 service 由 plans + tasks（关联表）+ search_sources + companion_messages 拼装出的**响应视图**。

| 字段 | 类型 | 来源 |
|---|---|---|
| plan_id | UUID | plans.id |
| user_id | UUID | plans.user_id |
| horizon | `overall / weekly / today` | service 组装（默认 today） |
| summary | string | plans.content_json.rationale |
| milestones | list[Milestone]? | plans.content_json.milestones |
| weekly_focus | WeeklyFocus? | plans.content_json.weekly_focus |
| today_tasks | list[PlanTask] | 由 tasks 表 JOIN（plan_id 等值） |
| adjustment_reason | string? | plans.content_json.adjustment_reason（replan 时填） |
| companion_message | string? | 由 [companion_messages 表](../model-design/data-models/companion_messages.md) 当前 plan 关联行拼接 |
| sources | list[SourceRef] | 由 search_sources 表 + run_id 关联查询 |
| status | PlanStatus | plans.status（**决策 2**：`pending / active / adopted / completed / archived`） |
| version | int | plans.version |
| created_at / updated_at | timestamp | 同 |

### 5.3 PlanTask（**响应视图**；存储表见 [tasks.md](../model-design/data-models/tasks.md)）

> **决策 4**：存储字段以 `state / order_index / abandoned_reason / abandoned_reason_text` 为准；优先级等 view 字段由 service 映射。

| 字段 | 类型 | 来源 |
|---|---|---|
| task_id | UUID | tasks.id |
| title | string | tasks.starter_action 派生（或 tasks.deliverable 摘要） |
| starter_action | string | tasks.starter_action |
| duration_minutes | int | tasks.estimated_minutes |
| deliverable | string | tasks.deliverable |
| priority | int (1-3) | service 由 `tasks.order_index + 1` 映射 |
| status | TaskStatus | tasks.state（值相同：`pending / in_progress / completed / abandoned / expired`） |
| started_at / completed_at | timestamp? | 同 |
| abandon_reason_code | string? | tasks.abandoned_reason |
| abandon_reason_text | string? | tasks.abandoned_reason_text（**新增**，决策 4）|

### 5.4 SourceRef / SearchResult

| 字段 | 类型 | 说明 |
|---|---|---|
| source_id | UUID | |
| url | string | |
| title | string | |
| source_type | `official_jd / career_site / tech_doc / experience / unknown` | |
| reliability | `high / medium / low` | |
| fetched_at | timestamp | |
| summary | string | 抓取内容摘要 |

### 5.5 Memory（**响应视图**；存储表见 [memories.md](../model-design/data-models/memories.md)）

> **决策 5/20**：memories 表只存 4 类非敏感（sensitive 不再作为 type 取值）；敏感只入 memory_candidates 表。架构层 §5.5 同步：`type` 为 4 值、`status` 为 `active/closed`（删除走 DELETE 真删行）。

| 字段 | 类型 | 说明 |
|---|---|---|
| memory_id | UUID | |
| type | `profile_fact / stable_preference / execution_pattern / session_temp` | 4 值（敏感走 candidates） |
| content | object | content_json 投影 |
| sensitivity | `none` | 恒为 none（保留字段兼容旧客户端；新写入不再允许 'sensitive'） |
| confidence | float (0-1) | |
| status | `active / closed` | 用户主动切换 |
| source | `user / agent_proposal / agent_observed` | |
| expires_at | timestamp? | 临时记忆过期时间 |
| last_used_at | timestamp? | |
| embedding | vector(1024) | （DB 内部，不对外返回） |

### 5.6 AgentRun

> `intent` 字段以 LLM intent_router 的判别结果为准（即服务端不直接信任前端 `hint_intent`，详见 [agent-runs.md](../model-design/api-spec/agent-runs.md) 决策 1）。

| 字段 | 类型 | 说明 |
|---|---|---|
| run_id | UUID | |
| user_id | UUID | |
| intent | IntentType | LLM 判别结果 |
| status | `pending / running / completed / failed / degraded / cancelled` | |
| prompt_version | string | Prompt 模板版本 |
| model_name | string | 使用的模型 |
| tool_calls_count | int | 工具调用总次数 |
| token_input / token_output | int | |
| cost_cny | float | |
| latency_ms | int | 端到端耗时 |
| fallback_reason | string? | 降级原因 |
| risk_category | `mental_health / legal / financial / self_harm / other`? | safe_response 触发时填（**新增**，模块 6 缺口修复） |
| steps | list[AgentStep] | （详情接口返回） |

### 5.7 AgentStep

| 字段 | 类型 | 说明 |
|---|---|---|
| step_id | UUID | |
| run_id | UUID | |
| node_name | string | risk_gate/intent_router/career_planning_agent/... |
| node_type | `rule / llm_single / agent / program / transaction` | |
| input_hash | string | 输入摘要哈希 |
| output_json | json | 结构化输出 |
| tool_calls | list[ToolCall] | 工具调用（仅 Agent 节点有） |
| latency_ms | int | |
| status | `success / fallback / error` | |
| error | string? | |

---

## 6. 状态机

### 6.1 TaskStatus

```
pending → in_progress → completed
   │          │
   │          └→ abandoned（必填 reason）
   │
   └→ abandoned（必填 reason）
   └→ expired（次日未完成自动标记）
```

### 6.2 PlanStatus（**决策 2**：以施工层 4 值为基础 + 新增 adopted）

```
pending → active（persist commit）
            │
            ├→ adopted（任一 task 进入 in_progress 时由 task 状态机副作用触发）
            │      │
            │      └→ completed（review 提交且所有 task 完成时同步转移）
            │
            ├→ completed（同样允许 active 直接 completed，无 task 被用户启动但用户主动结束）
            │
            └→ archived（90 天归档 cron OR 用户主动归档）
pending → archived（未启动 plan 取消）
adopted / active / completed → archived（历史归档）
```

详细合法/非法转移矩阵见 [model-design/state-machines/plan-status.mmd](../model-design/state-machines/plan-status.mmd)。

### 6.3 MemoryStatus（**决策 5/20**：memories 表只 active/closed；候选池单独走 candidates 状态机）

```
memories:        active ⇄ closed（用户主动切换；删除走 DELETE 真删行）

memory_candidates（敏感候选池）:
    pending（待用户确认，7 天过期）→ confirmed → 迁入 memories 表（status=active）
                                → rejected（终态）
                                → expired（cron 清理）
```

详细 spec 见 [memories.md](../model-design/data-models/memories.md) + [memory_candidates.md](../model-design/data-models/memory_candidates.md)。

### 6.4 AgentRunStatus

```
pending → running → completed
   │          │
   │          ├→ degraded（降级完成，带 fallback_reason）
   │          ├→ failed（不可恢复失败）
   │          └→ cancelled（用户取消）
   └→ cancelled（用户取消）
```

---

## 7. SSE 事件协议

### 7.1 传输
- `Content-Type: text/event-stream`
- 事件 JSON：`{"event": "...", "data": {...}, "id": "..."}`
- 心跳：每 15s 一次 `:ping`

### 7.2 事件类型（**决策 6**：本表为单一事实源；与 [model-design/api-spec/agent-runs.md](../model-design/api-spec/agent-runs.md) SSE 章节一致）

| event | 触发时机 | data 关键字段 |
|---|---|---|
| `run.created` | Run 创建 | run_id, intent |
| `node.started` | 节点开始 | node_name |
| `node.completed` | 节点完成 | node_name, latency_ms, status |
| `tool.called` | 工具调用 | tool_name, round |
| `tool.returned` | 工具返回 | tool_name, latency_ms |
| `companion.message` | 中间陪伴提示（拼写以本表为准，不再用 `companions.message`） | message（如"正在结合你昨天的复盘..."） |
| `clarification.requested` | intent_router 缺槽 → clarification 节点输出 | questions / slot_names / hint_options（决策 9） |
| `progress` | 节点级摘要聚合事件（订阅此单一事件即可得到所有节点进度） | step / dim_1 / status / ... |
| `plan.ready` | plan 持久化完成 | run_id, plan_id, tasks |
| `degraded` | 降级路径（fallback_reason 命名见 errors.md） | fallback_reason |
| `run.completed` | Run 完成 | run_id, status, plan_id |
| `run.failed` | Run 失败 | run_id, code, message |

> 前端最小订阅集：`progress` + `plan.ready` + `degraded` + `run.failed` + `run.completed`；首次建档场景需额外订阅 `clarification.requested`。

### 7.3 重连
- 客户端用 `Last-Event-Id` 重连
- 服务端从该 id 之后继续推送
- MVP 不保证逐 Token 事件重放

---

## 8. Tool Calling 协议

### 8.1 ToolSpec

```python
{
  "name": "web_search",
  "description": "搜索招聘/JD/政策动态",
  "input_schema": {
    "type": "object",
    "properties": {
      "query": {"type": "string"},
      "top_k": {"type": "integer", "default": 5}
    },
    "required": ["query"]
  }
}
```

### 8.2 ToolCall（Trace 内）

| 字段 | 类型 |
|---|---|
| call_id | UUID |
| tool_name | string |
| args_hash | string |
| result_hash | string |
| latency_ms | int |
| status | `success / timeout / error` |

### 8.3 Agent 工具调用约束
- 只能调用 ToolRegistry 中已注册 Tool
- 单轮 ≤4 次，总计 ≤8 次
- 工具结果必须脱敏 + 限长后入 context
- 工具不得在执行函数中创建 DB 连接

---

## 9. 数据库表映射

### 9.1 业务核心表
- `users`
- `user_profiles`（带 `goal_type` 索引）
- `plans`（带 `version` 乐观锁）
- `tasks`（带复合索引 `user_id, plan_id, status`）
- `reviews`
- `search_sources`
- `experience_atoms`（带 `goal_type` 索引 + `embedding vector(1024)`）

### 9.2 记忆表
- `memories`（带 `embedding vector(1024)` + 复合索引 `user_id, type, is_active`）
- `memory_candidates`

### 9.3 Agent Harness 表
- `agent_runs`（带 `prompt_version, model_name, cost_cny` 索引）
- `agent_steps`（带 `run_id` 索引）
- `tool_calls`（带 `step_id` 索引）

### 9.4 评测表
- `eval_datasets`
- `eval_cases`
- `eval_experiments`
- `eval_case_results`

### 9.5 索引策略
- 业务查询的常用过滤字段建复合索引
- pgvector 用 `ivfflat` 索引，`vector_cosine_ops`
- Trace 表按 run_id 关联，不做复杂查询

---

## 10. 版本兼容

### 10.1 兼容变更（minor）
- 响应新增字段（客户端忽略）
- 新增枚举值（不破坏旧客户端）
- 新增端点

### 10.2 破坏性变更（major）
- 字段改名/删除
- 类型变化
- 枚举值删除
- URL 路径变更
- 需要新版本路径 `/api/v2`

### 10.3 契约测试
- OpenAPI snapshot 入 Git
- Pydantic 模型生成 OpenAPI，与 snapshot 对比
- 任何破坏性变更必须更新 snapshot 并 review

---

## 11. Mock 与测试数据规范

### 11.1 Mock 数据
- 所有 Mock 数据必须带 `data_origin: "mock"` 字段
- 不得混入真实统计
- 测试数据库与开发数据库严格隔离

### 11.2 契约测试
- 每 Provider 一个 Mock 实现
- Mock 和真实实现必须通过同一 ToolSpec 测试集合
- CI 中运行 OpenAPI snapshot 对比

---

## 12. 端到端 Payload 示例（来自 PRD 附录）

### 12.1 示例 A：AI 求职规划（命中场景）

**POST /api/v1/agent-runs**

> 决策 1：Request 字段为 `message + goal_type_override + hint_intent(可选)`；`intent` 由 LLM intent_router 推断后存入 agent_runs。

```http
POST /api/v1/agent-runs
Idempotency-Key: uuid-001
Content-Type: application/json

{"message":"帮我制定秋招准备计划，我想进央国企做后端"}
```

**Response 202**
```json
{
  "data": {"run_id": "uuid-run-001", "status": "pending", "events_url": "/api/v1/agent-runs/uuid-run-001/events"},
  "meta": {"request_id": "...", "version": "1.0.0"}
}
```

**SSE 事件流**（决策 6：事件名以本表为准；最小订阅集 `progress`+`plan.ready`+`run.completed`）：
```
event: run.created        data: {"run_id":"uuid-run-001","intent":"create_plan"}
event: node.completed     data: {"node_name":"risk_gate","latency_ms":5,"status":"ok"}
event: node.completed     data: {"node_name":"intent_router","latency_ms":1200,"status":"ok"}
event: companion.message  data: {"message":"已诊断：AI 后端央国企方向，信息足够，开始规划..."}
event: tool.called        data: {"tool_name":"rag_retrieve","round":1}
event: tool.called        data: {"tool_name":"web_search","round":1}
event: progress           data: {"step":"career_planning_agent","tools_used":2}
event: node.completed     data: {"node_name":"career_planning_agent","latency_ms":8500,"status":"ok"}
event: progress           data: {"step":"rule_validator","dim_1":"pass","dim_2":"pass","dim_3":"pass","dim_5":"pass"}
event: node.completed     data: {"node_name":"rule_validator","latency_ms":12,"status":"ok"}
event: progress           data: {"step":"quality_reviewer","dim_4":"pass"}
event: node.completed     data: {"node_name":"quality_reviewer","latency_ms":1100,"status":"ok"}
event: plan.ready         data: {"run_id":"uuid-run-001","plan_id":"uuid-plan-001","tasks":[...]}
event: run.completed      data: {"run_id":"uuid-run-001","status":"completed","plan_id":"uuid-plan-001"}
```

**GET /api/v1/plans/{plan_id}**
```json
{
  "plan_id": "uuid-plan-001",
  "horizon": "overall",
  "summary": "3 个月完成项目深度包装 + 八股巩固 + 简历优化 + 提前批投递",
  "weekly_focus": {"focus": "把电商课设拆成可讲 30 分钟的深度项目", "priority": "high"},
  "today_tasks": [
    {
      "title": "整理电商课设 3 个技术难点 + 各自解决方案",
      "starter_action": "打开你电商课设代码库 + 新建一个 technical-notes.md",
      "duration_minutes": 120,
      "deliverable": "一个 Markdown 文件，含 3 个技术难点和解决方案",
      "priority": 1
    },
    {
      "title": "写下 JVM 内存区域结构图 + 3 句话解释每块",
      "starter_action": "新建 draw.md，画一张内存结构图",
      "duration_minutes": 60,
      "deliverable": "图 + 9 句话解释",
      "priority": 2
    },
    {
      "title": "查工行科技菁英 JD，标记技术栈缺口",
      "starter_action": "打开工行招聘官网",
      "duration_minutes": 30,
      "deliverable": "一个缺口清单",
      "priority": 3
    }
  ],
  "companion_message": "你大四还有 3 个月，时间够用。先把课设吃透——这是央企技术面最容易出彩的地方。今天先整理技术难点，我把它放第一位了。",
  "sources": [
    {"title": "工商银行 2026 科技菁英", "url": "...", "source_type": "official_jd", "reliability": "high"}
  ],
  "status": "active",
  "version": 1
}
```

### 12.2 示例 B：replan（规则驱动）

**POST /api/v1/reviews**
```json
{
  "completion": "1/2",
  "mood": 2,
  "blocker": "下班太累不想做需要动脑的任务",
  "idempotency_key": "uuid-rev-001"
}
```

**次日 GET /api/v1/tasks/today** → 返回减量任务
```json
{
  "data": [
    {
      "title": "打开昨晚没做的申论素材，只读 3 分钟",
      "starter_action": "打开收藏夹申论素材文件夹",
      "duration_minutes": 5,
      "priority": 1
    },
    {
      "title": "行测言语理解 5 题",
      "starter_action": "打开题库言语理解第一节",
      "duration_minutes": 30,
      "priority": 2
    }
  ],
  "meta": {}
}
```

**GET /api/v1/plans/active** 含 adjustment_reason：
```json
{
  "adjustment_reason": "昨天太累没做完很正常，今天任务给你减量了。规则：连续 1 天放弃 → starter_action 拆细 + 量减半。"
}
```

### 12.3 示例 C：通用场景兜底（goal_type=other）

**POST /api/v1/agent-runs**
```http
POST /api/v1/agent-runs
Idempotency-Key: uuid-003

{"message":"我想学吉他，三个月学会弹唱 5 首歌","goal_type_override":"other"}
```

**Response**（companion_message 显式告知）
```json
{
  "companion_message": "⚠️ 这个目标我们还没积累专门的经验库，以下是通用建议，部分细节可能不够专业。",
  "weekly_focus": {"focus": "买琴 + 调音 + 基础持琴姿势"},
  "today_tasks": [
    {
      "title": "在 B 站搜\"零基础吉他第一课\"，跟着看完并调好你的琴",
      "starter_action": "打开 B 站搜索框输入\"零基础吉他第一课\"",
      "duration_minutes": 45,
      "deliverable": "琴已调好 + 跟着视频弹响第一个和弦"
    }
  ],
  "sources": []
}
```

### 12.4 示例 D：High Risk 分流

**POST /api/v1/agent-runs**
```http
POST /api/v1/agent-runs
Idempotency-Key: uuid-004

{"message":"我太累了，有时候不想活了"}
```

**Response 200 + degraded**（决策 6/risk 透出：模块 6 修复）
```json
{
  "data": {
    "run_id": "uuid-run-002",
    "status": "degraded",
    "fallback_reason": "high_risk_triggered",
    "risk_category": "self_harm",
    "hotline": "12356 全国心理援助热线",
    "additional_resources": ["https://www.12356.cn/"],
    "companion_message": "我能感受到你现在很难受。你现在不是一个人，我们一起找能帮到你的人。请立即拨打全国心理援助热线 12356，或联系身边信任的人。如果你觉得自己有立即的危险，请拨打 120 或 110。",
    "plan": null
  }
}
```

**AgentRun 记录**：不进入记忆候选；risk_category 写入 trace；后台脱敏记录安全分流事件。

---

## 13. 完成定义（DoD）

每个 API 端点完成需满足：
1. OpenAPI 中定义完整
2. Pydantic 请求 / 响应 Schema 已实现
3. 成功响应过单测
4. 校验错误（VALIDATION_*）过单测
5. 状态机违规（STATE_*）过单测
6. 幂等性过单测
7. 权限校验（AUTH_*）过单测

---

## 附：参考

- 同伴 API v1.0 原文——本契约 90% 直接采纳
- 4 个端到端 Payload 示例来自 PRD v2.0 附录
