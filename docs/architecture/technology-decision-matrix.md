# 技术点决策矩阵

| 项目 | 内容 |
|---|---|
| 文档版本 | v1.0 |
| 日期 | 2026-07-11 |
| 状态 | 定稿 |
| 关联 | [ADR v2.0](././adr.md) 的细化展开 |
| 文档目的 | 给 Spec-driven AI 开发一份明确的"现在决策/延后/不考虑"指令清单——AI 看了不会跑偏 |

---

## 判定框架

每个技术点按三档处理：

| 标记 | 含义 | 落地方式 |
|---|---|---|
| ✅ **现在决策** | 写进 spec，AI 必须遵守 | ADR/TDD/API 写死，代码必须实现 |
| 🟡 **写触发条件不实现** | 写进 ADR，标明"什么情况才引入" | ADR 写明触发条件，代码不写 |
| ❌ **MVP 不考虑** | 一句话写明"不引入"+ 理由 | ADR 简短说明 |

**判定标准**：
- ✅ 现在决策 = 满足任一：① 后期改成本高 ② 影响 Schema/Contract ③ 影响多模块协作 ④ 安全/合规底线
- 🟡 延后 = 演进触发条件明确 + MVP 范围内不触发
- ❌ 不考虑 = 明显超出 MVP 范围

---

## 1. 数据存储

| 技术点 | 决策 | 落地结论 |
|---|---|---|
| 主数据库 | ✅ 现在决策 | PostgreSQL 16 |
| 向量检索 | ✅ 现在决策 | pgvector，不引入独立向量库 |
| 缓存（短期） | ✅ 现在决策 | Python 进程内 `lru_cache`，不引入 Redis |
| Redis | 🟡 延后 | 触发：日活 >500 且 plan_run P95 >15s；或需要分布式锁/限流；或会话数 >10k |
| 独立向量库（Qdrant/Milvus） | 🟡 延后 | 触发：向量数据 >1000 万条且 pgvector 检索 P95 >500ms |
| 对象存储（S3/OSS/MinIO） | 🟡 延后 | 触发：出现文件/截图上传需求 |
| MongoDB | ❌ 不考虑 | 关系型数据为主，事务+联表多，PostgreSQL 更合适 |
| ClickHouse/数据仓库 | ❌ 不考虑 | MVP 数据量小，PostgreSQL 聚合查询够用 |
| 分库分表 | ❌ 不考虑 | 单库远未到瓶颈 |
| 多数据源事务（XA） | ❌ 不考虑 | 单一 PostgreSQL |

## 2. Agent 的记忆

| 技术点 | 决策 | 落地结论 |
|---|---|---|
| 记忆分层模型 | ✅ 现在决策 | 5 类（画像事实/稳定偏好/执行模式/敏感/临时）—— schema 根基 |
| 记忆存储 | ✅ 现在决策 | 全部进 PostgreSQL（memories + memory_candidates 表）+ pgvector 向量字段 |
| 写入规则 | ✅ 现在决策 | 普通 vs 敏感的写入策略、confidence 计算、过期策略 |
| 检索方式 | ✅ 现在决策 | pgvector 语义检索 + 元数据过滤（user_id/goal_type/sensitivity/is_active）+ 时间衰减 |
| 保留期限 | ✅ 现在决策 | 画像事实/稳定偏好永久；执行模式 90 天；敏感内容确认后 90 天；临时 24h |
| 敏感记忆用户确认 | ✅ 现在决策 | 默认进 candidates 池，用户确认前不进长期上下文 |
| 跨 Agent 一致性 | ✅ 现在决策 | 统一 MemoryService，Agent 不直接写记忆表 |
| 记忆压缩/摘要 | 🟡 延后 | 触发：单用户记忆 >500 条且单 plan_run 检索 token >8K |
| 复杂生命周期（衰减/合并/覆盖） | 🟡 延后 | 触发：上线后用户回访率 >20% 且需要长期行为建模 |
| Agent 自主管理记忆 | ❌ 不考虑 | Agent 不允许直接写记忆，避免 LLM 自由发挥 |
| 神经嵌入式长期记忆（MemGPT 式） | ❌ 不考虑 | 复杂度过高，pgvector 检索 + 元数据过滤够用 |

