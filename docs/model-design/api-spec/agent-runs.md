# agent-runs.md — Agent Run 端点（最复杂）

状态：本轮实现。

> 这是阶段 2 纵切骨架的目标端点。POST 创建 plan_run → 异步执行 → SSE 推进度 → GET 拉最终结果。

## 端点：POST /api/v1/agent-runs

启动一次 plan_run。

**请求头**：
- `Authorization: Bearer <jwt>`（必填）
- `Idempotency-Key: <uuid>`（必填，R-Contract1）

**请求 Schema** `CreateRunRequest`（`app.schemas.agent_run`）：
| 字段 | 类型 | 必填 | 约束 |
|---|---|---|---|
| `message` | `str` | ✅ | min 1, max 2000；用户原始请求 |
| `goal_type_override` | `GoalType \| null` | ❌ | 默认从 profile 读；显式覆盖（如 "今天换后端 Java 规划"） |
| `hint_intent` | `Literal["create_plan","replan","query_plan"] \| null` | ❌ | 前端显式提示意图（如点击"重新规划"按钮时 hint_intent=replan）；服务端仍调 intent_router LLM 验证并允许覆盖（[intent_router.spec.md §0](../agent-nodes/intent_router.spec.md)） |
| `source_plan_id` | `str \| null` | ❌ | hint_intent=replan 时携带上游 plan_id（也可来自 [POST /reviews/{id}/accept-replan](./reviews.md) 注入） |

**成功响应 202** `CreateRunResponse`：
| 字段 | 类型 |
|---|---|
| `run_id` | `str`（UUIDv4） |
| `status` | `Literal["pending"]` |
| `events_url` | `str` |

**示例**：
```http
POST /api/v1/agent-runs
Idempotency-Key: idem-9af2
{"message":"帮我制定 5 周后的 Agent 秋招计划"}
```
```http
POST /api/v1/agent-runs
Idempotency-Key: idem-c2d1
{"message":"昨天太累了，今天调整一下","hint_intent":"replan","source_plan_id":"p-9e2a-..."}
```
```json
{
  "run_id": "r-2a8f-...",
  "status": "pending",
  "events_url": "/api/v1/agent-runs/r-2a8f-.../events"
}
```

**错误**：
| HTTP | code | 触发 |
|---|---|---|
| 401 | AUTH_TOKEN_EXPIRED | —— |
| 422 | VALIDATION_RUN_INVALID | message 空或超长 |
| 409 | STATE_RUN_ALREADY_ACTIVE | 同用户已有 pending/running run |
| 429 | RATE_LIMITED_RUN_PER_USER | 单用户 > 5 runs/min |

## 端点：GET /api/v1/agent-runs/{run_id}/events

SSE 流，推 plan_run 中间态。

**Accept: text/event-stream**

**事件类型**：

事件命名以 [api-and-data-contracts.md §7.2](../../architecture/api-and-data-contracts.md) 为权威源，下列事件为单一事实源；`progress` 作为聚合事件名（前端可仅订阅它得到节点级摘要）。

| event | data | 触发 |
|---|---|---|
| `run.created` | `{"run_id":"r-...", "intent":"create_plan"}` | Worker 接管 run |
| `node.started` | `{"node_name":"intent_router"}` | 节点入口 |
| `node.completed` | `{"node_name":"intent_router","latency_ms":1180,"status":"ok"}` | 每节点完成 |
| `tool.called` | `{"tool_name":"web_search","round":1}` | Agent 工具调用 |
| `tool.returned` | `{"tool_name":"web_search","latency_ms":2840}` | 工具返回 |
| `companion.message` | `{"message":"正在结合你昨天的复盘..."}` | 中间陪伴提示（注：拼写以 `companion.message` 为准，与架构层 §7.2 同步） |
| `progress` | `{"step":"rule_validator","dim_1":"pass","dim_2":"pass"}` | 节点级摘要聚合事件（可订阅单一事件得到所有节点进度） |
| `clarification.requested` | `{"questions":[...],"slot_names":[...],"hint_options":{...}}` | intent_router 缺槽 → clarification 节点输出（首次建档/槽位缺失场景，参 [clarification.spec.md §2](../agent-nodes/clarification.spec.md)） |
| `plan.ready` | `{"plan_id":"p-9e2a","tasks":[...]}` | plan 持久化完成 |
| `degraded` | `{"fallback_reason":"FALLBACK_AGENT_BUDGET_EXCEEDED"}` | 降级路径（fallback_reason 命名见 [errors.md](./errors.md)） |
| `run.failed` | `{"code":"AGENT_RUN_FAILED","message":"..."}` | fail |
| `run.completed` | `{"run_id":"...","status":"completed"}` | END |

