# data-models/ 数据模型 spec 入口

状态：本轮实现。

English summary: Per-table PostgreSQL specs — full columns, types, constraints, indexes, FKs, sample row. Authoritative for AI to write SQLAlchemy ORM and Alembic migrations. Source of truth for table fields.

## 定位

每张核心业务表一份 `.md` spec，给 AI 写 `app/models/*.py`（SQLAlchemy ORM）和 `db/migrations/versions/*.py`（Alembic）直接照抄。

表名、字段、类型、约束、索引、外键、示例行——**这就是字段级施工图纸**。

## 表清单（11 张）

| # | 表 | 用途 | spec |
|---|---|---|---|
| 1 | users | 用户基本信息（含 brief_login_type） | [users.md](./users.md) |
| 2 | user_profiles | 用户画像（goal_type / deadline / profile_preferences） | [user_profiles.md](./user_profiles.md) |
| 3 | plans | 计划（含 version 乐观锁 + 5 值状态机字段） | [plans.md](./plans.md) |
| 4 | tasks | 任务（含 state 机字段 + abandoned_reason_text） | [tasks.md](./tasks.md) |
| 5 | reviews | 复盘（mood / blockers / adjustment_request） | [reviews.md](./reviews.md) |
| 6 | memories | 长期记忆（4 类型 + status + embedding） | [memories.md](./memories.md) |
| 7 | memory_candidates | 记忆候选池（敏感用户确认） | [memory_candidates.md](./memory_candidates.md) |
| 8 | search_sources | 联网搜索结果快照 | [search_sources.md](./search_sources.md) |
| 9 | experience_atoms | 经验原子（pgvector + goal_type 索引） | [experience_atoms.md](./experience_atoms.md) |
| 10 | companion_messages | 陪伴话术存储（plan/review/task 关联）| [companion_messages.md](./companion_messages.md) |
| 11 | agent_runs + agent_steps + tool_calls | Trace 三表 | [trace-tables.md](./trace-tables.md) |

## 全局 ER 图

参 [er-diagram.mmd](./er-diagram.mmd)。

## 表 spec 模板（每份遵守）

```markdown
# <表名>.md — 表用途一句话

## 字段

| 字段 | 类型 | NULL | 默认 | 约束 | 说明 |
|---|---|---|---|---|---|

## 索引

## 外键

## 示例行

## 关联状态机
```

## 来源与权威

- 字段定义**权威来源于本目录**；`architecture/api-and-data-contracts.md` §11 只列名。
- 设计依据：[ADR-004 PostgreSQL + pgvector](../../architecture/adr.md)
- 一致性约束：[TDD §11.4](../../architecture/tdd.md)
- 迁移规则：`backend/db/migrations/README.md`
