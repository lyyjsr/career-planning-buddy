# user_profiles.md — 用户画像

状态：本轮实现。

## 字段

| 字段 | 类型 | NULL | 默认 | 约束 | 说明 |
|---|---|---|---|---|---|
| user_id | `uuid` | NO | — | PK + FK→users.id ON DELETE CASCADE | 一对一 |
| goal_type | `varchar(32)` | NO | `'other'` | CHECK ∈ {`ai_backend`,`agent_app`,`backend_java`,`data_engineer`,`fullstack`,`other`} | 目标方向 |
| stage | `varchar(16)` | NO | `'unknown'` | CHECK ∈ {`early`,`mid`,`late`,`unknown`} | 求职阶段 |
| time_budget_minutes | `integer` | NO | `120` | CHECK between 15 and 480 | 默认日可用时间（PRD 字段名为 available_minutes，统一为本字段） |
| skill_level | `varchar(16)` | NO | `'intermediate'` | CHECK ∈ {`beginner`,`intermediate`,`advanced`} | 技能自评 |
| skill_summary | `text` | YES | NULL | max 2000 字符 | 技能自由描述（PRD 决策 7：结构化 tag 由 service 后续提取入 profile_preferences） |
| employment_status | `varchar(32)` | YES | NULL | CHECK ∈ {`student_year_4`,`fresher`,`working`,`gap`} | 就业状态 |
| deadline | `date` | YES | NULL | —— | 求职截止日（决策 8：deadline 入表，规划阶段计算需要按日截止差） |
| profile_preferences | `jsonb` | YES | NULL | default `'{}'` | 决策 8：包含 `target_companies: list[str]`、`preferred_time_slot: "morning"/"afternoon"/"evening"`等可演进字段；不入主表避免 schema 膨胀 |
| version | `integer` | NO | `1` | `Field(ge=1)` | **乐观锁**（与 plans/tasks 一致） |
| created_at | `timestamptz` | NO | `now()` | —— | —— |
| updated_at | `timestamptz` | NO | `now()` | —— | —— |

## 索引

| 名 | 字段 | 说明 |
|---|---|---|
| PK | user_id | 一对一主键 |
| idx_profiles_goal_deadline | (goal_type, deadline) | 按 goal_type 统计 + 按 deadline 排序 |

## 外键

`user_id → users.id ON DELETE CASCADE`（删用户清画像）。

## 示例行

```sql
INSERT INTO user_profiles (user_id, goal_type, stage, time_budget_minutes, skill_level)
VALUES ('u-7c3e2f1a-...', 'agent_app', 'mid', 180, 'intermediate');
```

## 关联枚举

- `goal_type` ↔ `GoalType` Pydantic StrEnum（[schemas/enums.py](../../../backend/app/schemas/enums.py) 已实装 GoalType，本字段规范化为 varchar CHECK 保持与外部 API 命名一致）
