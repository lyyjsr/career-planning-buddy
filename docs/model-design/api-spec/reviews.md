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
| `adjustment_request` | `str \| null` | ❌ | max 300；用户主动提出的"调整请求"（PRD §8.1 复盘 4 项之一） |
| `free_text` | `str \| null` | ❌ | max 1000（自由复盘，与 adjustment_request 区分：调整请求是显式指令，自由文本是叙述） |
| `trigger_replan` | `bool` | ❌ | 默认由服务端按双层规则判（见 PRD §8） |

**成功响应 200** `ReviewResult`：
| 字段 | 类型 |
|---|---|
| `review_id` | `str` |
| `companion_message` | `str`（由 companion_response 节点生成） |
| `suggested_replan` | `bool` |
| `next_plan_id` | `str \| null`（如服务端自动触发 replan 则填；否则 null，需用户走 [POST /reviews/{id}/accept-replan](#endpostapiv1reviewsreview_idaccept-replan) 端点确认） |

**错误**：
| HTTP | code | 触发 |
|---|---|---|
| 422 | VALIDATION_REVIEW_INVALID | 字段校验失败 |
| 409 | STATE_PLAN_NOT_REVIEWABLE | plan 状态不属于 {active, adopted}（如已完成、已归档） |
| 404 | NOT_FOUND_PLAN | —— |

### 端点：POST /api/v1/reviews/{review_id}/accept-replan

用户在前端确认接受建议的 replan。先决条件：上游 review 返 `suggested_replan=true` 且 `next_plan_id=null`。**必填 Idempotency-Key**。

**成功响应 202** `ReplanAcceptedResponse`：
| 字段 | 类型 |
|---|---|
| `run_id` | `str`（新建的 plan_run） |
| `status` | `Literal["pending"]` |
| `events_url` | `str` |

**错误**：
| HTTP | code | 触发 |
|---|---|---|
| 404 | NOT_FOUND_REVIEW | —— |
| 409 | STATE_REVIEW_NO_SUGGESTED_REPLAN | 原 review.suggested_replan=false |
| 429 | RATE_LIMITED_RUN_PER_USER | 同用户已有 pending/running run |

> 路径形如 `/api/v1/reviews/r-3b4f-.../accept-replan`，行为等同 POST /agent-runs + hint_intent=replan + 上游 plan_id 注入。

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
