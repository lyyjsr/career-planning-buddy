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
| 当前用户 | 使用 `/me` 路径，不信任前端传入 user_id |

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

| 路径 | 方法 | 用途 |
|---|---|---|
| `/api/v1/auth/login` | POST | 登录获取 JWT |
| `/api/v1/me/profile` | GET/PUT | 读取/更新画像 |
| `/api/v1/agent-runs` | POST | 创建规划运行（异步 202） |
| `/api/v1/agent-runs/{run_id}` | GET | 查询运行状态 |
| `/api/v1/agent-runs/{run_id}/cancel` | POST | 取消运行 |
| `/api/v1/agent-runs/{run_id}/events` | GET（SSE） | 订阅运行事件流 |
| `/api/v1/me/plans/active` | GET | 当前活跃计划 |
| `/api/v1/plans/{plan_id}` | GET | 计划详情 |
| `/api/v1/plans/{plan_id}/sources` | GET | 计划关联来源 |
| `/api/v1/me/tasks/today` | GET | 今日任务 |
| `/api/v1/me/tasks` | GET | 任务列表（带筛选） |
| `/api/v1/tasks/{task_id}/transitions` | POST | 任务状态转换 |
| `/api/v1/me/reviews` | POST/GET | 提交/查询复盘 |
| `/api/v1/me/memories` | GET | 记忆列表 |
| `/api/v1/me/memories/{memory_id}` | DELETE | 删除记忆 |
| `/api/v1/me/memories/{memory_id}` | PATCH | 关闭/确认记忆 |
| `/api/v1/me/memory-candidates/{id}/confirm` | POST | 确认敏感记忆候选 |

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

### 5.1 UserProfile

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| user_id | UUID | ✅ | |
| goal_type | GoalType 枚举 | ✅ | `ai_backend / data_engineer / agent_app / fullstack / backend_java / other` |
| stage | string | ✅ | 如 "应届大四"/"研二" |
| available_minutes_per_day | int (10-720) | ✅ | 每日可用时间 |
| skills | list[SkillItem] | ❌ | 已有技能 |
| target_companies | list[string] | ❌ | 目标公司 |
| deadline | date | ❌ | 截止日期 |
| preferences | ProfilePreferences | ❌ | 偏好 |
| version | int | ✅ | 乐观锁 |
| updated_at | timestamp | ✅ | |

### 5.2 PlanDetail

| 字段 | 类型 | 说明 |
|---|---|---|
| plan_id | UUID | |
| user_id | UUID | |
| horizon | `overall / weekly / today` | |
| summary | string | 整体方向描述 |
| milestones | list[Milestone] | 整体方向用 |
| weekly_focus | WeeklyFocus | 本周重点 |
| today_tasks | list[PlanTask] | 今日任务 |
| adjustment_reason | string? | replan 时的调整说明 |
| companion_message | string? | 陪伴反馈话术 |
| sources | list[SourceRef] | 关联来源 |
| status | PlanStatus | draft/generated/adopted/in_progress/completed/abandoned |
| version | int | 乐观锁 |
| created_at / updated_at | timestamp | |

### 5.3 PlanTask

| 字段 | 类型 | 说明 |
|---|---|---|
| task_id | UUID | |
| title | string | 任务名 |
| starter_action | string | **最小启动动作**（必须可启动） |
| duration_minutes | int | 预计耗时 |
| deliverable | string | **完成标准**（可观测产物） |
| priority | int | 1-3 |
| status | TaskStatus | pending/in_progress/completed/abandoned/expired |
| started_at / completed_at | timestamp? | |
| abandon_reason_code | string? | |
| abandon_reason_text | string? | |

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

### 5.5 Memory

| 字段 | 类型 | 说明 |
|---|---|---|
| memory_id | UUID | |
| type | `profile_fact / stable_preference / execution_pattern / sensitive / temporary` | |
| content | string | |
| sensitivity | `normal / sensitive` | |
| confidence | float (0-1) | |
| status | `candidate / confirmed / closed / deleted` | |
| is_active | bool | 是否进入上下文 |
| expires_at | timestamp? | 临时记忆过期时间 |
| embedding | vector(1024) | （DB 内部，不对外返回） |

### 5.6 AgentRun

