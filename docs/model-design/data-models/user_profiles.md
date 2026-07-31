# user_profiles — 用户画像

| 字段 | 类型 | NULL | 默认/约束 | 说明 |
|---|---|---:|---|---|
| user_id | uuid | NO | PK, FK users.id ON DELETE CASCADE | 一对一 |
| goal_type | varchar(32) | NO | CHECK ai_backend/agent_app/backend_java/data_engineer/fullstack/other | 目标方向 |
| stage | varchar(16) | NO | CHECK exploring/preparing/applying/interviewing | 求职阶段 |
| time_budget_minutes | integer | NO | CHECK 15..480 | 每日时间预算 |
| skill_level | varchar(16) | NO | CHECK beginner/intermediate/advanced | 自评等级 |
| skill_summary | text | YES | max 2000 由 Schema 保证 | 技能描述 |
| deadline | date | YES | | 目标截止日 |
| preferences | jsonb | NO | default '{}' | 时间偏好、目标公司等可演进字段 |
| version | integer | NO | default 1, >=1 | 乐观锁 |
| created_at | timestamptz | NO | now() | |
| updated_at | timestamptz | NO | now() | |

`preferences` Pydantic Schema 第一版只允许：`target_companies`, `preferred_time_slot`, `weekly_available_days`。
