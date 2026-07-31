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
| hint_intent | create_plan/replan/query_plan/null | 只是提示，服务端仍校验 |
| goal_type_override | GoalType/null | 本轮临时覆盖 |
| source_plan_id | UUID/null | replan 时可填，必须属于当前用户 |

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

返回权威状态：

```json
{
  "run_id": "...",
  "status": "completed",
  "resolved_intent": "create_plan",
  "final_plan_id": "...",
  "fallback_reason": null,
  "risk_category": null,
  "total_tokens_in": 1200,
  "total_tokens_out": 530,
  "total_cost_cny": "0.013200",
  "total_latency_ms": 8120,
  "created_at": "...",
  "finished_at": "..."
}
```

普通用户不返回完整 prompt、node trace 和 Tool 参数。

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

### 重连

- 无 Last-Event-ID：从 sequence 1 开始；
- 有 Last-Event-ID：从 `last + 1` 开始；
- 先回放数据库历史，再等待新事件；
- Run 已终态且历史发送完后关闭连接。

## POST /api/v1/agent-runs/{run_id}/cancel

取消 pending/running Run。需要 `Idempotency-Key`。

```json
{"reason":"user_abort"}
```

成功返回：

```json
{"run_id":"...","status":"cancelled"}
```

终态 Run 再取消返回 409。

## 主要错误

| HTTP | code |
|---:|---|
| 404 | NOT_FOUND_RUN |
| 409 | STATE_RUN_ALREADY_ACTIVE |
| 409 | STATE_RUN_ALREADY_FINISHED |
| 422 | VALIDATION_RUN_INVALID |
| 429 | RATE_LIMITED |