## 3. MCP（Model Context Protocol）

| 技术点 | 决策 | 落地结论 |
|---|---|---|
| 实现 MCP Server | ❌ 不考虑 | MVP 只有一个客户端，无跨客户端需求 |
| 实现 MCP Client（接入外部工具） | ❌ 不考虑 | MVP 所有 Tool 都是自研的，不接入外部 MCP 工具 |
| 为 MCP 留接口抽象 | ❌ 不考虑 | YAGNI；Tool 已用 Protocol 抽象，未来要做 MCP 在这层加即可 |
| 何时考虑 | 🟡 远期 | 触发：要做插件生态 / 要被外部 Agent 调用 / 多 Agent 共享工具 |

## 4. 并发与运行

| 技术点 | 决策 | 落地结论 |
|---|---|---|
| async 框架选型 | ✅ 现在决策 | FastAPI 原生 async |
| plan_run 同步/异步 | ✅ 现在决策 | 异步：POST 返回 202 + run_id，SSE 推中间态 |
| Tool 并发调用 | ✅ 现在决策 | `asyncio.gather` 并发 RAG + Search |
| 数据库连接池 | ✅ 现在决策 | asyncpg，池大小 = CPU × 2 + 1 |
| 限流 | ✅ 现在决策 | 每用户每分钟 plan_run ≤5 次（FastAPI middleware + DB 计数） |
| 长任务处理 | ✅ 现在决策 | FastAPI BackgroundTasks（不上 Celery） |
| 分布式锁 | 🟡 延后 | 触发：多实例部署 / 需要跨进程互斥 |
| 任务队列（Celery/RQ） | 🟡 延后 | 触发：plan_run 平均 >30s 且需要跨进程恢复；或需要定时抓取 |
| 水平扩展 | 🟡 延后 | 触发：日活 >5000 且单机扛不住 |
| Actor 模型（Akka） | ❌ 不考虑 | 心智模型陡峭，与 FastAPI 生态不融合 |
| 多进程 Worker（Gunicorn） | ✅ 现在决策 | Uvicorn 单进程 MVP 够用；规模化上 Gunicorn 多 Worker |

## 5. 鉴权与安全

| 技术点 | 决策 | 落地结论 |
|---|---|---|
| 鉴权方式 | ✅ 现在决策 | JWT，单服务内置签发与校验 |
| MVP 用户来源 | ✅ 现在决策 | 测试用户 + 简化登录（账号密码）；远期上线接微信 openid |
| 密码哈希 | ✅ 现在决策 | bcrypt |
| HTTPS | ✅ 现在决策 | 本地开发 HTTP；docker compose 内置 Caddy/nginx 上 HTTPS |
| 内容安全（LLM 输出） | ✅ 现在决策 | 自建关键词词表 + LLM 分类器；上线后接 msgSecCheck |
| 安全分流（高风险/心理危机） | ✅ 现在决策 | 固定话术 + 12356 + 停止规划 |
| 数据出境 | ✅ 现在决策 | 只用国内大模型 API |
| OAuth/SSO | 🟡 延后 | 触发：上线 + 需要多端登录 |
| 多租户 | ❌ 不考虑 | MVP 单租户 |
| WAF/XSS/CSRF 防护 | 🟡 延后 | 上线前做一遍审查；FastAPI 内置基础 XSS 防护 |
| 加密存储敏感字段 | 🟡 P1 | 上线前完成字段级加密 |
| RBAC/ABAC 细粒度权限 | ❌ 不考虑 | MVP 仅用户/管理员两态 |

## 6. 监控与可观测性

