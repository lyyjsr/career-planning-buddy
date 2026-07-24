# AI 渐进式加载指南

状态：本轮实现。

English summary: AI agents should load only the docs required by the task, then expand context if the change crosses boundaries.

本文件定义 AI Agent 如何按开发/评审场景加载规范文档。根入口 [AGENTS.md](../../AGENTS.md) 的必读路径表优先；本文件用于补充阅读顺序与场景路由。

---

## 基础加载

所有开发/评审场景至少先读：

- 根入口：[AGENTS.md](../../AGENTS.md)
- 本指南：[governance/ai-reading-guide.md](./ai-reading-guide.md)

如果涉及业务实现，再按开发/评审场景加载专题文档。

---

## 分类路由

| 一级目录 | 内容 | 何时读取 |
|---|---|---|
| `docs/overview/` | 项目定位、业务背景 | 理解需求归属时 |
| `docs/architecture/` | 六层分层、ADR、TDD、API 契约、技术点决策 | 进行架构设计或跨层改动时 |
| `docs/model-design/` | 单节点的正式 spec（输入/输出 schema/不变量/状态机） | 实现或评审某个 Agent 节点时 |
| `docs/standards/` | Python/FastAPI 编码规范、Spec 编写规范、安全、测试 | 编写或评审代码时 |
| `docs/governance/` | AI 阅读、开发流程、验证评审、门禁、阶段化交付 | 开始任务、提交变更或排查门禁时 |
| `docs/requirements/` | 任务级 clarify/plan/tasks 留痕 | 改动某个特性的代码或排查行为时 |
| `docs/third-party-integration/` | 外部供方协议、Provider 官方对接 | 接入 DeepSeek/Tavily 等 |
| `docs/design-input/` | 原始设计归档（非权威） | 回溯某条决策的出处时 |

---

## 规范读取路径（按场景路由）

| 开发/评审场景 | 必读文档 |
|---|---|
| 新增功能与领域建模 | [project-overview](../overview/product-overview.md)、[tdd §4](../architecture/tdd.md)、[adr](../architecture/adr.md)、[development-workflow](./development-workflow.md)、[use-case-development-checklist](./use-case-development-checklist.md) |
| Python/FastAPI 代码 | [python-coding-standards](../standards/python-coding-standards.md) |
| Agent 节点 / Tool spec | [spec-writing-guide](../standards/spec-writing-guide.md)、对应节点的 [model-design/agent-nodes/](../model-design/agent-nodes/README.md)（11 份）|
| API 与数据契约 | [api-and-data-contracts](../architecture/api-and-data-contracts.md)（协议）+ [model-design/api-spec/](../model-design/api-spec/README.md)（端点级） |
| 数据模型 / 表 | [model-design/data-models/](../model-design/data-models/README.md)（10 表 + ER 图）+ [contract-standard](../standards/contract-standard.md) |
| 状态机 | [model-design/state-machines/](../model-design/state-machines/README.md)（4 份 mmd + 合法转移） |
| Prompt 规范 | [standards/prompts/](../standards/prompts/README.md)（格式 + 版本化 + 评审）|
| 错误处理 | [error-handling-standard](../standards/error-handling-standard.md) |
| LLM / Provider 接入 | [adr §ADR-005](../architecture/adr.md)、[third-party-integration/](../third-party-integration/README.md) |
| 数据库与状态机 | [api-and-data-contracts](../architecture/api-and-data-contracts.md)、Alembic 迁移（代码仓） |
| 安全、审计与合规 | [security-and-compliance](../standards/security-and-compliance.md) |
| 测试与 TDD | [testing-and-tdd](../standards/testing-and-tdd.md) |
| 某特性的任务澄清/计划 | `docs/requirements/<feature>/clarify.md`、`plan.md`、`tasks.md` |
| 验证与评审 | [verification-and-review](./verification-and-review.md)、[use-case-development-checklist](./use-case-development-checklist.md) |
| 门禁排查 | [check-scripts-spec](./check-scripts-spec.md) |
| 当前状态与下一步 | 根 [README.md](../../README.md)；阶段编号见 [stage-delivery-definition](./stage-delivery-definition.md) |
| Spec-Driven 流程 | [spec-driven-workflow](./spec-driven-workflow.md) |

---

## 扩展规则

- 如果一个改动跨层，必须同时读 [tdd §3 六层架构](../architecture/tdd.md) 和 [python-coding-standards](../standards/python-coding-standards.md)。
- 如果一个改动写数据库，必须读 [api-and-data-contracts 状态机部分](../architecture/api-and-data-contracts.md)。
- 如果一个改动调 LLM/外部能力，必须读 [adr §ADR-005 Provider](../architecture/adr.md) 和 [security-and-compliance](../standards/security-and-compliance.md)。
- 如果改动涉及高风险分流、记忆写入、LLM 调用，必须读 [security-and-compliance](../standards/security-and-compliance.md) 的审计点。
- 不确定某规则归属时，先读 [development-workflow](./development-workflow.md) 定位。

---

## 输出要求

实现后说明：

- 本次加载了哪些专题文档。
- 是否新增或修改了分层边界、Schema、状态机、API、审计点。
- 已执行或无法执行的验证命令。
