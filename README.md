# Career Planning Buddy — AI 求职规划搭子

> 面向计算机专业学生的垂直 Agent 产品：根据用户画像、目标岗位和真实执行反馈，完成“规划 → 今日任务 → 执行 → 复盘 → 重规划”的闭环。

## 项目边界

这是一个**从零独立开发的新项目**：

- 不以 ClawAgent 为底座；
- 不依赖或导入 ClawAgent 的代码、配置、数据库和运行时；
- 可以借鉴通用 Agent 工程思想，但本仓库中的接口、状态机、表结构和实现必须独立落地；
- Codex 是本项目选定的**代码生成与工程执行助手**，但不是项目运行时模型。

## 技术栈

| 层 | 选型 |
|---|---|
| 前端 | React + TypeScript + Vite + React Router + TanStack Query |
| 后端 | Python 3.11 + FastAPI + Pydantic v2 + SQLAlchemy 2 Async |
| Agent 编排 | LangGraph，单核心 `CareerPlanningAgent` + 受控节点 |
| 数据库 | PostgreSQL 16 + pgvector + Alembic |
| 实时通信 | SSE，事件写入 PostgreSQL 后支持断线续传 |
| 运行时模型 | OpenAI-compatible Provider，通过 `LLM_BASE_URL / LLM_API_KEY / LLM_MODEL` 配置 |
| 搜索与向量 | SearchProvider + EmbeddingProvider，MVP 后半程接入 |
| 测试 | pytest + pytest-asyncio + httpx + 前端 Vitest |
| 部署 | Docker Compose，MVP 单机单 Worker |

> 运行时模型与编码助手是两件事。团队使用 Codex 阅读规范、修改代码并运行测试；项目运行时模型仍通过 OpenAI-compatible Provider 独立配置。

## MVP 业务闭环

```text
用户建档
  → 发起规划请求
  → Agent 生成中期方向、每周重点与 1~3 个今日任务
  → 用户开始 / 完成 / 放弃任务
  → 用户提交每日复盘
  → 系统判断是否需要重规划
  → 用户确认后生成新版本计划
```

MVP 必须完成：

1. Guest JWT 登录与用户隔离；
2. 用户画像；
3. Agent Run + SSE；
4. 中期方向、每周重点和今日任务；
5. 任务状态机；
6. 复盘和重规划；
7. 基础记忆；
8. Trace 开发者页；
9. Docker Compose 与固定 Eval Case。

MVP 暂不引入 Redis、Celery、Kafka、MCP、多 Agent、Kubernetes 和对象存储。

## 当前状态

当前仓库是**实现前设计包**，尚未创建 `backend/` 和 `frontend/` 代码。下一步应直接进入 Stage 0，不需要等待某个特定模型的 PoC 才能搭工程骨架。

开发顺序以 [`docs/implementation/README.md`](./docs/implementation/README.md) 为准：

| 阶段 | 目标 |
|---|---|
| 0 | 创建前后端骨架、数据库和质量门禁 |
| 1 | 落地契约、鉴权、用户画像和迁移 |
| 2 | 用 Mock Provider 跑通一次完整 plan run |
| 3 | 接入真实 LLM，完成任务、复盘和重规划 |
| 4 | 接入记忆、搜索和 RAG |
| 5 | 完成 Trace、Eval、部署和作品包装 |

## 文档权威顺序

发生冲突时按以下顺序执行：

1. [`docs/implementation/project-baseline.md`](./docs/implementation/project-baseline.md)
2. [`docs/architecture/tdd.md`](./docs/architecture/tdd.md)
3. [`docs/architecture/api-and-data-contracts.md`](./docs/architecture/api-and-data-contracts.md)
4. [`docs/model-design/`](./docs/model-design/README.md) 下的 Runtime、Tool、端点、表和节点 spec
5. [`docs/overview/product-overview.md`](./docs/overview/product-overview.md)
6. `docs/design-input/` 仅供追溯，不作为实现依据

## 给 Codex 的使用方式

不要一次让模型生成整个项目。每次只执行一个阶段任务：

```text
1. 从仓库根目录启动 Codex，让其读取 `AGENTS.md`
2. 再读 `AGENTS.zh-CN.md` 与 `docs/implementation/project-baseline.md`
3. 只读当前阶段任务书；Stage 2~4 额外阅读 Agent Runtime 与 Tool spec
4. 先输出文件清单和实现计划
5. 再生成代码与测试
6. 本地执行验收命令
7. 通过后再进入下一阶段
```

各阶段可直接复制的任务说明位于 [`docs/implementation/`](./docs/implementation/README.md)。
更具体的 Codex 使用方法见 [`CODEX-CODING-GUIDE.md`](./CODEX-CODING-GUIDE.md)。

Agent 编码的三个关键施工入口：

- [`Agent Runtime`](./docs/model-design/agent-runtime/README.md)：Graph、State、预算、快照、取消和终态；
- [`Agent Tool`](./docs/model-design/tools/README.md)：白名单、Schema、超时、证据和 Replay fixture；
- [`Runtime Prompt 清单`](./docs/standards/prompts/runtime-prompt-matrix.md)：哪些节点使用模型、输入输出和修复边界。

## 计划中的仓库结构

```text
career-planning-buddy/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── repositories/
│   │   ├── models/
│   │   ├── agent/
│   │   ├── tools/
│   │   ├── providers/
│   │   ├── harness/
│   │   └── core/
│   ├── alembic/
│   └── tests/
├── frontend/
├── infra/
├── scripts/
└── docs/
```

## 完成定义

项目达到可投递状态，至少需要：

- 新用户可完成建档并生成计划；
- 一次 Agent Run 可稳定通过 SSE 展示进度；
- 任务状态、复盘和重规划形成真实数据库闭环；
- 失败、超时和取消能收敛到明确状态；
- 至少 30 条固定 Eval Case 可重复运行；
- Docker Compose 一键启动；
- README 中有真实截图、Demo 和实测指标。
