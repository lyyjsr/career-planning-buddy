# 需求规格说明书 SRS

| 项目 | 内容 |
|---|---|
| 版本 | v1.0 |
| 状态 | 本轮实现 |
| 面向对象 | 产品负责人、开发者、AI 编程助手、评审者 |
| 定位 | 将 PRD 的目标、用户、功能边界、验收指标整理为可验收的需求规格；作为开发任务拆分和测试用例设计的上游依据 |

English summary: Software Requirements Specification for Dazi. It translates the PRD into testable user roles, functional scope, non-functional requirements, acceptance criteria, and traceability.

---

## 1. 文档定位

本文是 Dazi 的需求规格说明书。它回答“系统必须做什么、边界在哪里、如何验收”。

本文不替代：

| 文档 | 负责内容 |
|---|---|
| [product-overview.md](./product-overview.md) | 背景、目标、产品方案 |
| [user-manual.md](./user-manual.md) | 用户视角使用说明 |
| [end-to-end-runtime-flow.md](../model-design/end-to-end-runtime-flow.md) | 工程运行链路 |
| [api-spec/](../model-design/api-spec/README.md) | 单端点字段级契约 |
| [agent-nodes/](../model-design/agent-nodes/README.md) | 单节点输入输出和不变量 |

## 2. 项目背景与目标

Dazi 面向计算机学生求职准备场景，解决“信息过载、路径不清、计划过重、行动启动困难和执行中断后不会调整”的问题。

业务目标：验证单核心 Agent + 受控工作流 + 证据驱动规划，能否把分散信息收敛为用户今天愿意开始并完成的第一步，并形成“计划 → 执行 → 复盘 → 调整”的闭环。

北极星指标：

| 指标 | 定义 | MVP 目标 |
|---|---|---|
| 每周第一步完成率 | 过去 7 天内完成 ≥1 个 starter_action 的用户 / 7 天内生成过计划的用户 | ≥ 35% |

## 3. 用户角色

| 角色 | 描述 | 核心诉求 |
|---|---|---|
| 方向模糊型学生 | 知道想做后端/AI/Agent，但不了解能力差距 | 明确方向和阶段路线 |
| 计划过重型学生 | 每天列很多任务但难以启动 | 控制任务数量，给出起步动作 |
| 执行摇摆型学生 | 做几天后中断，不知道如何调整 | 根据执行反馈重规划 |
| 临近秋招型学生 | 距离投递/面试时间短 | 按优先级压缩路径 |
| 项目包装型学生 | 有项目但不会完善和表达 | 把项目包装拆成具体任务 |
| 开发者/评审者 | 查看 Agent 运行过程与质量 | Trace、Replay、Eval、Bad Case |

## 4. MVP 范围

MVP 首发场景：计算机学生 AI / 后端 / Agent 应用方向求职准备。

### 4.1 做

| 模块 | 功能 | 优先级 |
|---|---|---|
| 首次建档 | 收集 `goal_type`、阶段、每日可用时间 | P0 |
| 澄清补齐 | 关键信息缺失时追问 | P0 |
| 生成规划 | 生成整体方向、本周重点、今日 1-3 个任务 | P0 |
| 今日任务 | 开始、完成、放弃、记录阻碍 | P0 |
| 每日复盘 | 记录完成情况、阻碍、状态、调整意愿 | P0 |
| 重规划 | 根据复盘和任务执行情况调整计划 | P0 |
| 记忆管理 | 查看、关闭、删除记忆；确认/拒绝候选记忆 | P0/P1 |
| 来源与经验 | 使用联网/RAG/经验原子支持规划 | P0 |
| 安全分流 | 高风险输入进入固定支持话术 | P0 |
| 开发者 Trace | 查看 run、step、tool call、cost、fallback | Dev |

### 4.2 不做

| 不做 | 原因 |
|---|---|
| 不做原生移动 App | MVP 仅 Web，移动端做响应式 |
| 不做心理/医疗/法律/金融咨询 | 超出产品边界，高风险内容分流 |
| 不做多 Agent 系统 | 只有 CareerPlanningAgent 是真 Agent |
| 不做 Redis/Celery/K8s | MVP 单机 FastAPI + PostgreSQL 足够 |
| 不做完整后台管理系统 | Dev Trace 是调试页，不是运营后台 |
| 不承诺岗位信息 100% 准确 | 外部信息需来源标注和降级说明 |

## 5. 功能需求

### FR-01 首次建档

用户首次进入时，系统必须判断 profile 是否完整。

验收：

- 缺少 profile 时进入建档/澄清流程。
- 必填字段至少包含目标方向、当前阶段、每日可用时间。
- 建档成功后可进入规划入口。

### FR-02 澄清补齐

当用户发起规划但关键信息不足时，系统必须追问，而不是生成泛泛计划。

验收：

- SSE 返回 `clarification.requested`。
- 前端展示问题和可选提示。
- 用户补齐后可继续规划或更新 profile。

