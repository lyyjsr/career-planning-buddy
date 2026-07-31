# Agent 节点施工索引

项目共 10 个核心节点和 2 个增强节点。只有 `career_planning_agent` 是真 Agent。

## 核心节点

| 节点 | 类型 | Stage |
|---|---|---:|
| [risk_gate](./risk_gate.spec.md) | 程序规则 + 可选分类模型 | 2 |
| [safe_response](./safe_response.spec.md) | 固定安全响应 | 2 |
| [intent_router](./intent_router.spec.md) | 规则 + 单次结构化分类 | 2 |
| [clarification](./clarification.spec.md) | 程序节点 | 2 |
| [context_builder](./context_builder.spec.md) | 程序节点 | 2 |
| [career_planning_agent](./career_planning_agent.spec.md) | 唯一真 Agent | 2/3 |
| [rule_validator](./rule_validator.spec.md) | 确定性规则 | 2 |
| [revise_or_fallback](./revise_or_fallback.spec.md) | 路由/一次修复 | 2/3 |
| [companion_response](./companion_response.spec.md) | 模板优先，可选 LLM | 2/3 |
| [persist](./persist.spec.md) | Service 事务适配节点 | 2 |

## 增强节点

| 节点 | 类型 | Stage |
|---|---|---:|
| [distill_evidence](./distill_evidence.spec.md) | 搜索证据整理 | 4 |
| [quality_reviewer](./quality_reviewer.spec.md) | LLM Judge | 5 |

所有节点输入输出必须可序列化，不允许把 ORM Session 或厂商 Client 放进 Graph State。
