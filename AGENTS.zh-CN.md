# AGENTS.zh-CN.md

| 版本 | v1.0 |
|---|---|
| 状态 | 已生效 |
| 作用 | AI Agent（Cursor / Claude Code / Codex）在本仓库工作的中文入口；只保留简洁规则和规范读取路径，动手前按场景加载对应 `docs/` 文档 |
| 优先级 | 高于任何单次对话指令；冲突时以本文件为准 |

English mirror: [AGENTS.md](./AGENTS.md)。完整释义宪法（更详细说明）：[docs/governance/AGENTS.md](./docs/governance/AGENTS.md)。

## 项目快照

`Dazi` 是一个**面向计算机学生的 AI 求职规划搭子**：单核心 Agent（CareerPlanningAgent）+ 受控节点工作流 + 六层 Harness + 证据驱动规划 + 执行反馈闭环。技术栈：FastAPI 单体 + React SPA + PostgreSQL 16 + pgvector + DeepSeek V4 + LangGraph。

**不是**：多 Agent 系统（只有 1 个真 Agent）、Java 业务系统、聊天机器人、demo。

当前状态与下一步：以根 [README.md](./README.md) 为准；阶段编号以 [stage-delivery-definition.md](./docs/governance/stage-delivery-definition.md) 为准。

## 规范读取路径

实现或评审前必须按场景读取：

| 开发/评审场景 | 必读文档 |
|---|---|
| 项目是什么 | [product-overview.md](./docs/overview/product-overview.md) |
| 架构决策 | [adr.md](./docs/architecture/adr.md) |
| 技术设计与六层分层 | [tdd.md](./docs/architecture/tdd.md) |
| API 与数据契约 | [api-and-data-contracts.md](./docs/architecture/api-and-data-contracts.md) |
| 技术点决策矩阵（现在做/延后/不做） | [technology-decision-matrix.md](./docs/architecture/technology-decision-matrix.md) |
| Python / FastAPI 编码规范 | [python-coding-standards.md](./docs/standards/python-coding-standards.md) |
| 怎么写 Agent 节点 / API spec | [spec-writing-guide.md](./docs/standards/spec-writing-guide.md) |
| 六层依赖边界与 import-linter | [tdd.md §3](./docs/architecture/tdd.md)、[python-coding-standards.md §1](./docs/standards/python-coding-standards.md) |
| Provider 协议与外部能力接入 | [adr.md §ADR-005](./docs/architecture/adr.md) |
| 数据库与状态机 | [api-and-data-contracts.md](./docs/architecture/api-and-data-contracts.md) |
| 安全、审计与合规 | [security-and-compliance.md](./docs/standards/security-and-compliance.md) |
| 测试与 TDD | [testing-and-tdd.md](./docs/standards/testing-and-tdd.md) |
| 单节点设计 spec（施工级，权威） | [docs/model-design/agent-nodes/](./docs/model-design/agent-nodes/README.md)（11 份节点 spec，各 7 要素） |
| 单表数据模型（施工级） | [docs/model-design/data-models/](./docs/model-design/data-models/README.md)（10 张表 + ER 图） |
| 单端点 API spec（施工级） | [docs/model-design/api-spec/](./docs/model-design/api-spec/README.md)（7 端点） |
| 状态机（单一事实源） | [docs/model-design/state-machines/](./docs/model-design/state-machines/README.md)（4 份 mmd + 合法转移矩阵） |
| Prompt 规范（Agent 项目独有） | [docs/standards/prompts/](./docs/standards/prompts/README.md) |
| 错误处理与降级 | [docs/standards/error-handling-standard.md](./docs/standards/error-handling-standard.md) |
| 契约规则（Pydantic + OpenAPI） | [docs/standards/contract-standard.md](./docs/standards/contract-standard.md) |
| Spec-Driven 工作流（澄清→计划→任务） | [spec-driven-workflow.md](./docs/governance/spec-driven-workflow.md) |
| 开发流程（纵切样例、模块落位） | [development-workflow.md](./docs/governance/development-workflow.md) |
| 新增用例 Checklist | [use-case-development-checklist.md](./docs/governance/use-case-development-checklist.md) |
| 验证与评审 | [verification-and-review.md](./docs/governance/verification-and-review.md) |
| 门禁脚本 | [check-scripts-spec.md](./docs/governance/check-scripts-spec.md) |
| 阶段化交付与退出条件 | [stage-delivery-definition.md](./docs/governance/stage-delivery-definition.md) |
| AI 渐进式加载策略 | [ai-reading-guide.md](./docs/governance/ai-reading-guide.md) |

完整分类索引见 [docs/README.md](./docs/README.md)。

## 不可违反规则（对应 AGENTS.md 的 RFC 2119 条款）

