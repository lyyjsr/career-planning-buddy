# plans — 求职计划版本

一个 Plan 是“中期方向 + 当前 planning_date 的行动批次”。它不会一次生成未来数周的所有 Task；次日续接或明显调整会基于来源 Plan 创建新版本。

| 字段 | 类型 | NULL | 默认/约束 | 说明 |
|---|---|---:|---|---|
| id | uuid | NO | PK | |
| user_id | uuid | NO | FK users.id | 所属用户 |
| source_run_id | uuid | NO | UNIQUE, FK agent_runs.id | 产生该计划的 Run |
| parent_plan_id | uuid | YES | FK plans.id | continue/adjust 的上一个计划 |
| status | varchar(16) | NO | generated/active/completed/archived | 见状态机 |
| plan_date | date | NO | | 当前行动批次日期，按用户时区确定 |
| horizon_start | date | NO | | 方向层起始日期 |
| horizon_end | date | NO | | 最多展开 8 周 |
| overall_direction | varchar(500) | NO | | 中期整体方向 |
| weekly_focus_json | jsonb | NO | default '[]' | 1~8 条 `{week_index,focus,success_signal}` |
| summary | varchar(500) | NO | | 当前版本用户可读摘要 |
| rationale | text | NO | | 规划理由 |
| adjustment_reason | text | YES | | adjust replan 必填，continue 可为空 |
| assumptions_json | jsonb | NO | default '[]' | 最多 5 条假设 |
| evidence_refs_json | jsonb | NO | default '[]' | `[{kind,id}]`，Pydantic 校验 |
| metadata_json | jsonb | NO | default '{}' | prompt/model/replan_mode 等非核心元数据 |
| version | integer | NO | default 1 | 乐观锁 |
| adopted_at | timestamptz | YES | | 首个任务开始时写入 |
| completed_at | timestamptz | YES | | 当日批次全部完成时写入 |
| archived_at | timestamptz | YES | | 被下一版本替代或手动归档 |
| created_at | timestamptz | NO | now() | |
| updated_at | timestamptz | NO | now() | |

## 索引与约束

- `(user_id, plan_date desc, created_at desc)`；
- partial unique：同一用户最多一个 `status IN ('generated','active')` 的计划；
- `parent_plan_id` 不得等于自身；
- `horizon_start <= plan_date <= horizon_end`；
- weekly_focus_json 必须通过 `WeeklyFocusList` Pydantic Schema，week_index 连续且不重复；
- 新计划成功持久化时，Service 在同一事务归档旧 generated/active/completed 来源计划；事务回滚时旧状态不变；
- evidence_refs_json 中每个引用必须在 Persist 前按用户/Run/类型校验：memory 属于用户且 active，experience_atom 可用，search_source 属于 source_run_id；
- PlanDetail 的 sources 由 Service 按 evidence_refs_json 解析，不把 JSONB 当作任意元数据。
