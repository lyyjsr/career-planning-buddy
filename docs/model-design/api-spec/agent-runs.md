# Agent Run API

## POST /api/v1/agent-runs

创建规划或重规划 Run。需要 JWT 与 `Idempotency-Key`。

### Request

```json
{
  "message": "帮我制定未来五周的大模型应用开发秋招计划",
  "hint_intent": "create_plan",
  "goal_type_override": null,
  "source_plan_id": null
}
```

字段：

| 字段 | 类型 | 约束 |
|---|---|---|
| message | string | 1~2000 |
| hint_intent | create_plan/replan/null | 弱提示；不能覆盖消息语义、来源计划或服务端 Review 决策 |
| goal_type_override | GoalType/null | 仅用户明确表达目标变化时使用 |
| source_plan_id | UUID/null | replan 可显式指定；省略时优先当前 generated/active，否则最近 completed Plan |

已有计划查询使用 `/plans` 与 `/tasks`，不通过 Agent Run。

意图路由不依赖 LLM。只有消息包含受支持的规划语义并满足来源约束时才进入生成 Graph；仅有 `hint_intent`、问候或含糊文本会返回 `intent_uncertain`，查询类文本返回 `unsupported_intent`。这两类结果都不会调用规划模型。

### 创建前校验

1. JWT 用户有效；
2. Idempotency-Key 合法；
3. source_plan_id 提供时必须属于当前用户；可作为来源的状态为 generated/active/completed，archived 仅允许显式指定；显式 hint=replan 但没有可用来源计划时返回 422；
4. 同用户没有 pending/running Run；
5. 生成并冻结 `graph_version/config_snapshot_json`；
6. 创建 `agent_runs(pending)` 后提交执行器。

### Response 202

```json
{
  "run_id": "f880d3e2-2de7-48aa-b123-068d1d6f5e69",
  "status": "pending",
  "events_url": "/api/v1/agent-runs/f880d3e2-2de7-48aa-b123-068d1d6f5e69/events"
}
```

重复 `(user_id, Idempotency-Key)` 返回原 Run；同用户已有活动 Run 返回 409。

## GET /api/v1/agent-runs/{run_id}

返回权威状态。普通用户只看到用户可理解的终态结果，不返回完整 Prompt、Tool 参数和内部 Trace。

### Plan 结果

```json
{
  "run_id": "...",
  "status": "completed",
  "resolved_intent": "create_plan",
  "replan_mode": "initial",
  "result_kind": "plan",
  "result": {
    "plan_id": "...",
    "status": "generated",
    "plan_date": "2026-07-31",
    "horizon_end": "2026-09-03",
    "summary": "今天先补齐可演示闭环",
    "task_count": 7
  },
  "final_plan_id": "...",
  "fallback_reason": null,
  "error_code": null,
  "risk_category": null,
  "total_tokens_in": 1200,
  "total_tokens_out": 530,
  "total_cost_cny": "0.013200",
  "total_latency_ms": 8120,
  "created_at": "...",
  "finished_at": "..."
}
```

### Clarification 结果

```json
{
  "run_id": "...",
  "status": "degraded",
  "result_kind": "clarification",
  "result": {
    "questions": ["你目前处于哪个求职阶段？"],
    "slot_names": ["stage"],
    "hint_options": {"stage": ["exploring", "preparing", "applying", "interviewing"]},
    "reason": "profile_incomplete"
  },
  "final_plan_id": null,
  "fallback_reason": "profile_incomplete"
}
```

`reason` 的稳定取值：

- `profile_incomplete`：意图已确定，但生成所需 Profile 字段缺失；
- `intent_uncertain`：消息语义不足、hint 冲突或重规划缺少来源；
- `unsupported_intent`：明确属于已有计划/任务查询等非生成请求。

### Safe Response 结果

```json
{
  "run_id": "...",
  "status": "degraded",
  "result_kind": "safe_response",
  "result": {
    "message": "...",
    "resource_ids": ["default-local-resource"],
    "disclaimer": "..."
  },
  "final_plan_id": null,
  "fallback_reason": "high_risk_routed"
}
```

`start-next-plan` 创建的 Run 由服务端额外注入 `source_review_id` 和 `replan_mode=continue/adjust`，客户端不能伪造。

failed/cancelled 时 `result_kind/result/final_plan_id` 均为空，并返回稳定 `error_code`；`fallback_reason` 仅用于 degraded。

## GET /api/v1/agent-runs/{run_id}/events

SSE，支持 `Last-Event-ID`。SSE `id` 等于 `agent_events.sequence`。

事件：

- run.created
- node.started
- node.completed
- tool.called
- tool.returned
- progress
- clarification.requested
- companion.message
- plan.ready
- run.degraded
- run.failed
- run.cancelled
- run.completed
- heartbeat

示例：

```text
id: 7
event: progress
data: {"run_id":"...","sequence":7,"stage":"validating","message":"正在检查任务时长"}
```

### 事件规则

- 除 heartbeat 外，事件先持久化再发送；
- heartbeat 不占 sequence；
- terminal event 是最后一个持久事件；
- 同一 Run 只允许一个 terminal event；
- `plan.ready` 只在 Plan 事务成功后出现；
- `run.degraded` payload 必含 result_kind 与 fallback_reason。

### 重连

- 无 Last-Event-ID：从 sequence 1 开始；
- 有 Last-Event-ID：从 `last + 1` 开始；
- 先回放数据库历史，再等待新事件；
- Run 已终态且历史发送完后关闭连接；
- 前端仍应调用 GET Run 获取权威结果。

## POST /api/v1/agent-runs/{run_id}/cancel

取消 pending/running Run。需要 `Idempotency-Key`。

```json
{"reason":"user_abort"}
```

服务端先写 `cancel_requested_at`，再尝试取消本进程 Task。接口只表示“取消请求已接受”，不能提前声称 Run 已进入 cancelled。

Response 202：

```json
{
  "run_id": "...",
  "status": "running",
  "cancel_requested": true
}
```

客户端随后通过 GET Run/SSE 等待权威 `cancelled` 终态。重复请求取消中的 Run 返回相同语义；已经 cancelled 可返回 200 当前结果；completed/degraded/failed 再取消返回 409。取消请求最终必须由 Finalizer 写 `run.cancelled`，不能只更新内存 Task。

## 主要错误

| HTTP | code |
|---:|---|
| 404 | NOT_FOUND_RUN |
| 404 | NOT_FOUND_SOURCE_PLAN |
| 409 | STATE_RUN_ALREADY_ACTIVE |
| 409 | STATE_RUN_ALREADY_FINISHED |
| 422 | VALIDATION_RUN_INVALID |
| 422 | VALIDATION_REPLAN_SOURCE_UNAVAILABLE |
| 429 | RATE_LIMITED |
