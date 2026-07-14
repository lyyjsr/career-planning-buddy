# trace-tables.md — Agent Trace 表（agent_runs / agent_steps / tool_calls）

状态：本轮实现。

> 三张表合一份 spec，因为它们是 Trace 链路父子结构。来源：[TDD §11.3](../../architecture/tdd.md) + [ADR Harness 五层](../../architecture/adr.md)。

## 1. agent_runs — 每次 plan_run 一行

| 字段 | 类型 | NULL | 默认 | 约束 | 说明 |
|---|---|---|---|---|---|
| id | `uuid` | NO | `gen_random_uuid()` | PK | run 全局 ID |
| user_id | `uuid` | NO | — | FK→users.id | —— |
| session_id | `uuid` | NO | — | —— | 会话 ID（多 run 共一会话） |
| status | `varchar(16)` | NO | `'pending'` | CHECK ∈ {`pending`,`running`,`completed`,`failed`,`degraded`} | 状态机见 state-machines/run-status.mmd |
| intent_result | `jsonb` | YES | NULL | —— | 来自 intent_router 节点 |
| final_plan_id | `uuid` | YES | NULL | FK→plans.id | 最终 plan（commit 后填） |
| total_cost_cny | `float` | NO | `0.0` | `Field(ge=0)` | 累计成本（含所有节点 token） |
| total_tokens_in | `integer` | NO | `0` | —— | |
| total_tokens_out | `integer` | NO | `0` | —— | |
| total_latency_ms | `integer` | NO | `0` | —— | start→end 总耗时 |
| fallback_reason | `varchar(64)` | YES | NULL | —— | 见 [verification-and-review.md §错误码](../../governance/verification-and-review.md)（未来的 standards/error-handling-standard.md） |
| created_at | `timestamptz` | NO | `now()` | —— | —— |
| started_at | `timestamptz` | YES | NULL | —— | 状态从 pending→running |
| finished_at | `timestamptz` | YES | NULL | —— | 状态到 completed/failed/degraded |

## 2. agent_steps — 每节点一行

| 字段 | 类型 | NULL | 默认 | 约束 | 说明 |
|---|---|---|---|---|---|
| id | `uuid` | NO | `gen_random_uuid()` | PK | —— |
| run_id | `uuid` | NO | — | FK→agent_runs.id ON DELETE CASCADE | —— |
| node_name | `varchar(64)` | NO | — | CHECK ∈ {11 节点名之一} | 节点名 |
| node_index | `integer` | NO | — | `Field(ge=0)` | 节点执行序号 |
| prompt_version | `varchar(64)` | YES | NULL | —— | 形如 `intent_router/v1`（R-Prompt1） |
| model | `varchar(64)` | YES | NULL | —— | 实际调用模型 |
| tokens_in | `integer` | NO | `0` | —— | |
| tokens_out | `integer` | NO | `0` | —— | |
| cost_cny | `float` | NO | `0.0` | —— | 本节点成本 |
| latency_ms | `integer` | NO | `0` | —— | 节点总耗时 |
| llm_latency_ms | `integer` | YES | NULL | —— | LLM 调用耗时（程序节点 NULL） |
| mock_mode | `varchar(16)` | YES | NULL | —— | 测试用 "happy"/"invalid"/"timeout" |
| fallback_reason | `varchar(64)` | YES | NULL | —— | 见标准 |
| success | `boolean` | NO | `true` | —— | false=未产生有效输出 |
| error_class | `varchar(64)` | YES | NULL | —— | Python 异常类名 |
| trace_data | `jsonb` | YES | NULL | —— | 节点专属 trace 字段（如 dim_1/dim_2、tool_calls_made 等） |
| created_at | `timestamptz` | NO | `now()` | —— | —— |

## 3. tool_calls — 每工具调用一行

| 字段 | 类型 | NULL | 默认 | 约束 | 说明 |
|---|---|---|---|---|---|
| id | `uuid` | NO | `gen_random_uuid()` | PK | —— |
| step_id | `uuid` | NO | — | FK→agent_steps.id ON DELETE CASCADE | 关联到节点（仅 career_planning_agent 触发） |
| run_id | `uuid` | NO | — | FK→agent_runs.id | 冗余便于 run 级查询 |
| tool_name | `varchar(64)` | NO | — | CHECK ∈ {`web_search`,`rag_retrieve`,`memory_lookup`,`context_summarize`} | TOOL 白名单 |
| round | `integer` | NO | — | CHECK between 1 and 2 | Agent 循环轮次 |
| args_hash | `varchar(64)` | NO | — | —— | sha256 参数 hash（不存原文敏感参数） |
| result_hash | `varchar(64)` | YES | NULL | —— | 结果 hash（用于 Replay） |
| result_token_count | `integer` | NO | `0` | —— | |
| latency_ms | `integer` | NO | `0` | —— | |
| success | `boolean` | NO | `true` | —— | |
| fallback_reason | `varchar(64)` | YES | NULL | —— | 如 `tool_timeout` |
| created_at | `timestamptz` | NO | `now()` | —— | —— |

## 索引

| 表 | 索引 | 用途 |
|---|---|---|
| agent_runs | idx_runs_user_status_started(user_id, status, started_at DESC) | 用户最近 run |
| agent_runs | idx_runs_status(status) WHERE status='pending' OR 'running' | 调度器扫待跑 |
| agent_steps | idx_steps_run_order(run_id, node_index) | run 内节点序输出 |
| tool_calls | idx_toolcalls_run(run_id, round) | run 内工具调用统计 |

## 示例行

```sql
-- 1 个 run
INSERT INTO agent_runs (id, user_id, session_id, status, total_cost_cny)
VALUES ('r-2a8f-...', 'u-7c3e2f1a-...', 's-9f4b-...', 'running', 0.0);

-- 3 个节点
INSERT INTO agent_steps (id, run_id, node_name, node_index, prompt_version, model,
                          tokens_in, tokens_out, cost_cny, latency_ms)
VALUES
  ('st-1-...', 'r-2a8f-...', 'risk_gate', 0, NULL, NULL, 0, 0, 0, 80),
  ('st-2-...', 'r-2a8f-...', 'intent_router', 1, 'intent_router/v1', 'deepseek-chat', 430, 62, 0.0021, 1180),
  ('st-3-...', 'r-2a8f-...', 'career_planning_agent', 2, 'career_planning_agent/v1', 'deepseek-v4', 3820, 1240, 0.0452, 22340);

-- 2 个 tool_calls（属于 career_planning_agent 步骤）
INSERT INTO tool_calls (id, step_id, run_id, tool_name, round, args_hash, result_token_count, latency_ms)
VALUES
  ('tc-1-...', 'st-3-...', 'r-2a8f-...', 'web_search', 1, 'sha:abc...', 620, 2840),
  ('tc-2-...', 'st-3-...', 'r-2a8f-...', 'rag_retrieve', 1, 'sha:def...', 410, 1820);
```

## 关联

- 完整 trace 字段定义在各节点 spec §7（如 [intent_router.spec.md §7](../agent-nodes/intent_router.spec.md)）
- 写入由 harness/ 负责（参 [TDD §12](../../architecture/tdd.md)）
- 敏感字段在 trace_data 内 hash 化（**绝不**入完整 prompt / API Key / 用户原文）
- Replay 重跑：相同 user_id + 相同 prompt_version + 相同 tool args_hash 重跑做 prompt A/B 对比
