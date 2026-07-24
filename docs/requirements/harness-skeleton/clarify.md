# harness-skeleton 需求澄清

| 版本 | v1.0 |
|---|---|
| 日期 | 2026-07-24 |
| 状态 | 已实现 |
| 性质 | **回顾性留痕**——harness 5 份 spec 已编写完成（commit 99ebe8d / cda558e）；本文件是把当时的隐性决策显式化，作为 `governance/spec-driven-workflow.md` 的**首份真实范例** |

---

## 0. 为什么补这份 clarify

harness 反馈层 spec（Trace / Replay / Eval / 实施总图）是跨模块大改动——严格按 [`spec-driven-workflow.md`](../../governance/spec-driven-workflow.md) 判定矩阵应**先写 clarify + plan + tasks 再写 spec**。当时为快速推进，直接写了 5 份 spec，跳过了流程留痕。

**后果**：`requirements/` 一直空置，下次启动 Stage 0 时 AI / 开发者**无完整范例可参考**，会自己发挥风格导致 SDD 流程失控。

本文件 + `plan.md` + `tasks.md` 是"既成事实的回顾"——所有决策已在已编写完成的 spec 中固化，无新争议，仅梳理当时未显式记录的澄清问题与决议。

---

## 1. 待澄清问题与答复

### Q1：harness 是架构层还是功能实现层？

- **A**：两者都是。作为"工件总称"承载思想（让 LLM 非确定性可控）、编排流程（ReAct 循环）、体现架构（六层分层 + Provider 横切）。
- **来源**：用户提问（会话），定稿见 [harness-overview.md §0.1](../../model-design/harness/harness-overview.md)

### Q2：要把 Eval 代码嵌套在 `harness/eval/` 还是平级 `evals/`？

- **A**：**平级**（方案 A）。理由 4 条：
  1. Eval（离线 CI 批量）与 harness（运行时同步执行）生命周期 / 失败容忍度 / 入口 / 延迟要求不同
  2. import-linter 对子包粒度支持差，平级能精确守 `evals-isolation`（禁止运行时 import evals）
  3. 与 `stage-delivery` 节奏一致：Stage 2-3 只用 harness/，Stage 5 才上 evals/
  4. 与 TDD §3.3 + ADR-001 演进原则一致
- **来源**：用户确认（会话），定稿见 [implementation-structure.md §1](../../model-design/harness/implementation-structure.md)

### Q3：节点写 trace 是显式调用还是装饰器？

- **A**：**装饰器**。`@with_harness` 串起 trace + budget + lifecycle，节点代码只关心业务逻辑。
- **来源**：会话讨论，定稿见 [implementation-structure.md §6.5](../../model-design/harness/implementation-structure.md)

### Q4：Replay 重跑整条 plan_run 还是只重跑从 career_planning_agent 起？

- **A**：**只从 career_planning_agent 起**。理由：前置节点（risk_gate / intent_router / context_builder）的输出已被 trace 记录，99% Prompt 改动集中在 agent 节点；若 override 了前置节点则从该节点起跑。
- **来源**：会话讨论，定稿见 [replay.md §2.2](../../model-design/harness/replay.md)

### Q5：Eval 数据集初始多少 case？

- **A**：**30 case**。分布：normal 10 / replan 5 / fallback_other 3 / high_risk 3 / budget_limited 3 / edge 3 / bad_case 3+。Stage 3-5 渐进补齐，Stage 5 跑通后启用 Bad Case 闭环持续增长。
- **来源**：会话讨论，定稿见 [eval-system.md §2.5](../../model-design/harness/eval-system.md)

### Q6：Eval 进 CI 的硬阈值是多少？

- **A**：**pass_rate ≥ 85% + 无 silent regression**（已通过 case 翻 fail 即阻断）。
- **来源**：与 [`check-scripts-spec.md §5`](../../governance/check-scripts-spec.md) 严禁项同步

### Q7：Replay / Eval API 是否产线暴露？

- **A**：**绝不**。所有 `/api/v1/dev/*` 路由 production env 启动时 `assert env != production` 失败，前端 dev 路由 guard 重定向 404。
- **来源**：会话讨论，定稿见 [implementation-structure.md §2](../../model-design/harness/implementation-structure.md) 原则 6

### Q8：harness/README.md 与 harness-overview.md 角色边界？

- **A**：README 砍到 ~45 行作**目录入口**（与其他子目录 README 形态一致），overview 含"5 分钟入门 + 施工细节"（约 450 行）。两者不重叠。
- **来源**：用户问"为什么两个 README"，定稿见 [harness/README.md](../../model-design/harness/README.md)

---

## 2. 未决假设

> 当时实际是一次次推进中做出的决策，本节回顾登记当时承担的隐性假设。

| 假设 | 风险 | 现状 |
|---|---|---|
| Replay 的 fixture 库会自动扩充 | 不自动——需开发者手工补 fixture | Stage 5 才落地，未定脚本；已在 `replay.md §3.2` 风险点显式说明 |
| Eval 30 case 由用户手填 | 用时可能不够 | Stage 3 启动时补 10 个 normal，Stage 4 补 11，Stage 5 补 9；已写进 [eval-system.md §8](../../model-design/harness/eval-system.md) |
| `@with_harness` 装饰器实现复杂度可控 | ReAct 循环节点比线性节点复杂 | Stage 2 落地时验证 |

---

## 3. 引用

- 上游需求：[ADR-008 工程治理](../../architecture/adr.md) + [TDD §12 Harness](../../architecture/tdd.md)
- 流程：[`governance/spec-driven-workflow.md`](../../governance/spec-driven-workflow.md) + [`governance/AGENTS.md`](../../governance/AGENTS.md) R-Plan1
- 产物：[`harness-overview.md`](../../model-design/harness/harness-overview.md) · [`implementation-structure.md`](../../model-design/harness/implementation-structure.md) · [`replay.md`](../../model-design/harness/replay.md) · [`eval-system.md`](../../model-design/harness/eval-system.md) · [`ui-spec/developer-trace.md`](../../model-design/ui-spec/developer-trace.md)
