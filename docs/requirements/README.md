# requirements/ 目录入口

状态：本轮实现。

English summary: Per-feature spec-driven artifacts — clarify.md / plan.md / tasks.md persisted under docs/requirements/<feature>/.

## 定位

按需求实现的专题文档聚合区。每次跨模块 / 新增 API / 新增节点 / 改状态机的工作流产物（clarify / plan / tasks）落在 `docs/requirements/<feature>/` 单一目录。

## 与相邻目录的边界

- `model-design/` 是节点的正式 spec（设计依据）；本目录是这一次任务的澄清与计划。
- `architecture/` 是全局契约；本目录是针对某次改动的具体执行计划。
- `design-input/` 是历史归档；本目录是活跃的工作流产物。

## 目录约定

```text
docs/requirements/<feature>/
├── README.md                 文档地图（可选，feature 内文档多时加）
├── clarify.md                澄清问答 + 假设清单（前置）
├── plan.md                   实现计划（前置，必含 mermaid 交互流程图）
├── tasks.md                  任务清单（可选，带 [P] 并行标记）
└── <专题文档>.md             例如 state-machine.md / regression-report-*.md
```

`<feature>` 命名沿用需求主题（如 `agent-runtime-skeleton`、`risk-gate-node`），**禁止数字前缀**。

## 持久化判定

见 [governance/spec-driven-workflow.md](../governance/spec-driven-workflow.md) 的判定矩阵。简版：

| 改动类型 | Clarify | Plan | Tasks |
|---|---|---|---|
| Bug fix < 30 行 单模块 | 必做口头 | 否 | 否 |
| 单特性 / 触状态机 | 必做 | 是 | 可选 |
| 新增 API / 新增表 / 新增节点 | 必做 | 是 | 是 |
| 架构级 | 必做评审 | 是 | 是 |
| 实验 | 可省 | 否 | 否 |

## 当前状态

当前状态与下一步以根 [README.md](../../README.md) 为准；阶段编号以 [stage-delivery-definition.md](../governance/stage-delivery-definition.md) 为准。
