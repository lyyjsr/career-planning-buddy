# standards/ 目录入口

状态：本轮实现。

English summary: How to write code — Python/FastAPI coding standards, Pydantic schema rules, security/compliance, testing/TDD, spec writing.

## 定位

承接"怎么写代码"。只承接编码约束规则与 spec 编写规范；架构/接口结构的设计规则以 `architecture/` 为单一事实来源。

## 与相邻目录的边界

- `architecture/` 定义分层架构；本目录定义各层内的 Python 代码应该怎么写。
- `governance/` 定义流程与门禁；本目录定义代码质量标准。
- `model-design/` 是写完的 spec；本目录的 `spec-writing-guide.md` 定义怎么写。

## 文档

| 文档 | 作用 |
|---|---|
| [Python / FastAPI 编码规范](./python-coding-standards.md) | 各层（L1-L6）的代码约束、Pydantic 规则、import 边界 |
| [Spec 编写规范](./spec-writing-guide.md) | Agent 节点 / API spec 的**七要素**模型与模板 |
| [安全、审计与合规](./security-and-compliance.md) | Prompt 注入防护、敏感记忆、内容审核、降级链 |
| [测试与 TDD](./testing-and-tdd.md) | pytest 分层、契约测试、故障注入、Eval |
| [契约规范](./contract-standard.md) | Pydantic v2 + OpenAPI snapshot + 字段约束 + 兼容性 |
| [错误处理与降级规范](./error-handling-standard.md) | 错误分类、降级/fail 判定、fallback_reason 命名、重试策略 |
| [Prompt 规范（子目录）](./prompts/README.md) | Prompt 格式 / 版本化 / 评审检查表（Agent 项目独有） |

## 读取顺序

写代码前先读 `python-coding-standards.md` + `contract-standard.md`；写 spec 前先读 `spec-writing-guide.md`；写 Agent 节点（涉及 Prompt）再读 `prompts/`；涉及敏感数据先读 `security-and-compliance.md`；涉及错误处理读 `error-handling-standard.md`；写测试前先读 `testing-and-tdd.md`。
