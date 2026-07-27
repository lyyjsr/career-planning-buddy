# architecture/ 目录入口

状态：本轮实现。

English summary: Cross-cutting contracts — layered architecture, ADR, TDD, API/data contracts, technology decision matrix.

## 定位

跨特性的**契约层与设计规则**单一事实来源：六层分层架构、ADR 决策记录、TDD 技术设计、API/数据契约、技术点决策矩阵。本目录定义"系统应该长什么样"；单特性的节点 spec 落 `model-design/`，Python 编码层细节落 `standards/`。

## 与相邻目录的边界

- `model-design/` 是单特性的节点 spec（输入/输出 schema/不变量/状态机）；本目录是跨特性的全局契约。
- `standards/` 承接"怎么写 Python/FastAPI 代码"；本目录承接"架构怎么分层、什么技术栈、什么决策"。
- `design-input/` 保留旧版 ADR 作为决策演进资料，非权威。

## 文档清单

| 文档 | 作用 | 阶段定位 |
|---|---|---|
| [ADR v2.0](./adr.md) | 9 条核心技术决策 + 演进路径 | 阶段 2-4 |
| [TDD v1.0](./tdd.md) | 系统分层、Agent 设计、Harness、数据架构 | 阶段 4-5 |
| [API 与数据契约 v1.0](./api-and-data-contracts.md) | 接口路径、Schema、状态机、Payload 示例 | 阶段 4 |
| [AI 场景与风险分析](./ai-scenario-and-risk-analysis.md) | AI 适用场景、不可交给 AI 的边界、数据/Prompt/RAG/Agent 风险控制 | 阶段 2 |
| [PoC 验证报告 v1.0](./poc-verification-report.md) | Stage 0 前置 Provider PoC 退出物；7 个待验证假设（H1-H7） + Go/No-Go 矩阵 | **阶段 3** |
| [技术点决策矩阵](./technology-decision-matrix.md) | 每个技术点现在做/延后/不做 | 阶段 4 |

## 读取顺序

- **进 Stage 0 之前必读**：[PoC 验证报告](./poc-verification-report.md)（确认 Go 才开工）
- 新增功能时建议读：ADR → TDD → API 契约。决策依据看 ADR，实现细节看 TDD，接口字段看 API 契约。
