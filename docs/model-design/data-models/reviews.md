# reviews.md — 复盘

状态：本轮实现。

## 字段

| 字段 | 类型 | NULL | 默认 | 约束 | 说明 |
|---|---|---|---|---|---|
| id | `uuid` | NO | `gen_random_uuid()` | PK | —— |
| user_id | `uuid` | NO | — | FK→users.id | —— |
| plan_id | `uuid` | NO | — | FK→plans.id | 关联 plan |
| mood | `integer` | NO | — | CHECK between 1 and 5 | 用户提交时主观打分（[PRD §8 调整规则](../../overview/product-overview.md)） |
| blockers | `text` | YES | NULL | max 500 | 用户填的阻碍 |
| completed_task_ids | `uuid[]` | NO | `'{}'` | —— | 本轮 plan 完成的 task IDs |
| abandoned_task_ids | `uuid[]` | NO | `'{}'` | —— | 放弃的 task IDs |
| free_text | `text` | YES | NULL | max 1000 | 用户自由复盘 |
| consecutive_abandoned | `integer` | NO | `0` | `Field(ge=0)` | 累计连续放弃次数（触发 T2 陪伴） |
| consecutive_completed | `integer` | NO | `0` | `Field(ge=0)` | 累计连续完成次数（触发 T5 陪伴） |
| created_at | `timestamptz` | NO | `now()` | —— | —— |

## 索引

| 名 | 字段 | 用途 |
|---|---|---|
| idx_reviews_user_created | (user_id, created_at DESC) | 历史复盘 / 连续性统计 |
| idx_reviews_plan | (plan_id) | plan 关联复盘 |

## 外键

- `user_id → users.id`
- `plan_id → plans.id`

## 示例行

```sql
INSERT INTO reviews (id, user_id, plan_id, mood, blockers, completed_task_ids, abandoned_task_ids,
                     consecutive_abandoned, free_text)
VALUES ('r-3b4f-...', 'u-7c3e2f1a-...', 'p-9e2a-...', 2, '太累了，没精力',
        ARRAY['t-1a8b-...']::uuid[], ARRAY['t-2c9d-...']::uuid[],
        2, '今天只完成了 1 项，算法太难了');
```

## 关联产品逻辑

- mood、consecutive_abandoned、consecutive_completed 为 companion_response 6 触发时刻的判定来源（[companion_response.spec.md §1](../agent-nodes/companion_response.spec.md)）
- 提交后由 service 触发可选重规划（PRD §8 双层调整）
