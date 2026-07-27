# Dazi 项目文档索引

| 项目 | 内容 |
|---|---|
| 项目名 | AI 规划搭子（Dazi） |
| 版本 | v2.0 |
| 状态 | 定稿（spec-driv­en 文档总入口，与仓库其它 README 同步维护）|
| 一句话定位 | 面向计算机学生的 AI 求职规划 Agent：单核心 Agent + 受控节点 + 证据驱动 + 执行反馈闭环 |
| 文档体系 | Spec-driven 开发——文档先于代码定稿，AI 开发按 spec 执行 |

English summary: This directory is the categorized source of truth for project context, architecture, per-feature design, coding standards, engineering governance, requirements artifacts, raw design input, and third-party integration materials. Project implementation skeleton (backend / frontend / infra / scripts) lives at repo root — see root [README.md](../README.md).

本根 README 按**主题分类**承载入口；具体开发/评审场景的必读路径见根 [AGENTS.md](../AGENTS.md)（英文）/ [AGENTS.zh-CN.md](../AGENTS.zh-CN.md)（中文）与 [governance/ai-reading-guide.md](./governance/ai-reading-guide.md)。

---

## 分类总览（八个一级目录）

| 目录 | 一句话定位 | 权威性 |
|---|---|---|
| [`overview/`](./overview/README.md) | 项目是什么：业务定位、统一术语、用例与用户旅程 | 权威 |
| [`architecture/`](./architecture/README.md) | 跨特性契约层：分层架构、ADR、API/数据契约、技术点决策矩阵、TDD | 权威 |
| [`model-design/`](./model-design/README.md) | 单特性的正式交互/接口设计稿：Agent 节点 spec、流程图、状态机、错误码 | 权威（特性设计依据） |
| [`requirements/`](./requirements/README.md) | 需求开发任务留痕：clarify/plan/tasks，按需求主题聚合 | 历史留痕 |
| [`standards/`](./standards/README.md) | 编码实现约束：Python 规范、FastAPI 模式、Pydantic、安全合规、测试 | 权威 |
| [`governance/`](./governance/README.md) | 工程治理：AI 阅读、开发流程、验证评审、架构强制、spec-driven | 权威 |
| [`third-party-integration/`](./third-party-integration/README.md) | 三方能力对接：外部供方协议、LLM Provider 协议、搜索/Embedding 对接 | 承接外部（非我方所有权） |
| [`design-input/`](./design-input/README.md) | 原始设计输入：早期 PRD/ADR/开发流程，追溯设计来源 | **非事实来源** |

> 一句话区分 **model-design** vs **requirements** vs **design-input**：看"我方某特性的节点/接口 spec"去 model-design；看"这次开发任务的澄清与计划"去 requirements；看"已归档的原始设计出处"去 design-input。

---

## 项目概览 `overview/`

用于理解项目为什么存在、面向什么用户、包含哪些业务场景。回答"是什么"。

- [产品概览 PRD v2.0](./overview/product-overview.md)
- [需求规格说明书 SRS](./overview/srs.md)
- [用户使用说明书](./overview/user-manual.md)
- [项目演示脚本](./overview/demo-walkthrough.md)
- [目录入口 README](./overview/README.md)（待补：统一术语表、限界上下文、用例追踪）

## 架构设计 `architecture/`

跨特性的**契约层与设计规则**单一事实来源：六层分层架构、ADR 决策、TDD 技术设计、API/数据契约、技术点决策矩阵。

- [架构设计目录入口](./architecture/README.md)
- [ADR 架构决策记录 v2.1](./architecture/adr.md)（9 条，G/T 模板 + ADR-009 LangGraph）
- [TDD 技术设计文档 v1.0](./architecture/tdd.md)
- [API 与数据契约 v1.0](./architecture/api-and-data-contracts.md)
- [AI 场景与风险分析](./architecture/ai-scenario-and-risk-analysis.md)
- [PoC 验证报告 v1.0](./architecture/poc-verification-report.md) — **Stage 0 前置 Provider PoC 退出物（进 Stage 0 前必读）**
- [技术点决策矩阵](./architecture/technology-decision-matrix.md)

## 模型与交互设计稿 `model-design/`

**施工级 spec**——给 AI 写代码直接照抄的"蓝图"。每个子目录有具体编法规范。

- [model-design 目录入口](./model-design/README.md)
- [端到端运行流程](./model-design/end-to-end-runtime-flow.md) — 启动、建档、规划、SSE、任务、复盘、记忆、安全分流的完整工程链路
- [知识库 / 数据设计说明](./model-design/data-seeding-and-sources.md) — 数据源、经验原子、RAG、种子数据、质量规则
- [前端页面使用流](./model-design/ui-spec/product-navigation.md) — PC/移动端导航、主路径、页面状态映射
- [Agent 节点 spec（11 份）](./model-design/agent-nodes/README.md) — 七要素：输入/输出/不变量/错误边界/状态机/副作用/Trace
- [数据模型 spec（10 表 + ER 图）](./model-design/data-models/README.md) — 完整字段/约束/索引/示例行
- [API 端点 spec（7 端点）](./model-design/api-spec/README.md) — 从 architecture/api-and-data-contracts.md 拆出
- [状态机 spec（4 份）](./model-design/state-machines/README.md) — mermaid 图 + 合法转移矩阵

