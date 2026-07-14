# companion_response.spec.md — 陪伴话术节点

状态：本轮实现。

## 0. 节点定位

| 维度 | 内容 |
|---|---|
| 中文名 | 陪伴反馈话术节点 |
| 类型 | LLM 单次调用（**不是 Agent**） |
| 工作流位置 | 第 10 步（候选 + 校验完成后） |
| 模型 | DeepSeek 小模型 |
| 责任 | 生成 6 触发时刻的对应话术 |

## 1. 6 触发时刻（产品决策，来自 TDD §10）

| ID | 触发条件 | 话术要求 |
|---|---|---|
| T1 | `mood <= 2` 且 tasks_completed > 0 | 共情优先 + 复盘情绪信号 |
| T2 | `consecutive_abandoned >= 2` | 减量 + 共情 + 不催促 |
| T3 | tasks_completed == plan_task_count | 完成庆祝（不加量！） |
| T4 | `time_budget_minutes < 60 && completed == 0` | 共情无产出，不评判 |
| T5 | `consecutive_completed >= 3` | 不加量（明确禁止陷阱） + 平稳鼓励 |
| T6 | 首次 plan_run（无 history） | 欢迎 + 期望校准（避免过度承诺） |

## 2. 输入 Schema

`app.schemas.companion.CompanionInput`

| 字段 | 类型 | 必填 |
|---|---|---|
| `run_id` | `str` | ✅ |
| `trigger_tag` | `Literal["T1","T2","T3","T4","T5","T6"]` | ✅ |
| `context_summary` | `str` | ✅ `max_length=1000` |
| `today_tasks` | `list[TaskCandidate]` | ✅ |
| `user_mood` | `Annotated[int, Field(ge=1, le=5)]` | ❌ |

## 3. 输出 Schema

`app.schemas.companion.CompanionMessage`

| 字段 | 类型 | 必填 |
|---|---|---|
| `message` | `str` | ✅ `max_length=500` |
| `trigger_tag` | `Literal["T1"-"T6"]` | ✅ |
| `tone` | `Literal["empathetic","encouraging","celebrating","calming"]` | ✅ |

## 4. 不变量

| ID | 不变量 |
|---|---|
| INV-1 | trigger_tag=T2 → tone ∈ {"empathetic","calming"} |
| INV-2 | trigger_tag=T3 → tone="celebrating" |
| INV-3 | 话术不得包含"我应该先..." 这种内疚诱导词 |
| INV-4 | 不得加量（与 PRD §8 红线一致） |

## 5. 错误边界

| 错误 | 处理 |
|---|---|
| LLM 超时 | 用 trigger_tag 取固定模板（fallback） |
| 话术触发 INV-* | reject + retry 1 → 模板兜底 |

## 6. 状态机

无状态机。

## 7. 依赖

| 依赖 | 用途 |
|---|---|
| LLM Provider (Small) | 1 次调用 |
| Prompts | `prompts/companion/v1.py`（按 6 触发分发） |
| Fallback 模板 | `core/companion_templates.py`（6 条硬编码话术） |

## 8. Trace 字段

| 字段 | 示例 |
|---|---|
| `node_name` | `"companion_response"` |
| `trigger_tag` | `"T2"` |
| `tone` | `"empathetic"` |
| `message_length` | `240` |
| `fallback_used` | `false` |

## 9. 实现顺序

1. `schemas/companion.py`
2. `core/companion_templates.py`（6 模板）
3. `prompts/companion/v1.py`
4. `agent/nodes/companion_response.py`
5. `tests/agent/test_companion.py` 6 case（覆盖每触发时刻）

## 10. 引用

- [PRD §4.2 陪伴](../../overview/product-overview.md) 业务级陪伴行为
- [PRD §8 调整红线](../../overview/product-overview.md) 不加量原则
- [TDD §10](../../architecture/tdd.md) 6 触发时刻