### 六层依赖边界
- **R-Layer1**：`import-linter` 守护层向。`app.api` 不得依赖 `app.repositories` 或 `app.models`；`app.agent` 不得依赖 `app.models`。强制者：`import-linter` → `scripts/check-architecture.sh`
- **R-Layer2**：Tool 只能依赖 Protocol / Service 接口，工具执行函数不得创建 DB 连接
- **R-Layer3**：`schemas` 与 `models` 分离；API 不得直接返回 ORM 对象；`app.providers` 不得向上暴露厂商特有响应对象

### 契约优先
- **R-Contract1**：先定 OpenAPI / Pydantic schema / 状态机 / Alembic 迁移，再实现 Router / Service / Prompt；不得从页面或 ORM 反推协议
- **R-Contract2**：破坏性 API 变更必须显式更新 OpenAPI snapshot

### 单 Agent 立场（重要）
- **R-Agent1**：只有 **1 个真 Agent**（CareerPlanningAgent）。`risk_gate` / `intent_router` / `rule_validator` / `quality_reviewer` / `distill_evidence` 都是节点
- **R-Agent2**：节点类不得命名为 `<X>Agent`（AIGOV 反模式 P-05：命名为 Agent 但没有 Harness）

### 权威数据单一
- **R-Data1**：PostgreSQL 是唯一业务事实源；进程内缓存只放可重建的临时数据
- **R-Data2**：MVP 阶段不得引入 Redis / Celery / K8s（除非触发 ADR-001 演进条件）

### 读写分离
- **R-IO1**：Agent 只能调只读工具（web_search / rag_retrieve / memory_lookup）
- **R-IO2**：所有写入经 persist 节点 + Service 事务；Agent 不得直接写业务表

### 失败显式化
- **R-Fail1**：不得静默吞错；降级必须带 `fallback_reason`；不保存半成品

### Prompt 是文件不是代码
- **R-Prompt1**：Prompt 模板放 `prompts/{goal_type}/*.py`，带版本号
- **R-Prompt2**：改 Prompt 必须新增版本号，不改旧版（便于 Replay 对比）

### 内容安全
- **R-Safety1**：高风险分流（关键词 + LLM 分类器）→ 固定话术 + 12356 → END，不进长期记忆
- **R-Safety2**：LLM 输出先审后发

### Spec-Driven 前置
- **R-Plan1**：非平凡代码（>30 行或 >2 文件）前必须 Clarify；命中持久化阈值（跨模块/改状态机/新增 API/新增表/新增节点/≥3 业务文件或 >50 行/架构级）必须写 `docs/requirements/<feature>/plan.md`，第 3 节必须含 mermaid 交互流程图
- **R-Plan2**：Bug fix < 30 行 + 单模块 + 不触状态机/schema/API 可跳过持久化，但仍需口头澄清一句

## 代码风格

- Python：`ruff` + `black` + `mypy --strict`（schemas、services 层）；snake_case（函数/变量），PascalCase（类）
- TypeScript（前端）：`eslint` + `prettier`，camelCase
- 所有公开函数 / 类 / Pydantic 模型有 docstring
- 所有 Pydantic 模型声明 `model_config = ConfigDict(extra="forbid")` 或显式 `extra="allow"`

## 禁止行为

| ❌ 禁止 | 理由 |
|---|---|
| 在 Prompt 里编造排查案例 | 用固定评测集 |
| 改 Schema 不改 OpenAPI snapshot | 破坏契约测试 |
| 写功能不写测试 | 测试随代码走 |
| 静默吞错 | 失败必须显式 |
| 让 LLM 直接写业务表 | Agent 只读 |
| 把节点叫 `<X>Agent` | 反模式 P-05 |
| MVP 阶段引入 Redis/Celery/K8s | 需触发 ADR-001 演进条件 |
| 引入 Java 后端 | 需触发 ADR-001 演进条件 |
| 把 Mock 数据混进真实统计 | Mock 必须带 `data_origin: "mock"` |

## 验证命令（不得发明命令）

- 全部门禁：`bash scripts/check.sh`
- Python 测试：`pytest`
- 架构测试：`import-linter --config backend/.importlinter.toml`
- 未在本文件或 `scripts/` 出现的构建 / 启动 / 部署命令不得虚构。

## 文档规则

- `docs/` 按主题分类为 `overview/`、`architecture/`、`model-design/`、`requirements/`、`standards/`、`governance/`、`third-party-integration/`、`design-input/`；文件名语义化；每个一级目录有自己的 `README.md`。完整索引：[docs/README.md](./docs/README.md)。
- `design-input/` 是原始归档，**不是事实来源**。
- 每篇正式文档必须声明状态（`定稿` / `本轮实现` / `规划中` / `已废弃`）；`design-input/` 与 `third-party-integration/` 除外。
