# plans — 求职计划

| 字段 | 类型 | NULL | 默认/约束 | 说明 |
|---|---|---:|---|---|
| id | uuid | NO | PK | |
| user_id | uuid | NO | FK users.id | 所属用户 |
| source_run_id | uuid | NO | UNIQUE, FK agent_runs.id | 产生该计划的 Run |
| parent_plan_id | uuid | YES | FK plans.id | replan 的上一个计划 |
| status | varchar(16) | NO | generated/active/completed/archived | 见状态机 |
| summary | varchar(500) | NO | | 用户可读摘要 |
| rationale | text | NO | | 规划理由 |
| adjustment_reason | text | YES | | replan 原因 |
| assumptions_json | jsonb | NO | default '[]' | 最多 5 条假设 |
| metadata_json | jsonb | NO | default '{}' | prompt/model/策略等非核心元数据 |
| version | integer | NO | default 1 | 乐观锁 |
| adopted_at | timestamptz | YES | | 首个任务开始时写入 |
| completed_at | timestamptz | YES | | 全部任务完成时写入 |
| archived_at | timestamptz | YES | | 被替代或手动归档 |
| created_at | timestamptz | NO | now() | |
| updated_at | timestamptz | NO | now() | |

## 索引与约束

- `(user_id, created_at desc)`；
- partial unique：同一用户最多一个 `status IN ('generated','active')` 的计划；
- `parent_plan_id` 不得等于自身；
- 新计划成功持久化时，Service 在同一事务归档旧 generated/active 计划。
