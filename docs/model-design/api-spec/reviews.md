# reviews.md — 复盘端点

状态：本轮实现。

## 端点：POST /api/v1/reviews

用户提交复盘。**必填 Idempotency-Key**。

**请求 Schema** `CreateReviewRequest`：
| 字段 | 类型 | 必填 | 约束 |
|---|---|---|---|
| `plan_id` | `str` | ✅ | UUID |
| `mood` | `int` | ✅ | 1-5 |
| `blockers` | `str \| null` | ❌ | max 500 |
| `completed_task_ids` | `list[str]` | ✅ | UUID 数组 |
| `abandoned_task_ids` | `list[str]` | ✅ | UUID 数组 |
| `free_text` | `str \| null` | ❌ | max 1000 |
| `trigger_replan` | `bool` | ❌ | 默认由服务端按双层规则判（见 PRD §8） |

**成功响应 200** `ReviewResult`：
| 字段 | 类型 |
|---|---|
| `review_id` | `str` |
| `companion_message` | `str`（由 companion_response 节点生成） |
| `suggested_replan` | `bool` |
| `next_plan_id` | `str \| null`（如触发 replan） |

**错误**：
| HTTP | code |
|---|---|
| 422 | VALIDATION_REVIEW_INVALID |
| 409 | STATE_PLAN_NOT_COMPLETED（plan 还没完成） |
| 404 | NOT_FOUND_PLAN |

## 副作用

提交后 service 异步触发：
1. 计算 consecutive_abandoned / consecutive_completed（更新 reviews）
2. 路由到 companion_response 节点生成话术
3. 按 PRD §8 双层规则判定是否建议 replan
4. 若建议 replan，可选自动触发新的 plan_run（需用户在前端确认）

## 示例

```http
POST /api/v1/reviews
Idempotency-Key: idem-7d4e
{
  "plan_id": "p-9e2a",
  "mood": 2,
  "blockers": "太累了",
  "completed_task_ids": ["t-1a8b"],
  "abandoned_task_ids": ["t-2c9d"]
}
```

## 关联

- 表：[reviews.md](../data-models/reviews.md)
- 节点：[companion_response.spec.md](../agent-nodes/companion_response.spec.md)
- 产品规则：[PRD §8 双层调整规则](../../overview/product-overview.md)
