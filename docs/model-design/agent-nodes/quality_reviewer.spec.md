# quality_reviewer.spec.md — 质量评分 LLM Judge 节点

状态：本轮实现。

## 0. 节点定位

| 维度 | 内容 |
|---|---|
| 中文名 | 质量评分 LLM Judge |
| 类型 | LLM Judge 节点（**不是 Agent**） |
| 工作流位置 | 第 8 步（rule_validator 之后或并行） |
| 模型 | DeepSeek 小模型 |
| Tool 权限 | ❌ 无 |
| 责任 | 跑维度 4（连续性）+ 编辑话术压力（若 fail） |

## 1. 输入 Schema

`app.schemas.validation.ReviewRequest`

| 字段 | 类型 | 必填 |
|---|---|---|
| `candidate` | `PlanCandidate` | ✅ |
| `yesterday_summary` | `str` | ✅ `max_length=500`（来自 history_stats_block） |
| `rubric_version` | `Literal["v1"]` | ✅ |

## 2. 输出 Schema

`app.schemas.validation.ReviewResult`

| 字段 | 类型 | 必填 |
|---|---|---|
| `dimension_4_continuity` | `Literal["pass","fail"]` | ✅ |
| `confidence` | `Annotated[float, Field(ge=0, le=1)]` | ✅ |
| `rationale` | `str` `max_length=200` | ✅ |
| `rewrite_prompt` | `str \| null` | ❌ 用于下一步 revise_or_fallback |

## 3. 维度 4 连续性的判定规则（LLM Rubric v1）

| 信号 | 判定 |
|---|---|
| 每个 task 引用了昨天的"完成" | pass |
| 每个 task 引用了昨天的"放弃"→ 调整/共情 | pass |
| 每个 task 引用了昨天的"阻碍"→ 提供解法 | pass |
| 完全无视 yesterday_summary | fail |
| 任务与昨天上下文互斥 | fail + rewrite_prompt |

## 4. 不变量

| ID | 不变量 |
|---|---|
| INV-1 | `dimension_4_continuity == "fail"` → `rationale` 非空 |
| INV-2 | `confidence < 0.7` 时视为"低置信 Judge"，不直接 fail |

## 5. 错误边界

| 错误 | 处理 |
|---|---|
| LLM 超时 | 跳过维度 4（视为 pass，trace 警告） |
| LLM schema 不符 | 重试 1 次 → 仍失败 → skip 维度 4 |

## 6. 状态机

无内部状态机。

## 7. 依赖

| 依赖 | 用途 |
|---|---|
| LLM Provider (Small) | 1 次调用 |
| Prompt | `prompts/quality_reviewer_rubric_v1.py` |
| 写 Trace | 1 行 |

## 8. Trace 字段

| 字段 | 示例 |
|---|---|
| `node_name` | `"quality_reviewer"` |
| `dim_4` | `"fail"` |
| `confidence` | `0.78` |
| `latency_ms` | `1140` |
| `cost_cny` | `0.0042` |

## 9. 实现顺序

1. `schemas/validation.py` 加 ReviewResult
2. `prompts/quality_reviewer/rubric_v1.py`
3. `agent/nodes/quality_reviewer.py`
4. `tests/agent/test_quality_reviewer.py` 3 case

## 10. 引用

- [PRD §7](../../overview/product-overview.md) 维度 4 + 话术压力
- [python-coding-standards.md](../../standards/python-coding-standards.md) LLM Judge 规则
