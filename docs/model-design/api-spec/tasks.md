# tasks.md — 任务端点

状态：本轮实现。

## 端点：GET /api/v1/tasks

列当前用户的任务（默认今日）。

**Query 参数**：
| 参数 | 类型 | 默认 | 约束 |
|---|---|---|---|
| `date` | ISO date | today | —— |
| `status` | `str \| null` | null | CHECK ∈ {`pending`,`in_progress`,`completed`,`abandoned`,`expired`} |
| `plan_id` | `uuid \| null` | null | —— |
| `cursor` | `str \| null` | null | 分页游标 |
| `limit` | `int` | 50 | `Field(ge=1, le=100)` |

**成功响应 200** `TaskListResponse`：
```json
{
  "items": [Task, ...],
  "next_cursor": "str | null"
}
```

**Task Schema**：参 [tasks 表](../data-models/tasks.md) 关键字段。

## 端点：PATCH /api/v1/tasks/{task_id}

更新任务状态（state 机）。**必填 Idempotency-Key + version**。

**请求 Schema** `UpdateTaskRequest`：
| 字段 | 类型 | 必填 |
|---|---|---|
| `state` | `Literal["in_progress","completed","abandoned","expired"]` | ✅ |
| `version` | `int` | ✅（乐观锁） |
| `actual_minutes` | `int \| null` | state=completed 时填 |
| `abandoned_reason` | `Literal["too_hard","too_easy","no_time","lost_interest","blocked","other"] \| null` | state=abandoned 时填 |
| `abandoned_reason_text` | `str \| null` | `abandoned_reason='other'` 时必填，max 200 |

**成功响应 200** `UpdateTaskResponse`：
| 字段 | 类型 |
|---|---|
| `task` | 完整 `Task`（含新 version）|
| `companion_message` | `str \| null`（任务完成/放弃触发了陪伴时刻 T2/T3 时返回，见 [companion_response.spec.md](../agent-nodes/companion_response.spec.md)）|

**错误**：
| HTTP | code |
|---|---|
| 422 | VALIDATION_TASK_INVALID |
| 409 | STATE_TASK_INVALID_TRANSITION（参 state-machines/task-state.mmd 合法转移） |
| 409 | STATE_VERSION_CONFLICT |
| 404 | NOT_FOUND_TASK |

## 示例

```http
PATCH /api/v1/tasks/t-1a8b
Idempotency-Key: idem-8b3c
{"state":"completed","version":3,"actual_minutes":25}
```

## Router 调用

`router → services.task.update_state(task_id, request) → repositories.task.update_version()`

## 关联

- 表：[tasks.md](../data-models/tasks.md)
- 状态机：[state-machines/task-state.mmd](../state-machines/task-state.mmd)