### FR-03 生成规划

系统必须根据用户请求、档案、记忆、历史任务、复盘和可用来源生成计划。

验收：

- `POST /api/v1/agent-runs` 返回 202 和 `events_url`。
- SSE 至少包含 `run.created`、`progress`、`plan.ready`、`run.completed`。
- 结果包含 1-3 个今日任务。
- 每个任务必须有 `starter_action`。

### FR-04 今日任务执行

用户必须能对今日任务执行开始、完成、放弃。

验收：

- 任务状态转移符合 `task-state.mmd`。
- 放弃任务必须能记录阻碍原因。
- 状态变更后前端同步更新。

### FR-05 每日复盘

用户必须能提交每日复盘，系统用复盘影响后续计划。

验收：

- 复盘保存到 `reviews`。
- 复盘可返回是否建议调整。
- 用户确认后可创建 replan run。

### FR-06 记忆管理

系统必须让用户看到并管理长期记忆和候选记忆。

验收：

- 用户可查看 active/closed memories。
- 用户可关闭或删除记忆。
- 敏感候选记忆必须由用户确认后才进入 active memories。

### FR-07 安全分流

系统必须识别高风险输入并进入固定分流路径。

验收：

- 高风险输入不进入普通规划链路。
- 不写入长期记忆。
- 返回固定支持话术和必要资源。
- Trace 记录分流结果。

### FR-08 开发者 Trace

开发者必须能查看一次规划运行的关键工程信息。

验收：

- 可查看 run 列表。
- 可查看 step 时间线。
- 可查看 tool call 摘要。
- 可查看成本、延迟、fallback reason。

## 6. 非功能需求

| 类别 | 要求 | MVP 目标 |
|---|---|---|
| 可用性 | 核心链路可在 PC 与移动端 Web 使用 | 响应式可用 |
| 性能 | 端到端规划延迟 | P95 ≤ 20s |
| 成本 | 单次 run 成本 | ≤ ¥0.2 |
| 可靠性 | Agent run 进入终态 | ≥ 95% |
| 结构化 | LLM 输出符合 schema | ≥ 98% |
| 安全 | 心理危机误判/漏判 | 0 |
| 可观测 | run/step/tool/cost/latency 可追踪 | Trace 完整 |
| 可测试 | Mock 与真实 Provider 共用契约测试 | Stage 2+ 必须 |

## 7. 验收指标

| 指标 | 类型 | 阶段 |
|---|---|---|
| `/health` 返回 200 | 工程 | Stage 0 |
| Pydantic/OpenAPI/DB schema 落地 | 契约 | Stage 1 |
| Mock plan_run 纵切跑通 | 功能 | Stage 2 |
| 真实模型 3 case 跑通 | AI | Stage 3 |
| 30 case Eval 通过率 ≥ 85% | AI 质量 | Stage 5 |
| 每周第一步完成率 ≥ 35% | 产品 | 上线后 |
| 计划过重率 ≤ 20% | 质量 | Stage 5+ |

## 8. 需求追踪矩阵

| 需求 | API | 表 | 节点/服务 | 测试建议 |
|---|---|---|---|---|
| FR-01 建档 | `PUT /profile` | `user_profiles` | ProfileService | profile schema + required slots |
| FR-02 澄清 | `POST /agent-runs` + SSE | `agent_steps` | intent_router / clarification | missing slot case |
| FR-03 规划 | `POST /agent-runs` | `agent_runs` / `plans` / `tasks` | 11 节点工作流 | Mock happy path |
| FR-04 任务 | `PATCH /tasks/{id}` | `tasks` | TaskService | 状态机转移测试 |
| FR-05 复盘 | `POST /reviews` | `reviews` | ReviewService | replan trigger case |
| FR-06 记忆 | `/memories` | `memories` / `memory_candidates` | MemoryService | candidate confirm/reject |
| FR-07 安全 | `POST /agent-runs` | `agent_steps` | risk_gate / safe_response | high-risk fixture |
| FR-08 Trace | `/dev/runs` | `agent_runs` / `agent_steps` / `tool_calls` | DevRunService | Trace read model |

## 9. 开放问题

| 问题 | 当前处理 |
|---|---|
| 中文岗位数据是否实时接入 | MVP 先用手工经验原子 + 开源职业技能库 + 少量岗位样本 |
| 真实模型 structured output 稳定性 | Pre-Stage 0 PoC 验证 |
| 移动端是否做独立 App | 不做，响应式 Web |
| Eval 数据集如何构建 | Stage 5 前补固定 30 case |

## 10. 关联文档

- [产品概览 PRD](./product-overview.md)
- [用户使用说明书](./user-manual.md)
- [端到端运行流程](../model-design/end-to-end-runtime-flow.md)
- [阶段化交付定义](../governance/stage-delivery-definition.md)
- [功能流程总览](../model-design/feature-flows/README.md)
