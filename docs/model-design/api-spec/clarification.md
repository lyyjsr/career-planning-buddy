# Clarification 契约

澄清不另设 REST 端点。Agent Run 缺少必要信息时，通过 SSE 发：

```json
{
  "run_id": "...",
  "sequence": 5,
  "questions": ["你目前处于求职准备的哪个阶段？"],
  "slot_names": ["stage"],
  "hint_options": {
    "stage": ["exploring", "preparing", "applying", "interviewing"]
  }
}
```

第一版不在同一 Run 内暂停并恢复。处理方式：

1. 当前 Run 以 degraded 结束，fallback_reason=`profile_incomplete`；
2. 前端展示澄清表单；
3. 用户 PUT/PATCH Profile；
4. 前端创建新 Run。

这样避免引入复杂 Checkpoint 和长期挂起状态。后续确有需求再增加 `waiting_input` 状态。
