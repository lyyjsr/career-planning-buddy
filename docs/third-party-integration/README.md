# third-party-integration/ 目录入口

状态：本轮实现。

English summary: Third-party capability integration — external vendor protocols, LLM/Search/Embedding provider docs, alignment analyses.

## 定位

承接外部供方提供的协议、接口文档、中间件依赖和对接分析。这里记录"对方接口是什么"，不替代我方正式 spec（在 `model-design/`）。

## 与相邻目录的边界

- `model-design/` 是我方节点的正式 spec；本目录是对方提供的协议资料。
- `architecture/adr.md` 第 ADR-005 定义了五类 Provider Protocol 抽象；本目录承接具体 Provider 的官方对接资料。

## 文档清单

| # | 文档 | 状态 | 阶段 |
|---|---|---|---|
| H01 | [DeepSeek API 对接](./deepseek-api.md) | 已补 v1.0 | 阶段 3 PoC 直接依赖 |
| H02 | Tavily Search 对接（[待补]） | 占位 | 阶段 4 |
| H03 | pgvector 使用（[待补]） | 占位 | 阶段 0-1 |

## 写作约定

承接外部供方接口/协议事实；不适用我方文档生命周期状态标记，但**每份对接 spec 自带版本/状态字段**便于追踪 spike 前后变化。
