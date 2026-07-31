# 端到端运行流程

## 1. 首次进入

```text
POST /auth/guest → JWT
GET /me → profile_complete=false
PUT /profile → 建档完成
```

## 2. 创建计划 Run

```text
POST /agent-runs
  → AgentRunService 校验 JWT、Profile、幂等、活动 Run
  → insert agent_runs(pending)
  → AgentRunExecutor submit
  → 202 run_id + events_url
```

## 3. SSE 与执行

```text
GET /agent-runs/{id}/events
  → 回放 agent_events(sequence > Last-Event-ID)
  → 等待新事件

Executor:
  pending→running
  → risk_gate
  → intent_router
  → clarification OR context_builder
  → career_planning_agent
  → rule_validator
  → revise_or_fallback
  → companion_response
  → persist
  → completed/degraded/failed/cancelled
```

每个节点：

1. 写 agent_steps running；
2. 写 node.started event；
3. 执行；
4. 更新 step；
5. 写 node.completed 或 run.failed event。

## 4. Persist 事务

```text
create plan(generated)
+ create 1~3 tasks
+ create companion_message
+ link search_sources
+ archive replaced plan if replan
+ set run.final_plan_id and terminal status
+ write plan.ready and terminal event
COMMIT
```

事件与业务终态必须在同一事务或通过可靠 outbox 语义保持一致。MVP 可把 agent_events 直接作为轻量 outbox。

## 5. 任务执行

- GET /tasks?date=today；
- PATCH pending→in_progress，同时 plan generated→active；
- PATCH in_progress→completed；
- 全部完成时 plan→completed；
- 放弃记录原因；
- 过期由定时任务处理。

## 6. 复盘和重规划

```text
POST /reviews
  → 读取任务事实
  → 计算完成/放弃数量
  → 规则判断 suggested_replan
  → 保存 review + companion

POST /reviews/{id}/accept-replan
  → create Agent Run(replan, source_plan_id)
  → 新计划成功后归档旧计划
```

## 7. 记忆和证据

Stage 4：context_builder 按优先级读 active memories、experience atoms、search sources。敏感候选由用户确认后才进入 memories。

## 8. 故障收敛

| 故障 | 结果 |
|---|---|
| Profile 缺失 | clarification + degraded |
| LLM 格式错误 | 修复一次，仍失败模板 degraded |
| Provider 超时 | Provider 统一异常，按策略 degraded/failed |
| Run 截止时间 | failed + AGENT_DEADLINE_EXCEEDED |
| 用户取消 | cancelled |
| 进程重启 | stale pending/running → failed(process_interrupted) |
| SSE 断线 | 依据 agent_events 重放 |

## 9. 权威恢复

前端刷新后不依赖内存：

- GET /me；
- GET /agent-runs/{id}；
- GET /plans/active；
- GET /tasks。

SSE 只负责实时体验，不是唯一事实源。