| 技术点 | 决策 | 落地结论 |
|---|---|---|
| 结构化日志 | ✅ 现在决策 | structlog，JSON 输出 |
| Agent Trace | ✅ 现在决策 | 每 run + step + tool_call + Prompt 版本 + 模型配置 + Token |
| Replay（同输入重跑） | ✅ 现在决策 | 保存 Prompt 版本 + 模型配置 + 工具快照，可重跑对比 |
| LangSmith 集成 | ✅ 现在决策 | LangGraph 标配，Trace 可视化 |
| Metrics（Prometheus） | 🟡 延后 | 触发：上线 + 需要业务指标告警 |
| 分布式 Tracing（OpenTelemetry） | 🟡 延后 | 触发：多服务拆分后 |
| 错误监控（Sentry） | 🟡 延后 | 触发：上线 + 需要栈追踪聚合 |
| 自告警系统 | ❌ 不考虑 | LangSmith 基础告警够用 |

## 7. 评测与质量

| 技术点 | 决策 | 落地结论 |
|---|---|---|
| 固定数据集 | ✅ 现在决策 | 30 case 覆盖 1 场景（正常/异常/边界） |
| 自动 grader | ✅ 现在决策 | 5 维质量评分 + 任务结构校验 + 来源覆盖率 |
| Bad Case 修复闭环 | ✅ 现在决策 | 失败 Trace 一键加入评测集 |
| 契约测试 | ✅ 现在决策 | Pydantic + OpenAPI snapshot + import-linter |
| 故障注入测试 | ✅ 现在决策 | LLM/Search/DB 失败注入，测降级路径 |
| LLM Judge 评测 | 🟡 P1 | MVP 后补，按 Rubric 自动评分 |
| 在线 A/B 评测 | ❌ 远期 | 上线且有真实流量后 |

## 8. 部署与运维

| 技术点 | 决策 | 落地结论 |
|---|---|---|
| 容器化 | ✅ 现在决策 | Docker + Docker Compose |
| CI/CD | ✅ 现在决策 | GitHub Actions：pytest + import-linter + 契约测试 + eval |
| 部署方式 | ✅ 现在决策 | docker compose up 一键起（fastapi + postgres + nginx/caddy） |
| 反向代理 | ✅ 现在决策 | Caddy 自动 HTTPS 或 Nginx |
| K8s | ❌ 不考虑 | 单机够用；触发：日活 >5000 |
| 多环境（dev/staging/prod） | 🟡 延后 | 本地 + 生产两环境；staging 上线后再加 |
| 蓝绿/金丝雀发布 | ❌ 不考虑 | 远期上线后再说 |
| 服务网格（Istio/Linkerd） | ❌ 不考虑 | 单后端不需要 |

## 9. 前端

| 技术点 | 决策 | 落地结论 |
|---|---|---|
| 框架 | ✅ 现在决策 | React 18 + TypeScript + Vite |
| UI 库 | ✅ 现在决策 | shadcn/ui（轻量 + Tailwind） |
| 状态管理 | ✅ 现在决策 | Zustand（不引入 Redux） |
| 数据请求 | ✅ 现在决策 | TanStack Query |
| SSE 客户端 | ✅ 现在决策 | EventSource API 原生 |
| 微信小程序 | ❌ 远期 | MVP 本地 Web 端，未来上线再换小程序 |
| 移动端原生 | ❌ 不考虑 | 响应式 Web 够用 |
| SSR/SSG | ❌ 不考虑 | 后台为准，CSR 够用 |

## 10. 产品功能边界

| 技术点 | 决策 | 落地结论 |
|---|---|---|
| 主动推送（订阅消息） | ❌ MVP 不做 | 用被动召回（次日续接卡片 + 回归欢迎语） |
| 多语言 | ❌ 不考虑 | 中文单语言 |
| 社交功能 | ❌ 不考虑 | 单用户产品 |
| 变现/付费 | ❌ 远期 | MVP 后再考虑 |

---

## 一句话总结

**核心原则**：选什么/不选什么/什么时候才选——三档分明。AI 看到 ✅ 就执行，看到 🟡 写触发条件不实现，看到 ❌ 一句话说明理由。这是 spec 给 AI 开发的最清晰指令。

**不允许的灰色地带**：写"可以考虑 Redis"或"规模化时引入队列"而不写触发条件——这种 spec AI 会乱猜，必须写死触发阈值。
