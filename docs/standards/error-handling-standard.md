# 错误处理与降级规范

状态：本轮实现。

English summary: Error classification, fallback chaining, fallback_reason naming, hard-fail-vs-degrade decision rules. Spec for Router error mapping + node error boundary.

## 1. 错误分类

| 类型 | 例子 | 处理原则 |
|---|---|---|
| **业务校验错**（VALIDATION_*） | 用户输入字段不合法 | 422 直接返回，不入 Agent |
| **状态机违规**（STATE_*） | task 不能从 completed 转 abandoned | 409 直接返回 |
| **资源不存在**（NOT_FOUND_*） | task_id 不存在 | 404 直接返回 |
| **鉴权**（AUTH_*） | token 过期 / 跨用户访问 | 401/403 直接返回 |
| **限流**（RATE_LIMITED_*） | 单用户 >5 runs/min | 429 直接返回 |
| **Agent 执行错**（AGENT_*） | LangGraph 抛未知异常 | 503，trace 记 ERROR |
| **降级**（FALLBACK_*） | LLM 超时 / schema 不符 / 超预算 | 200，body 带 `fallback_reason` |

## 2. 降级 vs Fail 判定（关键）

**判别原则**：能不能给用户一个**可接受的用户体验**？

| 能 | 处理 | HTTP |
|---|---|---|
| ✅ 给用户合理可用结果（即使降级） | degraded + fallback_reason | **200** |
| ❌ 无法给用户任何结果 | failed + UNKNOWN_ERROR | 503 |

例：
- intent_router timeout → 降级 query_plan，**仍能给用户最近计划**，HTTP 200 + fallback_reason
- persist 节点事务回滚 → 用户看不到结果，HTTP 503

## 3. fallback_reason 命名规范

格式：`FALLBACK_<NODE>_<CAUSE>`。完整列表参 [model-design/api-spec/errors.md](../model-design/api-spec/errors.md) §fallback_reason 命名规则。新增 fallback_reason **必须**同时更新 errors.md 和对应节点 spec §4。

## 4. 强制不变量

| ID | 不变量 | 守护 |
|---|---|---|
| E-1 | 任何 except 块不得空（无 `except: pass`） | ruff rule B902 + review |
| E-2 | 降级必须带 `fallback_reason` 字段（不可 null） | Pydantic validator |
| E-3 | 5xx 响应不得泄露内部异常 stack | Router error mapper |
| E-4 | Trace 必须记录 fallback_reason 或 error_class | Service 强制写 |
| E-5 | 一行 trace 必须对应一次节点执行（成功或失败） | harness 守 |

## 5. 重试策略（harness 内）

| 错误类型 | 重试次数 | 退避 |
|---|---|---|
| `ValidationError`（LLM schema 不符） | 1 | immediate |
| `asyncio.TimeoutError`（LLM） | 0 | 降级 |
| `asyncio.TimeoutError`（web_search） | 0 | 跳过该块 |
| `asyncio.TimeoutError`（DB） | 1 | 200ms |
| `AgentBudgetExceeded` | 0 | 立即降级 |

## 6. 异常 → HTTP 映射（Router 层）

```python
# 每个自定义异常基类带 code + http_status
class AgentError(Exception):
    code = "AGENT_RUN_FAILED"
    http_status = 503

# Router 全局错误映射 middleware
@app.exception_handler(AgentError)
async def handler(e: AgentError):
    return JSONResponse(
        status_code=e.http_status,
        content={"error": {"code": e.code, "message": str(e), "request_id": ctx.request_id}},
    )
```

## 7. 告警规则（阶段 6+ 起）

| 触发 | 告警级别 |
|---|---|
| 单节点 5 分钟内 fallback 占比 > 30% | P1（监控） |
| Agent 整体 fail 率 > 10% | P0 |
| Tavily 连续 3 次 timeout | P1 |

## 8. 引用

- [architecture/api-and-data-contracts.md §3 错误响应](../architecture/api-and-data-contracts.md)
- [model-design/api-spec/errors.md](../model-design/api-spec/errors.md) 业务错误码表
- [AGENTS.md R-Fail1](../../AGENTS.md)
- [verification-and-review.md](../governance/verification-and-review.md) 评审清单
