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
├── state-machines/                    状态机 spec（mermaid + 转移矩阵）
├── harness/                           Harness 反馈层 spec（Trace/Replay/Eval 总览 + 子 spec）
│   ├── README.md                      5 分钟入门（24 模块 + mermaid 全图）
│   ├── harness-overview.md            harness 总图（24 模块 + 四层模型 + Stage 映射）
│   ├── implementation-structure.md    施工总图（完整目录树 + import-linter 增强 + 生命周期钩子）
│   ├── replay.md                      Replay 机制（输入快照 / prompt 锁定 / diff）
│   └── eval-system.md                 Eval 数据集 / grader / 报告 / Bad Case / CI 门禁
│                                       (代码落地于 backend/app/evals/，与 harness/ 并列)
└── ui-spec/                           前端交互 spec（页面级）
    └── developer-trace.md             Trace / Replay / Eval / Bad Case 开发者页面
```

## 与相邻目录的边界

- `architecture/tdd.md` 定义六层 + 工作流整体；`model-design/agent-nodes/` 给每个节点的字段级 spec
- `architecture/api-and-data-contracts.md` 是 API/状态机的来源；`model-design/api-spec/` 把它拆为每端点一份（便于 AI 上下文聚焦）
- `architecture/tdd.md §11` 列表名；`model-design/data-models/` 给每张表完整字段+索引+约束+示例行
- `architecture/tdd.md §12` 概念性定义 Trace/Replay/Eval；`model-design/harness/` 把它们展开为字段级施工 spec（含新增表 `replay_runs` / `eval_cases` / `eval_runs` / `eval_cases_verdicts`）

## 读取顺序

写节点 N 的代码 → 读 `agent-nodes/N.spec.md` + 它引用的 `data-models/<表>.md` + `state-machines/<机>.mmd` + `api-spec/<资源>.md`。

写 Harness 反馈层代码（Stage 5）→ 读 `harness/harness-overview.md` 再分支到 `harness/replay.md` 或 `harness/eval-system.md` + 配套 `ui-spec/developer-trace.md`。
