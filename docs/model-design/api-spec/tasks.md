# Tasks API

## GET /api/v1/tasks

Query：

| 参数 | 默认 | 说明 |
|---|---|---|
| date | today | scheduled_date |
| state | null | 状态过滤 |
| plan_id | null | 计划过滤 |
| cursor | null | |
| limit | 50 | 1~100 |

## PATCH /api/v1/tasks/{task_id}

### Request

```json
{
  "state": "completed",
  "version": 3,
  "actual_minutes": 42,
  "abandoned_reason": null,
  "abandoned_reason_text": null
}
```

规则：

- pending→in_progress；
- in_progress→completed；
- completed→in_progress，用于用户撤销误操作；撤销时清空 completed_at 和 actual_minutes，并把刚完成的 Plan 恢复为 active；
- pending/in_progress→abandoned；
- expired 只能由系统 Job 设置；客户端不能主动写 expired；
- completed 需要 actual_minutes；
- abandoned 需要 abandoned_reason；other 时还需 reason_text；
- 首个任务开始时，同事务把计划 generated→active 并写 adopted_at。
- 任务完成只更新它所属的 `scheduled_date`，不会删除或补位；Plan 在当前周期任务全部进入 completed/abandoned/expired 后进入 completed。

## 每日详情与调整

- `GET /tasks/{task_id}`：返回任务、本周重点、成功标准和是否可编辑；
- `PATCH /tasks/{task_id}/details`：用户直接编辑 pending Task 的内容与预计时间；
- `POST /tasks/{task_id}/adjustment-proposals`：让 AI 生成结构化差异提案，不修改 Task；
- `POST /task-adjustment-proposals/{id}/confirm|reject`：用户确认后才原子应用或拒绝；
- 调整不得突破每日时间预算、固定周边界或覆盖已开始/已结算事实。

### Response 200

```json
{
  "task": {},
  "plan_status": "active",
  "companion_message": "你已经完成了第一步。"
}
```

version 冲突或非法状态转移返回 409。