| 字段 | 类型 | 说明 |
|---|---|---|
| run_id | UUID | |
| user_id | UUID | |
| intent | IntentType | |
| status | `pending / running / completed / failed / degraded / cancelled` | |
| prompt_version | string | Prompt 模板版本 |
| model_name | string | 使用的模型 |
| tool_calls_count | int | 工具调用总次数 |
| token_input / token_output | int | |
| cost_cny | float | |
| latency_ms | int | 端到端耗时 |
| fallback_reason | string? | 降级原因 |
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

### 6.2 PlanStatus

```
draft → generated → adopted（用户开始任一任务）→ in_progress → completed
                       │
                       └→ abandoned
```

### 6.3 MemoryStatus

```
candidate（敏感待确认）→ confirmed → closed → deleted
                │
                └→ 普通记忆直接 confirmed
```

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

### 7.2 事件类型

| event | 触发时机 | data 关键字段 |
|---|---|---|
| `run.created` | Run 创建 | run_id, intent |
| `node.started` | 节点开始 | node_name |
| `node.completed` | 节点完成 | node_name, latency_ms |
| `tool.called` | 工具调用 | tool_name |
| `tool.returned` | 工具返回 | tool_name, latency_ms |
| ` companions.message` | 中间陪伴提示 | message（如"正在结合你昨天的复盘..."） |
| `run.completed` | Run 完成 | run_id, status, plan_id |
| `run.failed` | Run 失败 | run_id, fallback_reason/error |

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
```json
{
  "intent": "create_plan",
  "user_request": "帮我制定秋招准备计划，我想进央国企做后端",
  "idempotency_key": "uuid-001"
}
```

**Response 202**
```json
{
  "data": {"run_id": "uuid-run-001", "status": "running"},
  "meta": {"request_id": "...", "version": "1.0.0"}
}
```

**SSE 事件流**：
```
event: node.completed   data: {"node_name": "risk_gate", "latency_ms": 5}
event: node.completed   data: {"node_name": "intent_router", "latency_ms": 1200}
event: companions.message data: {"message": " diagnosed: AI 后端央国企方向，信息足够，开始规划..."}
event: tool.called      data: {"tool_name": "rag_retrieve"}
event: tool.called      data: {"tool_name": "web_search"}
event: node.completed   data: {"node_name": "career_planning_agent", "latency_ms": 8500}
event: node.completed   data: {"node_name": "rule_validator", "result": {"5d_pass": [✓,✓,✓,✗,✓]}}
event: node.completed   data: {"node_name": "quality_reviewer", "result": {"rewrite": true}}
event: node.completed   data: {"node_name": "career_planning_agent", "note": "rewrite #1"}
event: run.completed    data: {"run_id": "...", "plan_id": "uuid-plan-001", "cost_cny": 0.12}
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
  "status": "generated",
  "version": 1
}
```

### 12.2 示例 B：replan（规则驱动）

**POST /api/v1/me/reviews**
```json
{
  "completion": "1/2",
  "mood": 2,
  "blocker": "下班太累不想做需要动脑的任务",
  "idempotency_key": "uuid-rev-001"
}
```

**次日 GET /api/v1/me/tasks/today** → 返回减量任务
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

**GET /api/v1/me/plans/active** 含 adjustment_reason：
```json
{
  "adjustment_reason": "昨天太累没做完很正常，今天任务给你减量了。规则：连续 1 天放弃 → starter_action 拆细 + 量减半。"
}
```

### 12.3 示例 C：通用场景兜底（goal_type=other）

**POST /api/v1/agent-runs**
```json
{
  "intent": "create_plan",
  "user_request": "我想学吉他，三个月学会弹唱 5 首歌"
}
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
```json
{"user_request": "我太累了，有时候不想活了"}
```

**Response 200 + fallback**
```json
{
  "data": {
    "run_id": "uuid-run-002",
    "status": "fallback",
    "fallback_reason": "high_risk_triggered",
    "companion_message": "我能感受到你现在很难受。你现在不是一个人，我们一起找能帮到你的人。请立即拨打全国心理援助热线 12356，或联系身边信任的人。如果你觉得自己有立即的危险，请拨打 120 或 110。",
    "plan": null,
    "memory_candidates": null
  }
}
```

**AgentRun 记录**：不进入记忆候选；后台脱敏记录安全分流事件。

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
