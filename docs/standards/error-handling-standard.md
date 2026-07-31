# 错误处理与降级规范

## 1. HTTP 错误

| 类型 | HTTP | 示例 code |
|---|---:|---|
| 身份无效 | 401 | AUTH_INVALID_TOKEN |
| 无权限 | 403 | AUTH_FORBIDDEN |
| 资源不存在 | 404 | NOT_FOUND_TASK |
| 幂等/状态冲突 | 409 | STATE_TASK_TRANSITION_INVALID |
| 参数或业务校验 | 422 | VALIDATION_PROFILE_INVALID |
| 限流 | 429 | RATE_LIMITED |
| 外部依赖暂不可用 | 503 | PROVIDER_UNAVAILABLE |

响应结构遵守 `contract-standard.md`，生产响应不暴露堆栈和密钥。

## 2. Agent Run 终态

Agent Run 通过异步 API 创建，执行期错误通常不改变 `POST /agent-runs` 的 202 响应，而是收敛到数据库状态和 SSE 终态：

- `completed`：正常结果；
- `degraded`：存在可用但质量受限的计划/模板结果，必须带 `fallback_reason`；
- `failed`：没有可用结果；
- `cancelled`：用户或系统取消。

持久化失败不能标记 degraded，因为用户没有可读取的结果。

## 3. 重试

- LLM 结构化输出失败：最多修复 1 次；
- 网络连接错误：只对幂等调用有限重试，使用短退避；
- Tool 超时：不无限重试，记录错误后按节点规则跳过或降级；
- 数据库事务失败：事务整体回滚，由 API 层决定是否安全重试；
- 副作用写入不得由 Agent 自由重试。

## 4. 预算错误

超过 LLM 次数、Tool 轮次、Token 或 Run deadline 时，抛出明确预算异常，停止后续调用并写事件。能生成合规模板时标记 degraded，否则 failed。

## 5. 日志与 Trace

每个异常至少记录 request_id/run_id、错误 code、节点、Provider、重试次数和脱敏摘要。不得记录 JWT、API key、完整敏感输入和外部页面全文。
