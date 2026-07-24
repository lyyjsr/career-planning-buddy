# career_planning_agent.spec.md — 核心规划 Agent

状态：本轮实现。

> **唯一真 Agent**（R-Agent1）。其余节点命名严禁 `<X>Agent`，本节点是例外。

## 0. 节点定位

| 维度 | 内容 |
|---|---|
| 中文名 | 求职规划 Agent |
| 类型 | **真 Agent**（自主选择 Tool + 循环） |
| 工作流位置 | 第 5 步（context_builder 之后） |
| 模型 | DeepSeek V4（ADR-005 主选） |
| 是否可写业务表 | ❌ 不直接写（candidate 输出，写入由 persist 节点） |
| 循环上限 | **2 轮**，单轮 ≤4 工具调用，总计 ≤8 次 |
| 超时 | 30s 总预算 |
| 成本上限 | 单次 ≤ ¥0.15（占 run ¥0.2 的主要部分） |

## 1. 输入 Schema

`app.schemas.agent.PlanningAgentInput`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `run_id` | `str` | ✅ | run 全局 ID |
| `intent` | `Literal["create_plan","replan"]` | ✅ | 意图（query_plan 不走本节点） |
| `planning_context` | `PlanningContext` | ✅ | 来自 context_builder |
| `tool_specs` | `list[ToolSpec]` | ✅ | 已注册 Tool 白名单（见 §6） |
| `budget` | `AgentBudget` | ✅ | 见 §1.1 |

**§1.1 AgentBudget** 字段：

| 字段 | 类型 | 默认 | 约束 |
|---|---|---|---|
| `max_rounds` | `int` | `2` | `Field(ge=1, le=2)` |
| `max_tool_calls_per_round` | `int` | `4` | `Field(ge=1, le=4)` |
| `max_tool_calls_total` | `int` | `8` | `Field(ge=1, le=8)` |
| `max_cost_cny` | `float` | `0.15` | `Field(ge=0.01, le=0.5)` |
| `timeout_seconds` | `int` | `30` | `Field(ge=10, le=60)` |
| `tool_timeout_seconds` | `int` | `10` | `Field(ge=5, le=30)` |

## 2. 输出 Schema

`app.schemas.agent.PlanningAgentResult`

| 字段 | 类型 | 必填 | 约束 |
|---|---|---|---|
| `status` | `Literal["ok","degraded","failed"]` | ✅ | 3 值 |
| `candidate_plan` | `PlanCandidate \| null` | status=ok 时必填 | 见 PlanCandidate 部分定义 |
| `tool_calls_trace` | `list[ToolCallRecord]` | ✅ | 完整工具调用历史 |
| `rounds_used` | `Annotated[int, Field(ge=0, le=2)]` | ✅ | 实际使用轮数 |
| `tool_calls_used` | `Annotated[int, Field(ge=0, le=8)]` | ✅ | 实际调用次数 |
| `total_cost_cny` | `Annotated[float, Field(ge=0)]` | ✅ | 实际成本 |
| `fallback_reason` | `str \| null` | degraded/failed 时必填 | 见 §4 |
| `memory_candidates` | `list[MemoryCandidate]` | ❌ | Agent 提议的记忆候选（默认不写） |

**PlanCandidate 部分**：
| 子字段 | 类型 | 约束 |
|---|---|---|
| `today_tasks` | `list[TaskCandidate]` | `min_length=1, max_length=3` |
| `rationale` | `str` | `max_length=500` | Agent 必须给出计划依据 |
| `assumptions` | `list[str]` | `max_length=5` |

## 3. 不变量

| ID | 不变量 |
|---|---|
| INV-1 | `status == "ok"` → `candidate_plan` 必填 |
| INV-2 | `rounds_used <= max_rounds` |
| INV-3 | `tool_calls_used <= max_tool_calls_total` |
| INV-4 | `total_cost_cny <= max_cost_cny`（超预算触发 degraded） |
| INV-5 | 任一 tool_call 必须属于 `tool_specs` 白名单（防越权） |
| INV-6 | tool_call 选择只能来自 `[web_search, rag_retrieve, memory_lookup, context_summarize]`（4 个 MVP Tool） |
| INV-7 | 涉及写入意图的 tool_call → reject（R-IO2，由 harness 拦截） |
| INV-8 | `today_tasks` 每项必须含 `starter_action`（不可启动性维度 1） |

## 4. 错误边界

