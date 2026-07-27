# plans.md — 计划端点

状态：本轮实现。

> 与 agent-runs 配合：plan_run 异步产出 plan 后，前端用本端点读 / 历史翻阅。PlanDetail 是 service 由 `plans + tasks + search_sources + companion_messages` 拼装的响应视图（决策 3）。

## 端点：GET /api/v1/plans/active

读当前用户的活跃计划（status ∈ {`active`, `adopted`}）。

**成功响应 200** `PlanDetail`：

| 字段 | 类型 | 来源 |
|---|---|---|
| plan_id | UUID | plans.id |
| user_id | UUID | plans.user_id |
| horizon | `overall / weekly / today` | service 默认 today |
| summary | str | plans.content_json.rationale |
| milestones | list[Milestone]? | plans.content_json.milestones |
| weekly_focus | WeeklyFocus? | plans.content_json.weekly_focus |
| today_tasks | list[PlanTask] | JOIN tasks (plan_id) |
| adjustment_reason | str? | plans.content_json.adjustment_reason（replan 时填） |
| companion_message | str? | 当前 plan 最近一行 companion_messages.message |
| sources | list[SourceRef] | JOIN search_sources via run_id |
| status | PlanStatus | plans.status（`active` / `adopted`） |
| version | int | plans.version |
| created_at / updated_at | timestamp | — |

**错误**：

| HTTP | code | 触发 |
|---|---|---|
| 401 | AUTH_TOKEN_EXPIRED | —— |
| 404 | NOT_FOUND_ACTIVE_PLAN | 用户当前无活跃 plan（首次建档前或全部 archived）|

## 端点：GET /api/v1/plans

列表（规划历史）。Cursor 分页。

**Query 参数**：

| 参数 | 类型 | 默认 | 约束 |
|---|---|---|---|
| `status` | `pending/active/adopted/completed/archived \| null` | null | 按状态过滤 |
| `intent_at_creation` | `create_plan / replan \| null` | null | 区分首计划/重规划 |
| `cursor` | str? | null | |
| `limit` | int | 20 | `Field(ge=1, le=100)` |

**成功响应 200** `PlanListResponse`：
```json
{ "items": [PlanSummary, ...], "next_cursor": "str | null" }
```

`PlanSummary` 字段：`plan_id / status / summary（rationale 摘要前 100 字） / created_at / task_count / completed_task_count`。

## 端点：GET /api/v1/plans/{plan_id}

单个 plan 详情。

**成功响应 200**：完整 `PlanDetail`（同 GET active 字段集）。

**错误**：

| HTTP | code |
|---|---|
| 401 | AUTH_TOKEN_EXPIRED |
| 403 | AUTH_NOT_OWN_PLAN |
| 404 | NOT_FOUND_PLAN |

## 端点：GET /api/v1/plans/{plan_id}/sources

关联的来源（search_sources）。

**成功响应 200** `SourceListResponse`：
```json
{ "items": [SourceRef, ...], "next_cursor": null }
```

**错误**：

| HTTP | code |
|---|---|
| 401 | AUTH_TOKEN_EXPIRED |
| 403 | AUTH_NOT_OWN_PLAN |
| 404 | NOT_FOUND_PLAN |

## Router 调用

- `routers/plans.py::get_active_plan` → `services.plan.read_active(user_id)` → `repositories.plan.get_active_by_user(user_id)` + JOIN tasks + JOIN companion_messages
- `routers/plans.py::list_plans` → `services.plan.list_by_user(user_id, filter, cursor, limit)`
- View 组装：`services.plan.compose_view(plan_row, tasks, sources, companion_message)` 输出 PlanDetail

## 关联

- 表：[plans.md](../data-models/plans.md) + [tasks.md](../data-models/tasks.md) + [search_sources.md](../data-models/search_sources.md) + [companion_messages.md](../data-models/companion_messages.md)
- 响应视图：[api-and-data-contracts.md §5.2 PlanDetail](../../architecture/api-and-data-contracts.md)
- 状态机：[state-machines/plan-status.mmd](../state-machines/plan-status.mmd)
- 端点触发：`plan.ready` SSE（[agent-runs.md](./agent-runs.md)）
