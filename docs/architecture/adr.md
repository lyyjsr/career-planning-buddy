# ADR 架构决策记录 v2.1

| 项目 | 内容 |
|---|---|
| 文档版本 | v2.1 |
| 日期 | 2026-07-12 |
| 状态 | 定稿 |
| 决策者 | 项目维护组 |
| 关联 | [PRD v2.0](../overview/product-overview.md)、[TDD v1.0](./tdd.md)、[API 契约 v1.0](./api-and-data-contracts.md)、[技术点决策矩阵](./technology-decision-matrix.md) |
| 变更说明 | v2.0 → v2.1：① 统一采用 G/T ADR 模板（Status / Context / Decision / Consequences / Alternatives）；② 新增 ADR-009 LangGraph 编排器选型，解开 ADR-001 / ADR-002 内容纠缠；③ 颗粒度对齐；④ 修正规范链接 |

> **模板约定**：每条 ADR 必须自包含——读者无需阅读其它 ADR 即可理解本条决策上下文、决策结果与代价。决策结果的具体执行细则见 [TDD](./tdd.md)；本文件**只记录"为什么这么决定"**。

> DeepSeek V4 是项目选型候选称呼；代码配置、Trace 示例与 PoC 实测必须使用官方 model id（当前为 `deepseek-chat`），不得把项目代号当作真实 model id。

---

## 总览：9 条核心架构决策

