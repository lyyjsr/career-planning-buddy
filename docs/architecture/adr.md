# ADR 架构决策记录 v3.0

| ADR | 决策 | 状态 |
|---|---|---|
| 001 | 独立 FastAPI 单体 + React SPA | Accepted |
| 002 | 单核心 Agent + 受控节点 | Accepted |
| 003 | 分层架构：API / Service / Repository / Agent / Provider / Harness | Accepted |
| 004 | PostgreSQL 16 + pgvector 作为唯一权威数据源 | Accepted |
| 005 | 运行时模型使用 OpenAI-compatible Provider，不绑定编码助手 | Accepted |
| 006 | Provider 只保留 LLM / Search / Embedding 三类 | Accepted |
| 007 | Agent Run 单 Worker 进程内执行，事件持久化后 SSE | Accepted with limitation |
| 008 | LangGraph 负责编排，确定性规则不交给 LLM | Accepted |
| 009 | Spec 驱动但以可运行纵切优先，禁止无限补文档 | Accepted |

## ADR-001：独立单体架构

### 决策

项目从零独立开发：

```text
React SPA → FastAPI → PostgreSQL/pgvector
                    → OpenAI-compatible LLM
                    → Search / Embedding Provider
```

不以 ClawAgent 为底座，不依赖其代码、数据库、工具协议和记忆实现。

### 原因

- 两人协作和秋招作品需要清晰的个人贡献边界；
- 单体便于调试、部署和演示；
- 当前规模不需要 Java 微服务或复杂基础设施。

### 演进触发

当出现任一条件再拆分：多团队独立发布、单模块吞吐成为瓶颈、需要独立安全边界。

## ADR-002：单核心 Agent + 受控节点

### 决策

只有 `CareerPlanningAgent` 可以在白名单内选择 Tool。风险判断、状态转移、规则校验、持久化和用户权限由确定性节点或 Service 负责。

### 原因

- 求职计划需要开放生成能力；
- 业务写入和安全边界必须稳定可测；
- 多 Agent 会增加调试和归因难度，MVP 没有必要。

## ADR-003：分层与依赖方向

```text
API → Service → Repository
          └→ Agent → Provider
          └→ Harness
```

- API 不直接访问 ORM；
- Agent 节点不直接写数据库；
- Provider 不暴露厂商 SDK 对象；
- Harness 负责事件、Trace、预算和评测。

## ADR-004：PostgreSQL + pgvector

### 决策

关系数据、Agent 运行记录、SSE 事件、记忆和向量统一放 PostgreSQL。

### MVP 不引入

Redis、MongoDB、Milvus、Qdrant、对象存储。

### 演进触发

- 多 Worker 可靠任务调度；
- 热点缓存带来明确收益；
- 向量数据量或检索延迟超过 PostgreSQL 能力；
- Trace Artifact 体积不适合数据库。

## ADR-005：编码助手与运行时模型分离

Codex 用于阅读规范、修改代码和执行测试，但不应进入运行时依赖图。

运行时统一配置：

```env
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=...
LLM_API_KEY=...
LLM_MODEL=...
LLM_ROUTER_MODEL=...
```

代码不得写死未经验证的模型项目代号，也不得把 Codex 当作运行时模型。Trace 只记录实际配置的 model id。

## ADR-006：三类 Provider

MVP 仅抽象：

```python
LLMProvider.complete(...)
SearchProvider.search(...)
EmbeddingProvider.embed(...)
```

Cache 和 ObjectStorage 不设空壳 Protocol。需要时再通过 ADR 增加。

## ADR-007：单 Worker 执行与 SSE

### 决策

- POST 创建 `agent_runs`；
- 进程内 `asyncio.Task` 执行 Graph；
- 每个事件先写 `agent_events`，再推送 SSE；
- `Last-Event-ID` 按 sequence 恢复；
- 启动时将超时的 pending/running Run 标记为 failed。

### 限制

该方案不提供跨进程任务接管。Docker 部署必须使用单 Uvicorn Worker。引入多 Worker 前，必须迁移到可靠队列或数据库抢占调度。

## ADR-008：LangGraph 编排

LangGraph 用于：条件路由、状态传递、Tool Calling 循环和节点 Trace。

不用 LangGraph 处理：数据库事务、权限、幂等、业务状态机和定时任务。

## ADR-009：文档服务于实现

文档必须足够让编码助手施工，但不得成为阻塞代码的无限前置工作。

执行原则：

1. 冻结当前阶段最小契约；
2. 用 Mock 跑通纵切；
3. 发现错误先改权威 spec；
4. 同步代码和测试；
5. 通过验收后进入下一阶段。
