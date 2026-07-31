# Stage 2：Mock Agent 纵切

## 目标

不接真实模型，用 Mock Provider 跑通完整链路：创建 Run → SSE → 保存 Plan/Task → 查询结果。

## 实现范围

### 表

- plans
- tasks
- agent_runs
- agent_steps
- tool_calls
- agent_events
- companion_messages

### API

- POST `/api/v1/agent-runs`
- GET `/api/v1/agent-runs/{id}`
- GET `/api/v1/agent-runs/{id}/events`
- POST `/api/v1/agent-runs/{id}/cancel`
- GET `/api/v1/plans/active`
- GET `/api/v1/tasks`

### Agent

使用 Mock Provider 实现核心 Graph：

```text
risk_gate → intent_router → context_builder
→ career_planning_agent → rule_validator
→ revise_or_fallback → companion_response → persist
```

缺画像字段时走 clarification；风险命中时走 safe_response。

## SSE 规则

- 每个事件先插入 `agent_events`；
- `sequence` 在 run 内单调递增；
- `Last-Event-ID` 从下一 sequence 继续；
- 终态一定产生 `run.completed`、`run.failed`、`run.degraded` 或 `run.cancelled`。

## 单 Worker 约束

执行任务可以使用进程内 `asyncio.Task` Registry，但必须：

- 不声称具备多 Worker 可靠性；
- 应用启动时把超时的 pending/running run 标记为 failed；
- 取消接口可取消本进程内 Task，并持久化最终状态。

## 验收

- Mock happy path 产生 1 个计划和 1~3 个任务；
- SSE 事件顺序稳定；
- 断线后用 Last-Event-ID 续传；
- 重复 Idempotency-Key 不重复创建 Run；
- 同用户并发创建第二个 Run 返回 409；
- Mock invalid schema 触发一次 repair；
- Mock timeout 收敛为 failed 或 degraded。