**Last-Event-Id** 支持断线重连游标。

> SSE 事件语义以 [api-and-data-contracts.md §7.2](../../architecture/api-and-data-contracts.md) 为权威源；本表与之一致。前端最小订阅集：`progress` + `plan.ready` + `degraded` + `run.failed` + `run.completed`；首次建档时再订阅 `clarification.requested`。

**浏览器示例**：
```js
const es = new EventSource(`/api/v1/agent-runs/${runId}/events`);
es.addEventListener("progress", (e) => setProgress(JSON.parse(e.data)));
es.addEventListener("plan.ready", (e) => setPlan(JSON.parse(e.data)));
es.addEventListener("clarification.requested", (e) => setClarification(JSON.parse(e.data)));
es.addEventListener("run.completed", () => es.close());
es.addEventListener("run.failed", (e) => reportError(JSON.parse(e.data)));
```

## 端点：GET /api/v1/agent-runs/{run_id}

拉取 run 的最终状态（权威，SSE 仅实时增强）。

**成功响应 200** `RunDetailResponse`：
| 字段 | 类型 |
|---|---|
| `run_id` | `str` |
| `status` | `Literal["pending","running","completed","failed","degraded","cancelled"]` |
| `plan` | `Plan \| null` |
| `tasks` | `list[Task]` |
| `companion_message` | `str \| null` |
| `fallback_reason` | `str \| null` |
| `cost_cny` | `float` |
| `risk_category` | `Literal["mental_health","legal","financial","self_harm","other"] \| null` | status 为 `degraded` 且 fallback_reason 表示 high_risk 时由 safe_response 节点透出（[safe_response.spec.md §2](../agent-nodes/safe_response.spec.md)） |
| `hotline` | `str \| null` | risk 风险分支时返回 `"12356 全国心理援助热线"` |
| `additional_resources` | `list[str] \| null` | risk 风险分支时返回 1-2 个权威 URL |
| `trace` | `TraceSummary \| null`（仅 dev 路径返回详尽 trace） |

## 路由层调用关系

```mermaid
sequenceDiagram
    participant U as Browser
    participant API as FastAPI Router
    participant SVC as AgentRunService
    participant G as LangGraph
    participant DB as Postgres
    U->>API: POST /agent-runs
    API->>SVC: create(user_id, request)
    SVC->>DB: insert agent_runs (pending)
    SVC-->>API: run_id
    API-->>U: 202 + run_id
    U->>API: GET /events (SSE)
    API->>SVC: stream(run_id)
    SVC->>G: invoke graph → events
    G->>DB: write each step trace
    G-->>SVC: events
    SVC-->>API: SSE events
    API-->>U: progress / plan_ready / complete
    U->>API: GET /agent-runs/{id}
    API->>SVC: get(run_id)
    SVC->>DB: SELECT plan_response + tasks
    SVC-->>API: RunDetailResponse
    API-->>U: 200 + detail
```

## 端点：POST /api/v1/agent-runs/{run_id}/cancel

用户取消未完成的 run。**必填 Idempotency-Key**。

**请求 Schema** `CancelRunRequest`（可选.body）：
| 字段 | 类型 | 必填 |
|---|---|---|
| `reason` | `Literal["user_abort","timeout","duplicate"] \| null` | ❌ |

**成功响应 200**：
| 字段 | 类型 |
|---|---|
| `run_id` | `str` |
| `status` | `Literal["cancelled"]` |

**错误**：
| HTTP | code | 触发 |
|---|---|---|
| 404 | NOT_FOUND_RUN | —— |
| 409 | STATE_RUN_ALREADY_FINISHED | run 已进入终态（completed/failed/degraded/cancelled），见 [run-status.mmd 非法转移](../state-machines/run-status.mmd) |

## Router 实现要点

- `@router.post("/agent-runs", status_code=202)`
- 创建 Service 注入用 `Depends(get_agent_run_service)`
- SSE 用 `StreamingResponse` + `async generator`
- 错误统一抛 `HTTPException` 由 Router 错误映射（R-Layer3）

## 关联

- 节点：所有 11 节点都被 AgentRunService 编排
- 表：[agent_runs / agent_steps / tool_calls](../data-models/trace-tables.md)
- 状态机：[state-machines/run-status.mmd](../state-machines/run-status.mmd)
- 通用协议：[architecture/api-and-data-contracts.md §6](../../architecture/api-and-data-contracts.md)
- ADR-007 async + SSE