## 编码规范 `standards/`

用于约束代码实现、安全、测试和评审质量，承接"怎么写代码"。

- [规范目录入口](./standards/README.md)
- [Python / FastAPI 编码规范](./standards/python-coding-standards.md)
- [Spec 编写规范](./standards/spec-writing-guide.md)
- [安全、审计与合规](./standards/security-and-compliance.md)
- [测试与 TDD](./standards/testing-and-tdd.md)

## 工程治理 `governance/`

用于指导 AI / 开发者与评审**如何在本仓库行动**。

- [AI 渐进式加载指南](./governance/ai-reading-guide.md)
- [AGENTS.md AI 协作宪章](./governance/AGENTS.md)
- [开发流程](./governance/development-workflow.md)
- [本地开发与调试手册](./governance/local-development-guide.md)
- [Spec-Driven 工作流（澄清→计划→任务）](./governance/spec-driven-workflow.md)
- [新增用例开发 Checklist](./governance/use-case-development-checklist.md)
- [验证与评审](./governance/verification-and-review.md)
- [门禁脚本规范](./governance/check-scripts-spec.md)
- [阶段化交付定义](./governance/stage-delivery-definition.md)

## 需求板块 `requirements/`

按需求实现的专题文档聚合区。每次跨模块 / 新增 API / 新增节点的工作流产物落在这里。

- [需求板块说明](./requirements/README.md)

## 三方能力对接 `third-party-integration/`

承接外部供方提供的协议、接口文档、中间件依赖和对接分析。

- [三方能力对接入口](./third-party-integration/README.md)

## 原始设计输入 `design-input/`

业务人员与架构设计人员提供的原始资料区，**不是事实来源**，仅用于追溯设计来源。

- [原始设计输入入口](./design-input/README.md)

---

## 核心决策摘要（3 分钟读完）

| 维度 | 决策 |
|---|---|
| 项目本质 | AI 应用开发（不是 Java 业务系统） |
| 后端 | FastAPI 单体（无 Java） |
| Agent | **1 个真 Agent（CareerPlanningAgent）+ 受控节点** |
| 数据存储 | PostgreSQL 16 + pgvector（无 Redis） |
| LLM | DeepSeek V4 主，五类 Provider Protocol 抽象 |
| MVP 场景 | 单一聚焦：计算机学生 AI/后端/Agent 求职 |
| 开发方式 | Spec-driven——文档先定稿，再用 AI 编程助手执行 |
| 开发节奏 | 8 个阶段化交付，按退出条件推进，不绑时间 |
| 工程护城河 | 六层 Harness + Trace/Replay/Eval + 5 维质量评分 |

---

## 权威关系

- 当前状态与下一步：以根 [README.md](../README.md) 为准。
- 阶段编号：以 [governance/stage-delivery-definition.md](./governance/stage-delivery-definition.md) 为准。
- API 路径、状态枚举、错误码：以 [architecture/api-and-data-contracts.md](./architecture/api-and-data-contracts.md) 为准。
- 端点、节点、数据表施工细节：以 [model-design/](./model-design/README.md) 为准，但不得覆盖 architecture 的契约。
- [design-input/](./design-input/README.md) 仅用于追溯，不作为事实源。

---

## 写作约定

- `docs/` 的一级目录表达文档类别；正式文档使用语义化文件名（不含数字前缀），设计输入归档保留原数字前缀。
- 每个一级目录必须有 `README.md`，描述本目录的**定位与边界**。
- 文档中文为主。
- 每篇文档只写自己的主题，跨主题使用可点击的相对链接，不复制大段规则。
- 移动或新增文档后必须同步更新根入口（`AGENTS.md` / docs/README / ai-reading-guide）和所有引用路径。
- 涉及代码事实时，以仓库当前实现为准；未落地的命令、模块、配置不得虚构。
- 每篇正式文档必须在首部声明状态：`定稿`、`本轮实现`、`规划中`、`已废弃`（`design-input/` 归档文档除外）。

---

## 文档变更原则

| 变更类型 | 处理 |
|---|---|
| 兼容性变更（细化、补充） | 直接改 + 版本号 minor |
| 破坏性变更（推翻决策） | 必须评审 + 写新版本 + 旧版本归档到 design-input |
| 发现 spec 错误 | 先改 spec 再改代码，不要在代码里绕过 spec |

---

## 当前阶段

当前状态与下一步以根 [README.md](../README.md) 为准；阶段编号以 [阶段化交付定义](./governance/stage-delivery-definition.md) 为准。
