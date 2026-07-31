# Agent Runtime 表

## agent_runs

| 字段 | 类型 | NULL | 说明 |
|---|---|---:|---|
| id | uuid | NO | PK |
| user_id | uuid | NO | FK users.id |
| idempotency_key | varchar(64) | NO | 与 user_id 联合唯一 |
| request_text | text | NO | 用户原始请求，按敏感数据保护 |
| hint_intent | varchar(32) | YES | 前端提示 |
| resolved_intent | varchar(32) | YES | 服务端判定 |
| goal_type_override | varchar(32) | YES | |
| source_plan_id | uuid | YES | replan 来源 |
| replay_of_run_id | uuid | YES | Replay 来源 |
| status | varchar(16) | NO | pending/running/completed/degraded/failed/cancelled |
| final_plan_id | uuid | YES | 成功计划 |
| model_id | varchar(128) | YES | 实际 runtime model id |
| total_tokens_in/out | integer | NO | default 0 |
| total_cost_cny | numeric(12,6) | NO | default 0 |
| total_latency_ms | integer | NO | default 0 |
| fallback_reason | varchar(64) | YES | |
| risk_category | varchar(32) | YES | |
| deadline_at | timestamptz | NO | |
| created_at/started_at/finished_at | timestamptz | mixed | |

约束：

- UNIQUE `(user_id, idempotency_key)`；
- partial unique：同用户最多一个 pending/running；
- `final_plan_id` 在计划持久化后填写。

## agent_steps

| 字段 | 类型 | 说明 |
|---|---|---|
| id | uuid | PK |
| run_id | uuid | FK agent_runs.id ON DELETE CASCADE |
| sequence | integer | 节点执行顺序 |
| node_name | varchar(64) | 不做易漂移的 DB CHECK，应用枚举校验 |
| attempt | integer | 默认 1 |
| status | varchar(16) | running/completed/failed/skipped |
| prompt_version | varchar(64) nullable | |
| model_id | varchar(128) nullable | |
| tokens_in/out | integer | |
| cost_cny | numeric(12,6) | |
| latency_ms | integer | |
| trace_data | jsonb | 脱敏信息 |
| error_code/error_message | varchar/text nullable | |
| created_at/finished_at | timestamptz | |

UNIQUE `(run_id, sequence)`。

## tool_calls

| 字段 | 类型 | 说明 |
|---|---|---|
| id | uuid | PK |
| run_id | uuid | FK |
| step_id | uuid | FK |
| tool_name | varchar(64) | 白名单 |
| round | integer | 1..2 |
| args_json | jsonb | 脱敏参数 |
| args_hash | varchar(64) | Replay key |
| result_preview | text nullable | 截断摘要 |
| result_hash | varchar(64) nullable | |
| latency_ms | integer | |
| success | boolean | |
| error_code | varchar(64) nullable | |
| created_at | timestamptz | |

## agent_events

| 字段 | 类型 | 说明 |
|---|---|---|
| id | uuid | PK |
| run_id | uuid | FK agent_runs.id ON DELETE CASCADE |
| sequence | integer | Run 内单调递增，SSE id |
| event_type | varchar(64) | dot notation |
| payload_json | jsonb | 必含 run_id、sequence |
| created_at | timestamptz | |

UNIQUE `(run_id, sequence)`；索引 `(run_id, sequence)`。

SSE 断线续传以本表为事实源，不依赖内存消息队列。