| 错误 | 触发 | 响应 | Trace |
|---|---|---|---|
| LLM 超时 | V4 超 5s/次或 30s 总计 | degraded + fallback_reason="llm_timeout" | 1 行 |
| LLM schema 不符 | structured output 验证失败 | 重试 ≤1 → degraded，fallback_reason="agent_schema_invalid" | 1 行 |
| 超轮（≥2 轮仍未收敛） | 信息仍不足 | degraded + fallback_reason="max_rounds_exhausted" | 1 行 |
| 超预算（>¥0.15） | budget checker 触发 | degraded + fallback_reason="budget_exceeded" | 1 行 |
| 危险 tool_call | harness 拦截 | 终止 + security alert + fallback_reason="unauthorized_tool_call" | 1 行 |
| 全部 fail | 多次重试失败 | 路由至 revise_or_fallback | — |

## 5. 状态机（Agent 主循环）

```mermaid
stateDiagram-v2
    [*] --> Observe: receive PlanningAgentInput
    Observe --> Decide
    Decide --> ToolPick: 需要更多信息
    ToolPick --> ToolExec
    ToolExec --> Observe
    Decide --> GenerateCandidate: 信息足够
    GenerateCandidate --> [*]: status=ok
    Decide --> CheckBudget: 工具次数/成本接近上限
    CheckBudget --> GenerateCandidate: 仍有预算
    CheckBudget --> FallbackDepleted: 无预算
    FallbackDepleted --> [*]: status=degraded, reason=budget_exceeded
    ToolExec --> ToolFailed: timeout/error
    ToolFailed --> Decide
```

## 6. 依赖与副作用

| 依赖 | 对象 | 说明 |
|---|---|---|
| LLM Provider | `DeepSeekV4Provider` | 唯一，不允许混小模型 |
| LangGraph | StateGraph checkpointer | PostgreSQL backend（断点恢复 R-ADR-009） |
| Tools 白名单 | 4 Tool（web_search / rag_retrieve / memory_lookup / context_summarize） | R-IO1：只读 |
| Harness | `BudgetChecker`、`ToolWhitelistGuard`、`ToolTimeout`、`TraceWriter` | 6 类要件 |
| Prompt 模板 | `prompts/career_planning_agent/v1.py` | System & Task prompt；**critical** |
| DB | ❌ 不直接写 | R-IO2 |
| LangSmith | 可选：调试 Trace | feature flag |

## 7. Trace 字段

每次 Agent 运行写 1 行 agent_steps + 多行 tool_calls：

| 字段 | 示例 |
|---|---|
| `node_name` | `"career_planning_agent"` |
| `prompt_version` | `"career_planning_agent/v1"` |
| `model` | `"deepseek-chat"` |
| `status` | `"ok"`/`"degraded"` |
| `rounds_used` | `1` |
| `tool_calls_used` | `3` |
| `total_tokens_in/out` | `3820`/`1240` |
| `latency_ms` | `22340` |
| `cost_cny` | `0.0452` |
| `fallback_reason` | `null` |
| `candidate_task_count` | `3` |

**tool_calls 子表（多行）**：

| 字段 | 示例 |
|---|---|
| `tool_name` | `"web_search"` |
| `args_hash` | `"sha256:..."`（不存原文 args） |
| `result_token_count` | `620` |
| `latency_ms` | `2840` |
| `success` | `true` |

## 8. 参考实现顺序

1. `schemas/agent.py`：PlanningAgentInput + AgentBudget + PlanningAgentResult + PlanCandidate + TaskCandidate
2. `schemas/intent.py` 已有 MemoryCandidate（如无则加）
3. `schemas/agent.py` 加 ToolCallRecord
4. `providers/llm/mock.py`：happy（带 candidate）/ budget_exceeded / max_rounds / schema_invalid / timeout 5 模式
5. `prompts/career_planning_agent/v1.py`（基础版 system+task+tool 描述）
6. `tools/registry.py` ToolSpec + 白名单 guard
7. `agent/state/plan_state.py` PlanState（TypedDict）
8. `agent/nodes/career_planning_agent.py` 主循环 + harness 调用
9. `tests/agent/test_career_planning_agent.py` 5 case

## 9. 引用

- [ADR-002](../../architecture/adr.md) 单 Agent 范式
- [ADR-005](../../architecture/adr.md) V4 主选
- [ADR-009](../../architecture/adr.md) LangGraph 编排 + Checkpointer
- [TDD §4.1](../../architecture/tdd.md) Agent 定义
- [TDD §6 Tool 系统](../../architecture/tdd.md)
- [TDD §7 上下文工程](../../architecture/tdd.md)
- [TDD §12 Harness 五层](../../architecture/tdd.md)
- [security-and-compliance.md §4 Prompt 注入防护](../../standards/security-and-compliance.md)
