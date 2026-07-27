# dev-runs.md — 开发者 Run 端点

状态：本轮实现。

> Harnes 反馈层前置 spec。Dev 路径不参与外部业务，仅供开发者页（[ui-spec/developer-trace.md](../ui-spec/developer-trace.md)）查询/重跑。权限：管理员或 dev role（[ADR-001](../../architecture/adr.md)）。

## 端点：GET /api/v1/dev/runs

Run 列表（不限用户，全量）。

**Query 参数**：

| 参数 | 类型 | 默认 | 约束 |
|---|---|---|---|
| `user_id` | uuid? | null | 按用户过滤 |
| `status` | `pending/running/completed/failed/degraded/cancelled \| null` | null | |
| `intent` | IntentType? | null | |
| `started_after` / `started_before` | timestamp? | null | 时间范围 |
| `cursor` / `limit` | —— | 50 | limit `Field(ge=1, le=200)` |

**成功响应 200** `DevRunListResponse`：`{items: [DevRunSummary], next_cursor}`。

`DevRunSummary` 字段（trace 摘要）：`run_id / user_id（hash） / status / intent / total_cost_cny / total_latency_ms / started_at / finished_at / prompt_version（取首个 LLM 节点）/ fallback_reason`。

## 端点：GET /api/v1/dev/runs/{run_id}

Run 详情，含完整 trace 树。

**成功响应 200** `DevRunDetail`：

| 字段 | 类型 |
|---|---|
| run | DevRunSummary + 完整字段（user_id hash、prompt_version、模型名等） |
| steps | list[AgentStep]（按 node_index 排序） |
| tool_calls | list[ToolCall]（按 step_id 分组） |
| plan_snapshot | PlanDetail?（如已 commit） |
| trace_artifacts_url | str? | 完整 prompt 文本（独立加密存储）下载地址 |

**错误**：

| HTTP | code |
|---|---|
| 401 / 403 | AUTH_TOKEN_EXPIRED / AUTH_NOT_DEV |
| 404 | NOT_FOUND_RUN |

## 端点：POST /api/v1/dev/runs/{run_id}/replay

使用同输入（user_id + prompt_version + tool args_hash）重跑，做 prompt A/B 对比。**必填 Idempotency-Key**。

**请求 Schema** `ReplayRequest`：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `target_prompt_version` | str? | ❌ | 切换到指定 prompt 版本；缺省用原 run |
| `target_model` | str? | ❌ | 切换模型；缺省用原 run |
| `tool_args_overrides` | dict? | ❌ | 替换特定 tool_call 的 args_hash（已知的话） |

**成功响应 202** `ReplayAcceptedResponse`：

| 字段 | 类型 |
|---|---|
| `new_run_id` | str（新 run） |
| `replay_of_run_id` | str（原 run） |
| `events_url` | str |

> replay 的 run 在 `agent_runs.replay_of_run_id` 字段记录（建议 [trace-tables.md](../data-models/trace-tables.md) 补该字段——见阶段五全局对齐总览表 TODO）。

**错误**：

| HTTP | code |
|---|---|
| 401 / 403 | AUTH_TOKEN_EXPIRED / AUTH_NOT_DEV |
| 404 | NOT_FOUND_RUN |
| 409 | STATE_RUN_NOT_REPLAYABLE（原 run 仍在 running） |

## 关联

- 表：[trace-tables.md](../data-models/trace-tables.md)（agent_runs / agent_steps / tool_calls）
- 计划：[plans.md](./plans.md)
- UI：[ui-spec/developer-trace.md](../ui-spec/developer-trace.md)
- Harness：[harness/replay.md](../harness/replay.md)
