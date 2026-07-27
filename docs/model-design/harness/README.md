# harness/ Harness 反馈层 spec 入口

| 版本 | v1.1 |
|---|---|
| 日期 | 2026-07-24 |
| 状态 | 草稿 |

English summary: Reflection-layer specs of the harness — overview (24 modules × repo mapping) + Replay mechanism + Eval system (dataset / grader / Bad Case loop / CI gate). Source of truth for AI writing `backend/app/harness/` code.

## 定位

harness = "模型权重之外的一切"。本子目录把 [TDD §12](../../architecture/tdd.md) 概念性提到的 **Trace / Replay / Eval** 三大反馈层能力展开为字段级施工 spec，覆盖原 [trace-tables.md](../data-models/trace-tables.md) 之外的 **E3 / E4 / F2 / F3 / F4** 五个模块。

本子目录与相邻目录的边界：

- `data-models/trace-tables.md` 定义 Trace 三张表（E1）的字段——本目录在其上**扩展** Replay/Eval/Dev Dashboard 的新表与机制
- `agent-nodes/rule_validator.spec.md` + `quality_reviewer.spec.md` + `revise_or_fallback.spec.md` 是 inline 校验回路（F1）——本目录的 Eval 系统是 offline 回归（F2~F4）
- `governance/check-scripts-spec.md` 定义 CI 脚本骨架——本目录的 [eval-system.md §6](./eval-system.md) 定义 check-eval.sh 在 Eval 上的判定规则

## 文件清单

| 文件 | 内容 | 关联模块 |
|---|---|---|
| [harness-overview.md](./harness-overview.md) | harness 总图：5 分钟入门（mermaid）+ 24 模块映射 + 对标 + Stage 时序 | 全部 |
| [implementation-structure.md](./implementation-structure.md) | 施工总图：完整目录树 + 三要素表 + import-linter 增强 + 生命周期钩子 + 专业术语对应 | 全部 |
| [replay.md](./replay.md) | Replay 机制：输入快照重建、prompt_version 锁定、diff 报告、`replay_runs` 表 | E3 |
| [eval-system.md](./eval-system.md) | Eval 数据集 schema + 6 grader + 4 表 + Bad Case 回流 + CI 门禁（**代码落地于 `backend/app/evals/`，与 harness/ 并列**） | F2 / F3 / F4 |

## 跨子目录协同

| 同层 spec | 关系 |
|---|---|
| [../ui-spec/developer-trace.md](../ui-spec/developer-trace.md) | 本目录定义后端 API + 表，UI spec 定义前端（Trace/Replay/Eval/Bad Case 入口） |
| [../data-models/trace-tables.md](../data-models/trace-tables.md) | 是本目录 Replay 与 Eval 的输入来源（agent_runs/steps/tool_calls） |
| [../state-machines/run-status.mmd](../state-machines/run-status.mmd) | 是本目录 Replay 的并发约束依据（pending/running 不可 Replay） |

## 读取顺序

- 第一次接触 harness → 先读 [harness-overview.md §0 5 分钟入门](./harness-overview.md)
- 写 harness 代码（Trace/Budget/Checkpoint/Replay） → 读 [implementation-structure.md](./implementation-structure.md) → [replay.md](./replay.md)
- 写 Eval 代码 → 读 [implementation-structure.md §3 evals/](./implementation-structure.md) → [eval-system.md](./eval-system.md)
- 写开发者页前端 → 读 [../ui-spec/developer-trace.md](../ui-spec/developer-trace.md)

## 实施时序

本子目录所有 spec 属 Stage 5 退出条件（[governance/stage-delivery-definition.md](../../governance/stage-delivery-definition.md)）；其中数据表迁移（`replay_runs` + eval_* 四表）属 Stage 1 契约冻结。