| ADR | 决策主题 | 结论 | 状态 |
|---|---|---|---|
| [ADR-001](#adr-001整体架构与服务边界) | 整体架构与服务边界 | FastAPI 单后端 + React SPA + PostgreSQL；MVP 无 Java/Redis/队列 | Accepted |
| [ADR-002](#adr-002agent-编排在单个-agent-与多-agent-之间选择单-agent--受控节点) | Agent 编排范式 | 单核心 Agent（CareerPlanningAgent）+ 受控节点 | Accepted |
| [ADR-003](#adr-003分层架构在分层方案中选择六层--provider-横切) | 分层架构 | 六层（Types→Config→Repository→Service→Runtime→API/UI）+ Provider 横切 | Accepted |
| [ADR-004](#adr-004数据存储在数据库方案中选择-postgresql--pgvector) | 数据存储 | PostgreSQL 16 + pgvector；不引入 Redis/独立向量库/对象存储 | Accepted |
| [ADR-005](#adr-005llm-与-provider在模型厂商与抽象层中选择-deepseek-v4--五类-provider-protocol) | LLM 与 Provider | DeepSeek V4 主选 + 五类 Provider Protocol 抽象 | Accepted（待 v4 spike 验证）|
| [ADR-006](#adr-006记忆系统五类分层--敏感内容用户确认) | 记忆系统 | 五类记忆分层 + pgvector 检索 + 敏感记忆用户确认 | Accepted |
| [ADR-007](#adr-007并发与运行-fastapi-async--sse--background-tasks) | 并发与运行 | FastAPI async + 202/SSE + Background Tasks | Accepted |
| [ADR-008](#adr-008工程治理spec-driven--阶段化交付--门禁脚本) | 工程治理 | Spec-Driven 五段式 + 阶段化交付 + 门禁脚本 + Docker Compose | Accepted |
| [ADR-009](#adr-009agent-编排器选型-langgraph-优于-autogen--自研循环) | Agent 编排器实现 | LangGraph 1.x（优于 AutoGen / 自研 ReAct 循环） | Accepted |

---

## ADR-001：整体架构与服务边界

| 项目 | 内容 |
|---|---|
| Status | Accepted |
| Date | 2026-07-11 |

### Context（为什么需要做这个决策）

项目定位为 AI 求职规划 Agent 应用，核心价值在 Agent 层（推理 / 检索 / 规划 / 校验闭环），不在 Web 业务吞吐。MVP 团队规模 ≤3 人，交付窗口 4 周。决策点：后端是 Python 单服务、Java + Python 双服务，还是 Node 单服务。

### Decision

**FastAPI 单后端（Python 3.11+）+ React SPA + PostgreSQL，MVP 不引入 Java / Redis / 任务队列。**

判断依据：

| 因素 | 判断 |
|---|---|
| 项目定位 | AI 应用，价值在 Agent 层，不在业务 CRUD |
| 业界参考 | Dify / FastGPT / LangGraph template / Open-Assistant 均为 Python 单后端 |
| 团队与窗口 | 双服务联调成本不可控；单服务让精力集中在 Agent 工程深度 |
| Spec-driven AI 开发 | 单后端让 AI 上下文一致；双服务增加 spec 跨语言对齐成本 |

### Consequences（正面 / 负面 / 中性）

- ✅ 正面：单一技术栈、单一门禁链、AI 上下文一致、Agent 工程深度可堆叠
- ⚠️ 负面：业务并发上限受 Python 单体约束；缺企业级 Java 生态（银行/政务对接）
- ➖ 中性：演进必须显式触发，见下表

### 演进触发条件

| 组件 | 何时引入 |
|---|---|
| Redis | 日活 >500 且 plan_run P95 > 15s；或需要分布式锁/限流 |
| 任务队列 | plan_run 平均 > 30s 且需要跨进程恢复；或需要定时抓取 |
| Java 业务服务 | 接入企业级 Java 业务体系；或团队扩展 Java 工程师 |
| 独立向量库 | 向量数据 > 1000 万条且 pgvector P95 > 500ms |
| K8s | 日活 > 5000 且需要弹性扩缩容 |

### Alternatives（已否决）

| 方案 | 否决理由 |
|---|---|
| Java + Python 双服务 | 业务不在吞吐瓶颈；联调成本无收益 |
| 纯 Spring AI（Java） | LangGraph 生态在 Python；AI 岗不认 Java 主语 Agent |
| Node.js 后端 | LangChain/LangGraph 主语是 Python；Node 在 Agent 生态较弱 |

---

## ADR-002：Agent 编排——在单个 Agent 与多 Agent 之间选择单 Agent + 受控节点

| 项目 | 内容 |
|---|---|
| Status | Accepted |
| Date | 2026-07-11 |

### Context

PRD 把"诊断 → 搜索蒸馏 → 规划 → 校验"四步抽象成多个环节。决策点：每步封装成独立 Agent（多 Agent 系统），还是用单个真 Agent + 一组受控节点（编排工作流）。参考 LangGraph 官方多 Agent 判定标准："Multi-agent is for when sub-tasks have different tool sets and need parallel execution."

### Decision

**单核心 Agent（CareerPlanningAgent）+ 受控节点工作流。不做多 Agent。**

四维判定：

| 维度 | 多 Agent 才合理的条件 | 本项目是否符合 |
|---|---|---|
| 独立工具集 | 各 Agent 有专属不共享工具 | ❌ 共享 web_search / rag / memory |
| 并行执行 | 多 Agent 同时跑省时 | ❌ 顺序流水线 |
| 独立停止条件 | 各有不同"完成"判据 | ❌ 节点间传结构化输出 |
| 独立权限边界 | 不同 Agent 不同写权限 | ❌ 全部只读 |

### Consequences

- ✅ 正面：可调试（Trace 单链路）、可解释（每节点显式输入输出）、可收敛（循环受预算约束）
- ✅ 正面：面试可讲清楚"为什么不是多 Agent"——优于"装多 Agent 但无 Harness"的反模式
- ⚠️ 负面：未来出现并行/独立工具集需求时需重构（演进条件见下）
- ➖ 中性：节点命名严禁 `<X>Agent`（避免 AIGOV P-05 反模式）

### 演进触发条件

| 何时考虑 Supervisor-Worker / 多 Agent |
|---|
| 出现真实并行需求（多求职方向对比、多用户聚合并行） |
| 子任务出现独立工具集与独立停止条件 |

### Alternatives

| 方案 | 否决理由 |
|---|---|
| 4 Agent（诊断/搜索/计划/校验） | 不满足多维判定；命名 Agent 但无 Harness |
| Supervisor-Worker | 当前无并行/独立工具集需求 |
| ReAct 开放循环 | 不可控，循环难收敛 |

> Agent 编排**器**实现选型见 [ADR-009](#adr-009agent-编排器选型-langgraph-优于-autogen--自研循环)；Agent 自身设计（节点表 / PlanState / 循环约束）见 [TDD §4](./tdd.md)。

---

## ADR-003：分层架构——在分层方案中选择六层 + Provider 横切

| 项目 | 内容 |
|---|---|
| Status | Accepted |
| Date | 2026-07-11 |

### Context

后端代码切几层？决策点：传统三层（Controller/Service/DAO）够不够、要不要用 DDD 全套、Agent 项目独有的 Runtime 能力（Harness / Tool / Eval）放哪里。参考：Clean Architecture（依赖倒置）、Hexagonal（Port & Adapter）、Harness Engineering（Anthropic）。

### Decision

**六层（L1 Types → L2 Config → L3 Repository → L4 Service → L5 Runtime → L6 API/UI）+ Providers 横切。这是 Clean Architecture 依赖倒置的 Python 落地，轻量引入 DDD 战术设计（值对象 = L1 Types、Repository 接口 = L3）。**

### Consequences

- ✅ 正面：Agent 工程化能力独立成 L5 Runtime，不污染业务层也不被业务层污染——这是 Agent 项目区别于普通 Web 项目的关键
- ✅ 正面：分层约束用 import-linter 变为机器可校验门禁，比"靠 review 守纪律"更可靠
- ⚠️ 负面：六层目录对新成员有学习曲线；阶段 0 起步成本高于三层
- ➖ 中性：初期可先用 LangGraph template 的 3 层（graph/state/tools）跑通纵切，再扩展到六层

### Alternatives

| 方案 | 否决理由 |
|---|---|
| 三层（api/service/dao） | Runtime / Tool / Harness / Provider 无处安放，会塞进 Service 导致业务与模型调用混杂 |
| DDD 全套战略 + 战术 | 个人项目过重；限界上下文映射成本 > 收益 |
| 六边形架构独立实践 | 与六层本质等价，但与 Python 生态契合度更低 |

> 每层允许/禁止内容、机械约束、Python Protocol 代码、与 DDD/Clean Architecture 对应关系见 [TDD §3 六层依赖架构](./tdd.md)。

---

## ADR-004：数据存储——在数据库方案中选择 PostgreSQL + pgvector

| 项目 | 内容 |
|---|---|
| Status | Accepted |
| Date | 2026-07-11 |

### Context

需要同时存储关系型业务事实（用户 / 计划 / 任务 / 复盘）、向量（memory embedding / experience_atoms embedding）、Agent Trace（JSON）、Prompt 模板（文件）、短期会话上下文。决策点：用 PostgreSQL + pgvector 一锅端，还是引入 Redis + Qdrant/Milvus + MongoDB 的多组件栈。

### Decision

**PostgreSQL 16 + pgvector 作为唯一权威数据源；MVP 不引入 Redis / 独立向量库 / 对象存储 / MongoDB。**

数据归属：业务事实 / 向量 / Trace / 短期会话上下文全部落入 PostgreSQL；缓存走进程内 `lru_cache`；Prompt 模板走文件系统（`prompts/{goal_type}/*.py`）以便独立版本化。

一致性：所有 plan_run 使用 `Idempotency-Key` 幂等，乐观锁 `version` 字段，单次 plan_run 一个事务。

### Consequences

- ✅ 正面：单一数据源、单组件运维、事务跨关系型 + 向量数据可用
- ✅ 正面：Alembic 迁移统一管理 schema 演进
- ⚠️ 负面：大数据量向量检索性能受 pgvector 上限约束（> 1000 万条需演进）
- ⚠️ 负面：单实例无分布式锁——并发上限由进程内限流承载

### 演进触发条件

| 组件 | 何时引入 |
|---|---|
| Redis 缓存/锁 | 日活 > 500 且 P95 不可控；或需要分布式限流 |
| 独立向量库（Qdrant/Milvus） | 向量数据 > 1000 万条且 pgvector P95 > 500ms |
| 对象存储 | 出现文件 / 截图上传需求 |

### Alternatives

| 方案 | 否决理由 |
|---|---|
| Redis 缓存 | MVP 规模不需要；PostgreSQL + 进程缓存足够 |
| Qdrant/Milvus 独立向量库 | pgvector 够用，不增加运维组件 |
| MongoDB | 关系型数据为主，事务 + 联表多，PostgreSQL 更合适 |

---

## ADR-005：LLM 与 Provider——在模型厂商与抽象层中选择 DeepSeek V4 + 五类 Provider Protocol

| 项目 | 内容 |
|---|---|
| Status | Accepted（待 v4 spike 验证）|
| Date | 2026-07-11 |

### Context

需要为 6 类模型用途（意图分类、Agent 推理、经验蒸馏、质量评分、Embedding、内容安全）选定厂商与抽象层。约束：国内合规（不出境）、单次 plan_run 成本 ≤ ¥0.2、Provider 可替换（降级链）。决策点：用单厂商 + Protocol 抽象，还是多厂商混搭。

### Decision

**DeepSeek V4 主选 + 五类 Provider Protocol 抽象（LLM / Search / Embedding / Cache / ObjectStorage）。所有外部能力通过 Protocol 接口隔离，Mock 与真实实现共享同一契约测试集。**

分层调用：简单节点（intent_router / quality_reviewer / 内容安全）用 DeepSeek 小模型省钱；核心规划（CareerPlanningAgent / distill_evidence）用 V4 保质量；Embedding 用同厂 Embedding 便于 RAG。

降级链：LLM `DeepSeek V4 → GLM-4.5 → 模板`；Search `Tavily → 缓存 → 经验库`；Embedding 不可降级（失败即拒）。

### Consequences

- ✅ 正面：Provider 可替换，模型演进（换 GPT-5、换 Claude）只改 Provider 实现
- ✅ 正面：Mock 与真实实现共享契约测试，阶段 2 纵切可用 Mock 全链路跑通
- ⚠️ 负面：DeepSeek V4 的结构化输出稳定性、5 维评分通过率尚未实测——**ADR-005 标"待 spike 验证"，spike 结果可能推翻选型**
- ⚠️ 负面：单厂商绑定风险（API 限流 / 价格变动）由降级链 + Protocol 抽象对冲

### 待验证假设（spike 优先级 P0）

| 假设 | 怎么验证 |
|---|---|
| V4 能稳定输出 IntentResult / PlanCandidate schema | 5-10 case 实测，目标通过率 ≥ 98% |
| 5 维质量评分 ≥ 85% 通过率 | 5-10 case 实测 |
| 单 run 总成本 ≤ ¥0.2 | token 估算 × DeepSeek 单价 + Tavily 单价 × query 数 |

### Alternatives

| 方案 | 否决理由 |
|---|---|
| OpenAI GPT-4o | 贵 + 数据出境合规 |
| 多家模型混搭 | 增加复杂度，单 Provider + 降级链够用 |
| 自部署开源模型 | 单卡推理 + 运维成本 > 调 API |

> 五类 Provider Protocol 代码定义见 [TDD §3.2.1](./tdd.md)；分层调用与 token 预算见 TDD §7 上下文工程、TDD §14 成本控制。

---

## ADR-006：记忆系统——五类分层 + 敏感内容用户确认

| 项目 | 内容 |
|---|---|
| Status | Accepted |
| Date | 2026-07-11 |

### Context

要做到"陪伴"产品行为（PRD §4.2），需要用户长期记忆。但记忆有两类风险：① 敏感内容（健康 / 财务 / 家庭 / 强烈情绪）直接写入有合规风险；② LLM 自由写记忆会造成噪声 / 偏见累积。决策点：记忆要不要分层、敏感内容默认是否写入。

### Decision

**五类记忆分层 + pgvector 语义检索 + 敏感记忆默认不写入、用户确认后才进长期记忆。**

| 类型 | 写入规则 | 检索方式 |
|---|---|---|
| 画像事实 | 用户明确提交后写入 | 每次规划直接读取 |
| 稳定偏好 | 多次行为或用户明确表达 | 影响任务数量和表达 |
| 执行模式 | 结构化统计生成，带 confidence | 重规划规则输入，按时间降权 |
| 敏感内容 | **默认不写入**，候选池 → 用户确认后激活 | 仅确认后使用 |
| 会话临时 | 仅当前/短期有效 | TTL 字段自动过期 |

写入路径：Agent 生成 `memory_candidates` → `persist` 节点统一写入。Agent 不直接操作记忆表。

### Consequences

- ✅ 正面：合规（敏感内容需用户确认）；记忆噪声可控（写入路径单一）；时间衰减避免陈旧记忆污染
- ⚠️ 负面：候选池流程增加用户交互摩擦（产品的代价）
- ⚠️ 负面：执行模式记忆的 confidence 阈值需用 Eval 校准

### 生命周期

| 类型 | 默认保留 | 过期策略 |
|---|---|---|
| 画像事实 / 稳定偏好 | 永久 | 用户删除/注销时清除 |
| 执行模式 | 90 天活跃窗口 | 90 天后归档，不再主动进上下文 |
| 敏感内容 | 确认后 90 天 | 用户未确认则 7 天后清理候选池 |
| 会话临时 | 24 小时 | TTL 字段自动过期 |

### Alternatives

| 方案 | 否决理由 |
|---|---|
| 单一记忆表无分层 | 敏感内容合规风险高；新用户冷启动被旧记忆带偏 |
| LLM 自由写记忆 | 噪声与偏见累积；不可审计 |
| 用 Redis 存短期记忆 | 单实例不需要；PostgreSQL + TTL 字段够用 |

---

## ADR-007：并发与运行——FastAPI async + SSE + Background Tasks

| 项目 | 内容 |
|---|---|
| Status | Accepted |
| Date | 2026-07-11 |

### Context

plan_run 是长任务（P95 ≤ 20s）但前端要持续感知进度（PRD §4.2 "规划等待中每 3-5s 进度更新"）。决策点：上 Celery 任务队列，还是 FastAPI 原生 async + Background Tasks。

### Decision

**FastAPI 原生 async + 异步 plan_run（POST 返 202 + run_id，SSE 推中间态）+ Background Tasks。不上队列。**

并发模型：Tool 调用走 `asyncio.gather` 并发执行；DB 连接池 asyncpg，池大小 = CPU × 2 + 1；限流每用户每分钟 plan_run ≤ 5 次（FastAPI middleware + DB 计数）；Trace 写入异步 fire-and-forget。

### Consequences

- ✅ 正面：单实例部署简单；浏览器原生支持 SSE；Background Tasks 零运维
- ⚠️ 负面：跨进程恢复能力弱（长任务中断只能重跑）；水平扩展时需引入队列
- ➖ 中性：演进触发条件是 plan_run 平均 > 30s 或需要跨进程恢复

### Alternatives

| 方案 | 否决理由 |
|---|---|
| Celery 任务队列 | 单实例 Background Tasks 够用；增加 Redis/RabbitMQ 运维 |
| Redis 分布式锁 | 单实例不需要 |
| gRPC Streaming | SSE 足够，浏览器原生支持 |

---

## ADR-008：工程治理——Spec-Driven + 阶段化交付 + 门禁脚本

| 项目 | 内容 |
|---|---|
| Status | Accepted |
| Date | 2026-07-11 |

### Context

代码主要由 AI 编程助手生成（Cursor / Claude Code / Codex）。AI 写代码无法靠"review 守纪律"，必须把规则机器化。同时项目时间窗口 4 周但需求复杂度高，不能用纯时间表驱动。决策点：用传统 Sprint，还是 Spec-Driven + 阶段化交付。

### Decision

**Spec-Driven 五段式（Clarify → Plan → Tasks → Implement → Verify）+ 阶段化交付（8 阶段，按退出条件驱动，不绑时间）+ 门禁脚本 + Docker Compose 部署。**

工程护城河：六层 Harness + Trace/Replay/Eval + 5 维质量评分 + 复盘-调整双层规则。

### Consequences

- ✅ 正面：AI 生成的代码有机器门禁兜底；质量可量化（5 维评分 + Eval 通过率）
- ✅ 正面：阶段化退出条件让"该不该进下一阶段"有客观判据，不靠主观估计
- ⚠️ 负价：门禁脚本本身需要维护成本；阶段化交付要求团队接受"不达条件不进下一阶段"的纪律
- ➖ 中性：spec-driven 的持久化判定矩阵由 `check-plan.sh` 强制

### 演进触发条件

| 何时调整 |
|---|
| 团队规模 > 5 人时引入 CODEOWNERS + 多环境发布 |
| 上线后接入 SaaS 监控（Sentry / LangSmith） |

### Alternatives

| 方案 | 否决理由 |
|---|---|
| 4 周时间表 Sprint | 时间是估计值，应该按退出条件驱动而非时间 |
| K8s 早期部署 | MVP 单机够用 |
| 早期多环境发布 | MVP 不需要 |

> 详细流程见 [governance/spec-driven-workflow.md](../governance/spec-driven-workflow.md)、[governance/stage-delivery-definition.md](../governance/stage-delivery-definition.md)、[governance/check-scripts-spec.md](../governance/check-scripts-spec.md)。

---

## ADR-009：Agent 编排器选型——LangGraph 优于 AutoGen / 自研循环

| 项目 | 内容 |
|---|---|
| Status | Accepted |
| Date | 2026-07-12 |

### Context

ADR-002 选定"单 Agent + 受控节点"范式，但范式本身不规定**编排器实现**。决策点：用 LangGraph 1.x、Microsoft AutoGen、还是自研 ReAct 循环。约束：需要原生 Checkpointer（断点恢复）、SSE 友好、Python 生态主流、社区活跃。

### Decision

**采用 LangGraph 1.x 作为 Agent 编排器。**

| 维度 | LangGraph | AutoGen | 自研 ReAct 循环 |
|---|---|---|---|
| 状态机 + 受控节点 | ✅ StateGraph 原生支持 | ⚠️ 偏 multi-agent 对话 | ✅ 但需自写 |
| Checkpointer（断点恢复） | ✅ PostgreSQL backend 原生 | ❌ | ❌ 需自写 |
| 工具调用封装 | ✅ ToolSpec + ToolNode | ✅ | ❌ 需自写 |
| Python + async 友好 | ✅ 原生 | ✅ | ⚠️ |
| 循环约束（轮数 / 预算） | ✅ RecursionLimit + Budget | ⚠️ 弱 | ✅ 完全可控 |
| 调试可观测 | ✅ 配 LangSmith | ⚠️ | ❌ |
| 社区与文档 | ✅ 活跃 | ✅ 活跃 | — |
| 面试讲故事 | ✅ 单 Agent 立场是主流叙事 | ⚠️ multi-agent 偏]重 | ⚠️ "为什么不开源" |

### Consequences

- ✅ 正面：Checkpointer / Tool / Budget / SSE / LangSmith 调试都开箱即用
- ✅ 正面：节点是 Python 函数（`async def`），与六层架构 L5 Runtime 自然融合
- ⚠️ 负面：绑定 LangChain 生态（state / message 抽象），未来切换编排器有迁移成本
- ⚠️ 负面：LangGraph API 仍在演进（>= 0.2.x），breaking change 风险存在

### 演进触发条件

| 何时迁移 |
|---|
| LangGraph 弃维或 breaking change 无法平滑升级 |
| 出现真实多 Agent 需求（见 ADR-002 演进条件）需要 Supervisor-Worker 模式 |

### Alternatives

| 方案 | 否决理由 |
|---|---|
| Microsoft AutoGen | 偏 multi-agent 对话；Checkpointer 弱；与"单 Agent + 受控节点"立场不一致 |
| 自研 ReAct 循环 | Checkpointer / 调试 / 工具调用自写成本高；面试官视角"为什么不开源"难答 |
| CrewAI | 偏 role-based multi-agent，与单 Agent 范式不符 |

---

## 参考

- 业界参考：Dify / FastGPT / LangGraph template / langchain-ai/memory-agent / Open-Assistant / Anthropic 工程博客
- 原始 ADR v1.0：[design-input/03_架构决策记录ADR.md](../design-input/03_架构决策记录ADR.md)（保留作为决策演进记录）
- 技术点决策矩阵：[technology-decision-matrix.md](./technology-decision-matrix.md)
