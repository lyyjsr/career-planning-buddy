# model-design/ 目录入口

状态：本轮实现。

English summary: Construction-level design specs for AI to write code. Each subdir has its own format: node specs (7 elements), data models (full table + er-diagram), api-spec (per-endpoint contract), state-machines (mermaid + transition matrices).

## 定位

**施工级 spec**——给 AI 写代码直接照抄的"蓝图"，不是给人看决策层。

差异：
- `architecture/` 答"为什么这么设计" → 给人看的决策记录（ADR/TDD/API）
- `standards/` 答"怎么写代码" → 通用规则
- `model-design/` 答"具体某节点/某表/某接口长什么样" → 字段级施工图纸，给 AI 抄

## 子目录

```
model-design/
├── README.md                          本文件（索引）
├── agent-nodes/                       Agent 节点 spec（10 份）
│   ├── README.md                      spec 编写规则在 standards/spec-writing-guide.md
│   ├── intent_router.spec.md
│   ├── risk_gate.spec.md
│   ├── context_builder.spec.md
│   ├── career_planning_agent.spec.md  唯一真 Agent
│   ├── distill_evidence.spec.md
│   ├── rule_validator.spec.md
│   ├── quality_reviewer.spec.md
│   ├── companion_response.spec.md
│   ├── persist.spec.md
│   └── safe_response.spec.md
├── data-models/                       数据库表 spec（每表一份 + ER 全图）
├── api-spec/                          API 端点 spec（每资源一份）
└── state-machines/                    状态机 spec（mermaid + 转移矩阵）
```

## 与相邻目录的边界

- `architecture/tdd.md` 定义六层 + 工作流整体；`model-design/agent-nodes/` 给每个节点的字段级 spec
- `architecture/api-and-data-contracts.md` 是 API/状态机的来源；`model-design/api-spec/` 把它拆为每端点一份（便于 AI 上下文聚焦）
- `architecture/tdd.md §11` 列表名；`model-design/data-models/` 给每张表完整字段+索引+约束+示例行

## 读取顺序

写节点 N 的代码 → 读 `agent-nodes/N.spec.md` + 它引用的 `data-models/<表>.md` + `state-machines/<机>.mmd` + `api-spec/<资源>.md`。
