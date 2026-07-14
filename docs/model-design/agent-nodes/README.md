# agent-nodes/ 节点 spec 入口

状态：本轮实现。

English summary: One *.spec.md per Agent node. Per `standards/spec-writing-guide.md` seven elements: Input Schema, Output Schema, Invariants, Error Boundary, State Machine, Dependencies/Side Effects, Trace Fields. Authoritative design basis for AI writing node code.

## 节点 spec 列表（共 11 份）

| 节点 | 类型 | 复杂度 | spec 文件 |
|---|---|---|---|
| intent_router | LLM 单次分类 | 低 | [intent_router.spec.md](./intent_router.spec.md) |
| risk_gate | 规则节点 | 极低 | [risk_gate.spec.md](./risk_gate.spec.md) |
| clarification | 程序节点 | 低 | [clarification.spec.md](./clarification.spec.md) |
| context_builder | 程序节点 | 中 | [context_builder.spec.md](./context_builder.spec.md) |
| **career_planning_agent** | **真 Agent** | **高** | [career_planning_agent.spec.md](./career_planning_agent.spec.md) |
| distill_evidence | 程序节点 | 中 | [distill_evidence.spec.md](./distill_evidence.spec.md) |
| rule_validator | 程序节点 | 中 | [rule_validator.spec.md](./rule_validator.spec.md) |
| quality_reviewer | LLM Judge | 中 | [quality_reviewer.spec.md](./quality_reviewer.spec.md) |
| revise_or_fallback | 路由节点 | 低 | [revise_or_fallback.spec.md](./revise_or_fallback.spec.md) |
| companion_response | LLM 单次调用 | 低 | [companion_response.spec.md](./companion_response.spec.md) |
| persist | 事务节点 | 中 | [persist.spec.md](./persist.spec.md) |
| safe_response | 程序节点（安全兜底） | 极低 | [safe_response.spec.md](./safe_response.spec.md) |

## 写作规则（七要素）

参 [standards/spec-writing-guide.md](../../standards/spec-writing-guide.md) §七要素。

## 命名约束（R-Agent2）

只有 `career_planning_agent` 是 Agent。其他节点命名严禁后缀 `Agent`。
