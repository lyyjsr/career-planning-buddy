# tasks.md — 任务（用户执行项）

状态：本轮实现。

## 字段

| 字段 | 类型 | NULL | 默认 | 约束 | 说明 |
|---|---|---|---|---|---|
| id | `uuid` | NO | `gen_random_uuid()` | PK | —— |
| plan_id | `uuid` | NO | — | FK→plans.id ON DELETE CASCADE | 所属 plan |
| user_id | `uuid` | NO | — | FK→users.id | 冗余以便快速查询 |
| order_index | `integer` | NO | — | `Field(ge=0, le=2)` | 在 plan 内顺序（最多 3 个） |
| state | `varchar(16)` | NO | `'pending'` | CHECK ∈ {`pending`,`in_progress`,`completed`,`abandoned`,`expired`} | 状态机见 state-machines/task-state.mmd |
| starter_action | `text` | NO | — | max 200 | 可启动动作（PRD §7 维度 1） |
| deliverable | `text` | NO | — | max 200 | 完成可观测产物 |
| rationale | `text` | YES | NULL | max 300 | 为什么这个任务 |
| estimated_minutes | `integer` | NO | — | `Field(ge=5, le=480)` | 预估时长 |
| actual_minutes | `integer` | YES | NULL | `Field(ge=0)` | 实际时长（完成时填） |
| created_at | `timestamptz` | NO | `now()` | —— | —— |
| started_at | `timestamptz` | YES | NULL | —— | 进入 in_progress 时 |
| completed_at | `timestamptz` | YES | NULL | —— | 进入 completed 时 |
| abandoned_at | `timestamptz` | YES | NULL | —— | —— |
| abandoned_reason | `varchar(32)` | YES | NULL | CHECK ∈ {`too_hard`,`too_easy`,`no_time`,`lost_interest`,`blocked`,`other`} | —— |
| abandoned_reason_text | `varchar(200)` | YES | NULL | 当 abandoned_reason='other' 时必填 | 用户自由文本（PRD §6.2 "放弃任务记录原因"产品要求） |
| expires_at | `timestamptz` | YES | NULL | —— | 进入 expire 时 |

## 索引

| 名 | 字段 | 用途 |
|---|---|---|
| idx_tasks_user_state_date | (user_id, state, created_at DESC) | 用户当天任务查询 |
| idx_tasks_plan | (plan_id, order_index) | plan 内任务排序 |

## 外键

- `plan_id → plans.id ON DELETE CASCADE`
- `user_id → users.id ON DELETE RESTRICT`

## 示例行

```sql
INSERT INTO tasks (id, plan_id, user_id, order_index, state, starter_action, deliverable,
                   estimated_minutes, rationale)
VALUES ('t-1a8b-...', 'p-9e2a-...', 'u-7c3e2f1a-...', 0, 'pending',
        '打开 GitHub 新建仓库 ai-agent-starter',
        'GitHub 仓库 URL 已创建',
        20, '热身 + 后续任务的基础');
```

## 关联状态机

参 [state-machines/task-state.mmd](../state-machines/task-state.mmd)。

## 跨表副作用

- `pending → in_progress` 时：写 `tasks.started_at`；**并触发 plan 状态机副作用**——若 `plans.status='active'`，由 service 同事务 `UPDATE plans SET status='adopted', adopted_at=now(), version=version+1`（见 [plan-status.mmd](../state-machines/plan-status.mmd) active→adopted 转移）。
- `in_progress → completed` 时：写 `tasks.completed_at` 和 `actual_minutes`。
- `in_progress / pending → abandoned` 时：写 `tasks.abandoned_at` 与 `abandoned_reason`（含 'other' 时必填 `abandoned_reason_text`）。
