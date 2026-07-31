# Reviews API

## POST /api/v1/reviews

需要 `Idempotency-Key`。

```json
{
  "plan_id": "c91f8734-2839-4f55-9db1-1c39b8a410f2",
  "review_date": "2026-07-31",
  "mood": 2,
  "blockers": "部署环境一直报错",
  "adjustment_request": "明天任务少一点",
  "free_text": "今天把接口跑通了，但没有完成部署"
}
```

客户端不提交 completed_task_ids 和 abandoned_task_ids。Service 根据该日期的 tasks 计算数量，避免事实冲突。

### Response 201

```json
{
  "review_id": "71f6b355-d6a8-480c-890d-684d8bcb2785",
  "completed_count": 1,
  "abandoned_count": 1,
  "suggested_replan": true,
  "replan_reason": "时间预算下降且存在持续阻塞",
  "companion_message": "今天已经推进了接口，明天先把部署拆小。"
}
```

## GET /api/v1/reviews

Query：plan_id、date_from、date_to、cursor、limit。

## POST /api/v1/reviews/{review_id}/accept-replan

需要 `Idempotency-Key`。只在 `suggested_replan=true` 且尚未接受时可调用。

Response 202：

```json
{
  "run_id": "...",
  "status": "pending",
  "events_url": "/api/v1/agent-runs/.../events"
}
```

该端点等价于服务端创建 `hint_intent=replan`、`source_plan_id=review.plan_id` 的新 Run。它不立即归档原计划，只有新计划成功持久化后才归档。
