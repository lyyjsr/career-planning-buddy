# requirements/ 目录入口

状态：本轮实现。

English summary: Per-feature spec-driven artifacts — clarify.md / plan.md / tasks.md persisted under docs/requirements/<feature>/.

## 定位

按需求实现的专题文档聚合区。每次跨模块 / 新增 API / 新增节点 / 改状态机的工作流产物（clarify / plan / tasks）落在 `docs/requirements/<feature>/` 单一目录。

## 与相邻目录的边界

- `model-design/` 是节点的正式 spec（设计依据）；本目录是这一次任务的澄清与计划。
- `architecture/` 是全局契约；本目录是针对某次改动的具体执行计划。
- `design-input/` 是历史归档；本目录是活跃的工作流产物。


## WBS 设计原则

本目录的 `<feature>` 以业务可感知功能为主组织，技术工作包下沉到 `tasks.md`。目标是让 SDD 产物既能追溯用户价值，也能直接指导 AI / 人类编码。

- 顶层 WBS = 用户可感知的业务功能，来源以 [PRD §6 功能清单](../overview/product-overview.md#6-功能清单) 和 [PRD §10.1 MVP 做](../overview/product-overview.md#101-mvp-做) 为准。
- 叶子任务 = 技术工作包，单包原则上不超过 3 天，并在 `tasks.md` 写清验收、依赖、API / 表 / 节点映射。
- 基础设施类单独成组，不混入业务功能：Docker、CI、脚手架、import-linter、`scripts/check.sh`、Provider PoC、契约冻结等属于工程组。
- 每个业务功能对应一个 SDD feature 目录；若功能很小，可合并到同一用户旅程下，避免按节点或代码层级碎片化。

## 顶层 WBS 建议

| WBS | 顶层功能 | 建议 feature 目录 | 类型 | 阶段锚点 | 说明 |
|---|---|---|---|---|---|
| 0 | 基础设施与工程基线 | `engineering-baseline` | 工程组 | Pre-Stage 0 / Stage 0 / Stage 1 | Provider PoC、目录骨架、Docker、CI、契约冻结、门禁脚本；不混入业务功能 |
| 1 | 首次建档与追问补齐 | `profile-onboarding` | 业务功能 | Stage 1 / Stage 2 | 采集 goal_type / stage / available_minutes，缺槽位走 clarification |
| 2 | 生成规划 Plan Run | `plan-generation` | 业务功能 | Stage 1 / Stage 2 / Stage 3 / Stage 4 | 创建 run、节点编排、规划生成、来源标注、5 维校验、SSE 事件、最小 Trace |
| 3 | 今日任务执行 | `today-task-execution` | 业务功能 | Stage 2 / Stage 6 | 今日任务展示、开始、完成、放弃、状态机与乐观锁 |
| 4 | 执行反馈闭环 | `execution-feedback-loop` | 业务功能 | Stage 6 | 每日复盘、复盘调整、次日续上，合并为一个闭环 feature |
| 5 | 记忆与用户控制 | `memory-user-control` | 业务功能 | Stage 6 | 记忆查看 / 删除 / 关闭、敏感记忆候选确认 |
| 6 | 安全分流与合规响应 | `safety-gate` | 业务功能 | Stage 3 / Stage 6 | 高风险识别、固定话术、12356、安全审计、不进长期记忆 |
| 7 | 陪伴话术与等待态反馈 | `companion-feedback` | 业务功能 | Stage 2 / Stage 6 | 6 个陪伴触发时刻、等待规划时的进度反馈 |
| 8 | 通用场景 fallback | `generic-goal-fallback` | 业务功能 | Stage 4 / Stage 6 | goal_type=other 的坦诚告知、通用模板、质量校验 |
| 9 | Harness 工程台 | `harness-workbench` | 工程/开发者功能 | Stage 1 / Stage 2 / Stage 5 | Trace / Replay / Eval / Bad Case 闭环；开发者可感知，但不归入普通用户业务功能 |
| 10 | 后台 CRUD | `admin-crud` | 管理功能 | P1 / Stage 7+ | 用户、计划、任务后台管理；MVP 可延后 |

## 技术工作包字段

每个 feature 的 `tasks.md` 中，叶子任务至少包含以下字段，避免只列技术动作而缺少验收依据。

| 字段 | 要求 |
|---|---|
| 工作包 | 以可交付产物命名，如 `AgentRunService 创建 run`、`POST /agent-runs 契约测试` |
| 验收 | 可运行 / 可检查，例如接口响应、状态转移、trace 行、测试 case |
| 依赖 | 上游 feature、API、表、节点或 Provider 假设 |
| 映射 | 关联 API spec、data model、agent node、state machine 文档 |
| 阶段 | 对齐 [stage-delivery-definition.md](../governance/stage-delivery-definition.md) 的阶段编号 |
| 预计 | 原则上 ≤3 天；超过则继续拆分 |

## 目录约定

```text
docs/requirements/<feature>/
├── README.md                 文档地图（可选，feature 内文档多时加）
├── clarify.md                澄清问答 + 假设清单（前置）
├── plan.md                   实现计划（前置，必含 mermaid 交互流程图）
├── tasks.md                  任务清单（可选，带 [P] 并行标记）
└── <专题文档>.md             例如 state-machine.md / regression-report-*.md
```

`<feature>` 命名沿用顶层 WBS 或工程组主题（如 `profile-onboarding`、`plan-generation`、`engineering-baseline`、`harness-workbench`），**禁止数字前缀**。

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
