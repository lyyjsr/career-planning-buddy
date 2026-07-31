# Profile API

## GET /api/v1/profile

返回当前用户画像。未建档返回 404 `NOT_FOUND_PROFILE`。

## PUT /api/v1/profile

首次创建或完整替换画像。需要 `Idempotency-Key`。

```json
{
  "goal_type": "agent_app",
  "stage": "preparing",
  "time_budget_minutes": 120,
  "skill_level": "intermediate",
  "skill_summary": "熟悉 FastAPI、RAG 和基础 Agent 开发",
  "deadline": "2026-10-31",
  "preferences": {
    "target_companies": ["字节跳动"],
    "preferred_time_slot": "evening",
    "weekly_available_days": [1,2,3,4,5]
  }
}
```

必填：goal_type、stage、time_budget_minutes、skill_level。

## PATCH /api/v1/profile

部分更新，必须带当前 `version`：

```json
{
  "version": 2,
  "time_budget_minutes": 90,
  "skill_summary": "..."
}
```

成功响应返回完整 Profile 和新 version。

## 约束

- `time_budget_minutes`: 15~480；
- `deadline` 不能早于当前日期；
- `preferences` 只允许已定义字段；
- version 冲突返回 409；
- 请求不允许 user_id。
