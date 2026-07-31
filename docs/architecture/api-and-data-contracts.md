# API 与数据契约 v2.0

## 1. 通用规范

- Base URL：`/api/v1`
- JSON：UTF-8，snake_case
- 时间：ISO 8601 UTC
- ID：标准 UUID 字符串
- 鉴权：`Authorization: Bearer <jwt>`
- Request Schema：`extra="forbid"`
- 写请求支持 `Idempotency-Key` 或 version 乐观锁

成功响应直接返回资源，不额外套 `{code,data}`。错误统一：

```json
{
  "error": {
    "code": "STATE_VERSION_CONFLICT",
    "message": "resource version changed",
    "request_id": "...",
    "details": {}
  }
}
```

## 2. 身份和作用域

- 请求体和 Query 不接收 user_id；
- user_id 从 JWT claim 获取；
- Repository 查询必须包含 user_id 或通过归属关系校验；
- `/dev/*` 需要 `role=dev`。

## 3. API 总览

| 方法 | 路径 | 作用 |
|---|---|---|
| POST | `/auth/guest` | 创建或复用 Guest 用户并签发 JWT |
| GET | `/me` | 当前用户首页摘要 |
| GET/PUT/PATCH | `/profile` | 用户画像 |
| POST | `/agent-runs` | 创建规划或重规划 Run |
| GET | `/agent-runs/{id}` | Run 权威状态 |
| GET | `/agent-runs/{id}/events` | SSE 事件 |
| POST | `/agent-runs/{id}/cancel` | 取消 Run |
| GET | `/plans` | 计划历史 |
| GET | `/plans/active` | 当前计划 |
| GET | `/plans/{id}` | 计划详情 |
| GET | `/tasks` | 日期/计划/状态过滤任务 |
| PATCH | `/tasks/{id}` | 更新任务状态 |
| POST/GET | `/reviews` | 提交/查询复盘 |
| POST | `/reviews/{id}/accept-replan` | 接受重规划建议 |
| GET | `/memories` | 查询记忆 |
| PATCH/DELETE | `/memories/{id}` | 关闭、恢复或删除记忆 |
| GET | `/memory-candidates` | 查询记忆候选 |
| POST | `/memory-candidates/{id}/confirm` | 确认候选 |
| POST | `/memory-candidates/{id}/reject` | 拒绝候选 |
| GET | `/dev/runs` | Trace 列表 |
| GET | `/dev/runs/{id}` | Trace 详情 |
| POST | `/dev/runs/{id}/replay` | 重放 |
| GET/POST | `/dev/evals/*` | 评测 |

## 4. 核心枚举

### GoalType

`ai_backend / agent_app / backend_java / data_engineer / fullstack / other`

### CareerStage

`exploring / preparing / applying / interviewing`

### RunStatus

`pending / running / completed / degraded / failed / cancelled`

### PlanStatus

`generated / active / completed / archived`

### TaskStatus

`pending / in_progress / completed / abandoned / expired`

## 5. Profile

```json
{
  "goal_type": "agent_app",
  "stage": "preparing",
  "time_budget_minutes": 120,
  "skill_level": "intermediate",
  "skill_summary": "熟悉 FastAPI 和 RAG",
  "deadline": "2026-10-31",
  "preferences": {"preferred_time_slot": "evening"},
  "version": 2
}
```

## 6. PlanDetail

PlanDetail 是 Service 拼装视图，不等同数据库单表：

```json
{
  "plan_id": "c91f8734-2839-4f55-9db1-1c39b8a410f2",
  "status": "generated",
  "version": 1,
  "summary": "未来一周优先补齐 Agent 项目的可演示闭环",
  "rationale": "基于目标岗位、截止时间和当前能力",
  "adjustment_reason": null,
  "tasks": [],
  "sources": [],
  "companion_message": "先从今天能完成的一步开始。",
  "created_at": "2026-07-31T02:00:00Z"
}
```

## 7. Task

```json
{
  "task_id": "69844cd6-6889-4d57-89b0-5a7ecdbf88cf",
  "plan_id": "c91f8734-2839-4f55-9db1-1c39b8a410f2",
  "title": "补齐 Agent Run Trace",
  "task_type": "project",
  "scheduled_date": "2026-07-31",
  "state": "pending",
  "starter_action": "打开后端项目并新建 trace 表迁移文件",
  "deliverable": "迁移文件和一条 Run Trace 示例",
  "estimated_minutes": 45,
  "actual_minutes": null,
  "version": 1
}
```

## 8. Agent Run Request

```json
{
  "message": "帮我制定未来 5 周的大模型应用开发秋招计划",
  "hint_intent": "create_plan",
  "goal_type_override": null,
  "source_plan_id": null
}
```

服务端注入：user_id、profile、近期任务、复盘、记忆、预算和 deadline。

## 9. SSE 事件

事件统一使用 dot notation：

| event | 含义 |
|---|---|
| `run.created` | Run 被执行器接管 |
| `node.started` | 节点开始 |
| `node.completed` | 节点完成 |
| `tool.called` | Tool 开始 |
| `tool.returned` | Tool 完成 |
| `progress` | 用户可读进度摘要 |
| `clarification.requested` | 需要补充信息 |
| `companion.message` | 陪伴提示 |
| `plan.ready` | 计划持久化完成 |
| `run.degraded` | 使用降级结果 |
| `run.failed` | 执行失败 |
| `run.cancelled` | 用户取消 |
| `run.completed` | 正常完成 |
| `heartbeat` | 保持连接 |

事件 data 必须包含 `run_id` 和 `sequence`。SSE `id` 使用 sequence 字符串。

## 10. 状态转移

### Plan

- 新计划持久化：generated；
- 首个任务开始：generated→active，并写 adopted_at；
- 所有任务完成：active→completed；
- 重规划成功替代或用户归档：generated/active/completed→archived。

### Task

- pending→in_progress；
- in_progress→completed；
- pending/in_progress→abandoned；
- pending→expired。

### Run

- pending→running；
- running→completed/degraded/failed；
- pending/running→cancelled。

## 11. 幂等

- POST agent-runs：`(user_id, idempotency_key)` 唯一，重复请求返回原 Run；
- POST reviews：同上；
- accept-replan：同一 review 只能成功一次；
- PATCH 资源：version 乐观锁，不额外要求 Idempotency-Key。

## 12. 分页

Cursor 使用服务端签名的 opaque token，不向客户端暴露 SQL offset。默认 20，最大 100。

## 13. 错误码

| HTTP | code | 场景 |
|---:|---|---|
| 401 | AUTH_INVALID_TOKEN | JWT 无效 |
| 403 | AUTH_FORBIDDEN | 无资源或 dev 权限 |
| 404 | NOT_FOUND_* | 资源不存在 |
| 409 | STATE_VERSION_CONFLICT | 乐观锁冲突 |
| 409 | STATE_INVALID_TRANSITION | 非法状态转移 |
| 409 | STATE_RUN_ALREADY_ACTIVE | 用户已有活动 Run |
| 422 | VALIDATION_* | 请求或结构化输出不合法 |
| 429 | RATE_LIMITED | 限流 |
| 503 | PROVIDER_UNAVAILABLE | 外部服务不可用 |

详细端点以 [`model-design/api-spec`](../model-design/api-spec/README.md) 为准。
