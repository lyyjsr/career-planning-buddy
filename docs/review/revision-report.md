# 设计稿一致性审查与修订报告

## 审查结论

原仓库包含较完整的产品、架构和 Agent 设计，但存在“文档数量多于可执行决策”的问题：技术选型和状态枚举重复、运行时模型与编码助手混淆、SSE 缺少持久事件事实源、计划状态含义冲突、开发阶段过多，以及若干历史外链和硬编码安全资源。

本次修订将其收敛为一个**独立实现的垂直求职规划项目**，明确不以 ClawAgent 为底座。

## 主要修订

1. 统一技术栈为 React + FastAPI + PostgreSQL/pgvector + LangGraph。
2. MVP 单体单 Worker，不引入 Redis、Celery、Kafka、MCP 或多 Agent。
3. Provider 收敛为 LLM/Search/Embedding 三类，先 Mock 后真实接入。
4. Codex 作为项目编码助手，不与运行时模型绑定。
5. Agent Graph 统一为 10 个核心节点和 2 个增强节点。
6. 新增 `agent_events`，定义 SSE sequence、持久化和断线补发。
7. Plan 状态统一为 generated/active/completed/archived，`adopted_at` 只是时间字段。
8. Review 的任务事实由服务端查询，不接受客户端伪造完成列表。
9. Guest 登录、用户隔离、事务、幂等、取消和超时契约补齐。
10. 高风险资源从配置读取，不在权威文档硬编码地区号码。
11. 开发计划收敛为 6 个可验收阶段，并增加可直接交给 Codex 的任务书。
12. 历史设计输入改为归档，只作追溯，不作为实现依据。

## 尚需团队在编码前确认

- 首个真实运行时模型及预算；
- Search/Embedding 供应商；
- Guest 账号未来是否升级正式账号；
- 高风险资源覆盖哪些目标地区；
- Demo 部署平台和域名。

这些未决项不阻塞 Stage 0~2，均可先用 Mock 和配置接口开发。

## 本次包内静态校验

- Markdown 内部相对链接：0 个失效；
- Markdown fenced code block：全部成对闭合；
- 历史设计文件名：已恢复为可读中文名称；
- 权威文档中：未保留硬编码地区热线、虚构运行时模型版本或旧五类 Provider 方案；
- 实现阶段：Stage 0~5 与任务书、治理文档和根 README 已对齐。

本次校验只针对设计文档。仓库尚无业务代码，因此没有声称编译、迁移或测试已通过。
