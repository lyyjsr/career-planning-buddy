# context_builder.spec.md — 上下文构建节点

状态：本轮实现。

## 0. 节点定位

| 维度 | 内容 |
|---|---|
| 中文名 | 上下文构建节点 |
| 类型 | 程序节点 |
| 工作流位置 | 第 4 步（在 clarification 和 career_planning_agent 之间） |
| 任务 | 按预算拼装 `PlanningContext` |
| 是否调 LLM | ❌（只调用 Tool + DB） |
| 是否可写业务表 | ❌ |

## 1. 输入 Schema

`app.schemas.context.BuildContextRequest`

| 字段 | 类型 | 必填 | 约束 |
|---|---|---|---|
| `user_id` | `str` | ✅ | UUIDv4 |
| `intent` | `Literal["create_plan","replan"]` | ✅ | 2 值 |
| `goal_type` | `GoalType` | ✅ | 6 值枚举 |
| `stage` | `Literal["early","mid","late","unknown"]` | ✅ | 求职阶段 |
| `time_budget_minutes` | `Annotated[int, Field(ge=15, le=480)]` | ✅ | 当日可用时间 |
| `skill_level` | `Literal["beginner","intermediate","advanced"]` | ❌ | 默认 `"intermediate"` |
| `context_budget_tokens` | `Annotated[int, Field(ge=2000, le=8000)]` | ✅ | 预算默认 `4000` |

## 2. 输出 Schema

`app.schemas.context.PlanningContext`（TDD §7.1 字段组）

| 字段 | 类型 | 必填 | 来源 |
|---|---|---|---|
| `profile_block` | `str` | ✅ | DB user_profiles |
| `recent_stats_block` | `str` | ✅ | service 统计近 7 天 |
| `memory_block` | `str` | ❌ | memory_lookup Tool |
| `experience_atoms_block` | `list[str]` | ❌ | rag_retrieve Tool |
| `search_results_block` | `list[str]` | ❌ | web_search Tool（仅 requires_fresh_information） |
| `history_summary_block` | `str` | ❌ | DB 最近 3 轮对话 |
| `token_breakdown` | `dict[str, int]` | ✅ | 每块实际占用 token 数 |

## 3. 不变量

| ID | 不变量 |
|---|---|
| INV-1 | `sum(token_breakdown.values()) <= context_budget_tokens` |
| INV-2 | `profile_block` 非空（P0 优先级不可缺） |
| INV-3 | `requires_fresh_information == False` 时 `search_results_block` 必须为 None/空 |
| INV-4 | 拼装优先级遵循 P0 → P3（TDD §7.1 表） |

## 4. 错误边界

| 错误 | 处理 |
|---|---|
| DB 读 user_profiles 失败 | fail-hard，不能进入 Agent；trace 记 `error_class="profile_unavailable"` |
| memory_lookup 超时 (>3s) | 该块置 None，继续拼装 |
| rag_retrieve 超时 (>3s) | 该块置 None |
| web_search 超时 (>8s) | 该块置 None，trace `fallback_reason="web_search_timeout"` |
| 所有可选块全 None | 仅 profile + intent 进 Agent，trace 警告 |

## 5. 状态机

节点本身无状态机；这是 LangGraph 纯数据准备节点。

## 6. 依赖与副作用

| 依赖 | 对象 | 说明 |
|---|---|---|
| 读 DB | `repositories.user.get_profile(user_id)` | 必读 |
| 读 DB | `repositories.run.get_recent_stats(user_id, days=7)` | service 聚合 |
| Tool 调用 | `tool_memory_lookup`、`tool_rag_retrieve`、`tool_web_search`、`tool_context_summarize` | 走 harness 包装 |
| Token 计数 | `core/token_counter.py` (tiktoken) | 精确预算 |
| Prompt 模板 | `prompts/context_builder/v1.py`（无 LLM 但拼装格式版本化） |

## 7. Trace 字段

| 字段 | 示例 |
|---|---|
| `node_name` | `"context_builder"` |
| `context_budget_tokens` | `4000` |
| `context_actual_tokens` | `3820` |
| `token_breakdown` | `{"profile": 280, "stats": 180, "memory": 1200, "atoms": 1400, "search": 600, "history": 160}` |
| `tool_calls_made` | `["memory_lookup","rag_retrieve","web_search"]` |
| `fallback_reason` | `null` 或 `"web_search_timeout"` |

## 8. 参考实现顺序

1. `schemas/context.py` PlanningContext + BuildContextRequest
2. `core/token_counter.py` tiktoken 包装
3. `agent/nodes/context_builder.py`
4. `tests/agent/test_context_builder.py`（happy/budget_overflow/web_timeout 3 case）

## 9. 引用

- [TDD §7 上下文工程](../../architecture/tdd.md) 设计依据
- [TDD §6.1 MVP Tool 清单](../../architecture/tdd.md) Tool 输入输出
