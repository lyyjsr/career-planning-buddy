# errors.md — 统一错误响应规范

状态：本轮实现。

## 统一错误响应格式

所有 4xx/5xx 响应遵循：

```json
{
  "error": {
    "code": "VALIDATION_RUN_INVALID",
    "message": "用户可读的错误描述",
    "field_errors": [{"field": "message", "reason": "min length 1"}],
    "fallback_reason": null,
    "request_id": "req-7c3e2f"
  }
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `error.code` | `str` | ✅ | 业务错误码（前缀见下表）|
| `error.message` | `str` | ✅ | 用户可读描述（中英双语字典待定）|
| `error.field_errors` | `list[FieldError] \| null` | ❌ | 仅 422 时含字段级错误 |
| `error.fallback_reason` | `str \| null` | ❌ | **降级时**填，HTTP 仍 200 但通过错误响应提示 |
| `error.request_id` | `str` | ✅ | X-Request-Id 对应 |

## 业务错误码表

| 前缀 | HTTP | 含义 | 示例 code |
|---|---|---|---|
| `AUTH_*` | 401 / 403 | 鉴权失败 | AUTH_TOKEN_EXPIRED, AUTH_NOT_OWN_MEMORY |
| `VALIDATION_*` | 422 | 字段校验失败 | VALIDATION_RUN_INVALID, VALIDATION_PROFILE_INVALID, VALIDATION_REVIEW_INVALID, VALIDATION_TASK_INVALID |
| `STATE_*` | 409 | 状态机违规 / 版本冲突 | STATE_RUN_ALREADY_ACTIVE, STATE_PLAN_NOT_COMPLETED, STATE_TASK_INVALID_TRANSITION, STATE_VERSION_CONFLICT |
| `NOT_FOUND_*` | 404 | 资源不存在 | NOT_FOUND_PROFILE, NOT_FOUND_TASK, NOT_FOUND_PLAN, NOT_FOUND_MEMORY |
| `RATE_LIMITED_*` | 429 | 限流 | RATE_LIMITED_RUN_PER_USER, RATE_LIMITED_AUTH |
| `AGENT_*` | 500 / 503 | Agent 执行错误 | AGENT_RUN_FAILED, AGENT_TIMEOUT, AGENT_BUDGET_EXCEEDED |
| `FALLBACK_*` | 200 | 降级（body 带说明） | FALLBACK_LLM_TIMEOUT, FALLBACK_SCHEMA_INVALID, FALLBACK_BUDGET_EXCEEDED |

## fallback_reason 命名规则

`FALLBACK_<节点>_<原因>`：
| 值 | 触发场景 |
|---|---|
| `FALLBACK_INTENT_LLM_TIMEOUT` | intent_router LLM 超时 |
| `FALLBACK_INTENT_SCHEMA_INVALID` | intent_router schema 不符 |
| `FALLBACK_AGENT_BUDGET_EXCEEDED` | career_planning_agent 超预算 |
| `FALLBACK_AGENT_MAX_ROUNDS_EXHAUSTED` | 超 2 轮未收敛 |
| `FALLBACK_RISK_CLASSIFIER_FAILURE` | risk_gate LLM 分类器异常 |
| `FALLBACK_WEB_SEARCH_TIMEOUT` | web_search 工具超时 |

## 异常 → HTTP 映射（Router 层职责）

```python
# app/api/exceptions.py（建议）
EXCEPTION_TO_HTTP = {
    "AuthenticationError": 401,
    "AuthorizationError": 403,
    "ValidationError": 422,
    "StateTransitionError": 409,
    "VersionConflictError": 409,
    "NotFoundError": 404,
    "RateLimitError": 429,
    "AgentError": 503,
}
```

## 关联

- 通用协议：[architecture/api-and-data-contracts.md §3](../../architecture/api-and-data-contracts.md)
- 各端点的具体错误响应：见本目录各 `*.md` 端点的 "错误" 表
- Trace 字段 fallback_reason：[trace-tables.md](../data-models/trace-tables.md)
