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
- pending/in_progress→abandoned；
- expired 只能由系统 Job 设置；客户端不能主动写 expired；
- completed 需要 actual_minutes；
- abandoned 需要 abandoned_reason；other 时还需 reason_text；
- 首个任务开始时，同事务把计划 generated→active 并写 adopted_at。
- 任务完成只更新它所属的 `scheduled_date`；Plan 只有在当前七天执行表的全部 Task 都完成后才进入 completed。

### Response 200

```json
{
  "task": {},
  "plan_status": "active",
  "companion_message": "你已经完成了第一步。"
}
```

version 冲突或非法状态转移返回 409。
