# plans.md — 计划

状态：本轮实现。

## 字段

| 字段 | 类型 | NULL | 默认 | 约束 | 说明 |
|---|---|---|---|---|---|
| id | `uuid` | NO | `gen_random_uuid()` | PK | UUIDv4 |
| user_id | `uuid` | NO | — | FK→users.id | 所属用户 |
| version | `integer` | NO | `1` | `Field(ge=1)` | **乐观锁** R-Contract1 |
| status | `varchar(16)` | NO | `'pending'` | CHECK ∈ {`pending`,`active`,`completed`,`archived`} | 状态机见 state-machines/run-status.mmd |
| content_json | `jsonb` | NO | — | NOT NULL | 完整 plan 内容（rationale / assumptions / metadata） |
| intent_at_creation | `varchar(32)` | NO | — | CHECK ∈ {`create_plan`,`replan`} | 创建时意图 |
| created_at | `timestamptz` | NO | `now()` | — | — |
| updated_at | `timestamptz` | NO | `now()` | — | — |
| archived_at | `timestamptz` | YES | NULL | — | 归档时间 |

## 索引

| 名 | 字段 | 用途 |
|---|---|---|
| PK | id | —— |
| idx_plans_user_active | (user_id, status) WHERE status='active' | 取用户当前激活 plan |
| idx_plans_user_created | (user_id, created_at DESC) | 历史列表 |

## 外键

`user_id → users.id ON DELETE RESTRICT`（用户删除前必须先归档所有 plan）。

## 示例行

```sql
INSERT INTO plans (id, user_id, version, status, content_json, intent_at_creation)
VALUES ('p-9e2a-...', 'u-7c3e2f1a-...', 1, 'active',
        '{"rationale":"基于近7天统计...","assumptions":["用户偏好早晨执行"]}',
        'create_plan');
```

## 关联状态机

参 [state-machines/run-status.mmd](../state-machines/run-status.mmd) pending→active→completed/archived。

## content_json Schema（jsonb 内部）

```json
{
  "rationale": "str max 500",
  "assumptions": ["str max 5"],
  "metadata": {"strategy": "conservative", "adjusted_from": null}
}
```
