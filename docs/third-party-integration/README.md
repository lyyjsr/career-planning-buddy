# third-party-integration/ 目录入口

状态：本轮实现。

English summary: Third-party capability integration — external vendor protocols, LLM/Search/Embedding provider docs, alignment analyses.

## 定位

承接外部供方提供的协议、接口文档、中间件依赖和对接分析。这里记录"对方接口是什么"，不替代我方正式 spec（在 `model-design/`）。

## 与相邻目录的边界

- `model-design/` 是我方节点的正式 spec；本目录是对方提供的协议资料。
- `architecture/adr.md` 第 ADR-005 定义了五类 Provider Protocol 抽象；本目录承接具体 Provider 的官方对接资料。

## 文档（随阶段推进补齐）

| 文档 | 来源 | 阶段 |
|---|---|---|
| DeepSeek API 对接 | DeepSeek 官方 | 阶段 3 |
| Tavily Search 对接 | Tavily 官方 | 阶段 4 |
| pgvector 使用 | pgvector 官方 | 阶段 0-1 |

## 写作约定

承接外部供方接口/协议事实，**不适用**我方文档生命周期状态标记；本目录 Markdown 不加`状态：`行。
