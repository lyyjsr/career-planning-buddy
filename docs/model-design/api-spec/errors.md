# 错误响应与业务码

格式：

```json
{"error":{"code":"STATE_VERSION_CONFLICT","message":"...","request_id":"...","details":{}}}
```

| code | HTTP | 说明 |
|---|---:|---|
| AUTH_INVALID_TOKEN | 401 | JWT 无效或过期 |
| AUTH_FORBIDDEN | 403 | 无权限 |
| NOT_FOUND_PROFILE | 404 | 未建档 |
| NOT_FOUND_RUN | 404 | Run 不存在 |
| NOT_FOUND_PLAN | 404 | Plan 不存在 |
| NOT_FOUND_TASK | 404 | Task 不存在 |
| STATE_VERSION_CONFLICT | 409 | 乐观锁冲突 |
| STATE_INVALID_TRANSITION | 409 | 非法状态转移 |
| STATE_RUN_ALREADY_ACTIVE | 409 | 用户已有活动 Run |
| STATE_RUN_ALREADY_FINISHED | 409 | 终态操作冲突 |
| STATE_REPLAN_ALREADY_ACCEPTED | 409 | 重规划已接受 |
| VALIDATION_PROFILE_INVALID | 422 | 画像字段错误 |
| VALIDATION_RUN_INVALID | 422 | Run 请求错误 |
| VALIDATION_LLM_OUTPUT | 422/内部降级 | 模型结构化输出错误 |
| RATE_LIMITED | 429 | 用户限流 |
| PROVIDER_TIMEOUT | 503/内部降级 | 外部服务超时 |
| PROVIDER_UNAVAILABLE | 503/内部降级 | 外部服务不可用 |
| AGENT_DEADLINE_EXCEEDED | 504/内部状态 | Run 超时 |

公开 message 不返回堆栈、SQL、API Key 或完整 Provider 原文。
