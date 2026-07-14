# clarification.spec.md — 澄清节点

状态：本轮实现。

## 0. 节点定位

| 维度 | 内容 |
|---|---|
| 中文名 | 澄清节点 |
| 类型 | 程序节点（不调 LLM） |
| 工作流位置 | intent_router 后，缺关键槽位时触发 |
| 触发条件 | `IntentResult.needs_clarification == True` |
| 输出目标 | 返回用户 1 个澄清问题；用户答完后回 intent_router 重判 |
| 是否调 LLM | ❌ |
| 写权限 | ❌ |

## 1. 输入 Schema

`app.schemas.intent.IntentResult`（来自上一个节点）

主要读字段：`missing_slots`、`intent`、`goal_type`（context）

## 2. 输出 Schema

`app.schemas.intent.ClarificationRequest`

| 字段 | 类型 | 必填 | 约束 |
|---|---|---|---|
| `questions` | `list[str]` | ✅ | `min_length=1, max_length=3`；每条 `max_length=200` |
| `slot_names` | `list[str]` | ✅ | 与 questions 一一对应；值限定于枚举 `[goal, stage, time_budget, skill_level]` |
| `hint_options` | `dict[str, list[str]]` | ❌ | 给每槽位 2-4 个候选提示，`max_length=4` |

**示例**：
```json
{
  "questions": ["你希望秋招的目标方向是？"],
  "slot_names": ["goal"],
  "hint_options": {"goal": ["AI 后端", "Agent 应用", "数据分析"]}
}
```

## 3. 不变量

| ID | 不变量 |
|---|---|
| INV-1 | `len(questions) == len(slot_names)` |
| INV-2 | `set(slot_names) ⊆ {"goal","stage","time_budget","skill_level"}` |
| INV-3 | 任一 question 必须明确针对一个槽位（人工评审标准） |

## 4. 错误边界

| 错误 | 处理 |
|---|---|
| `missing_slots` 为空但 needs_clarification=True | 不应发生（INV 已守护），fail-fast |
| 用户连续 3 轮澄清仍缺槽 | 降级 query_plan，trace 记 `fallback_reason="clarification_overflow"` |

## 5. 状态机

节点无状态机；触发为 intent_router 的分支条件。

## 6. 依赖与副作用

| 依赖 | 对象 | 用途 |
|---|---|---|
| 配置 | `core/slots/slot_questions.py` | 槽位 → 模板问题映射 |
| Prompt 模板 | `prompts/clarification/v1.py`（可选：若问题需 LLM 润色） |
| 写 Trace | 节点一行 |

## 7. Trace 字段

| 字段 | 示例 |
|---|---|
| `node_name` | `"clarification"` |
| `slots_asked` | `["goal"]` |
| `questions_count` | `1` |
| `fallback_reason` | `null` 或 `"clarification_overflow"` |

## 8. 参考实现顺序

1. `schemas/intent.py` 加 `ClarificationRequest`
2. `core/slots/slot_questions.py` 4 槽位模板
3. `agent/nodes/clarification.py`（纯 Python 路由）
4. `tests/agent/test_clarification.py` 4 case

## 9. 引用

- [TDD §4.3 节点 3](../../architecture/tdd.md)
- [PRD §"消歧体验"要求](../../overview/product-overview.md)
