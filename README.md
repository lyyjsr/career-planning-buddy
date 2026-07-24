# Dazi — AI 求职规划搭子

> 面向计算机学生的 AI 求职规划 Agent：单核心 Agent（CareerPlanningAgent）+ 受控节点 + 证据驱动 + 执行反馈闭环。

| 项目 | 内容 |
|---|---|
| 项目类型 | AI 应用开发（Python 单后端，不是 Java 业务系统）|
| 后端 | FastAPI 单体 + LangGraph 1.x |
| 前端 | React + TypeScript + Vite |
| 数据库 | PostgreSQL 16 + pgvector |
| LLM | DeepSeek V4 主选，五类 Provider Protocol 抽象 |
| 部署 | Docker Compose（单机）|
| 开发方式 | Spec-Driven（文档先定稿，AI 编程助手按 spec 执行） |
| 当前阶段 | 📍 **Pre-Stage 0：SDD 文档收敛 + Provider PoC 准备** |

---

> ⚠️ **当前状态（2026-07-24）**
>
> 本仓库当前**只有文档，没有代码**：`backend/` / `frontend/` / `scripts/` / `infra/` 等目录尚未创建。
> 这是 **Spec-Driven Development 的预期状态**，不是 bug。
>
> - 文档侧进度：核心 SDD 文档已基本就绪；Stage 0 前置 Provider PoC 待验证（见 [PoC 验证报告](./docs/architecture/poc-verification-report.md)）
> - 下一步动作：跑 Pre-Stage 0 Provider PoC → H1/H2/H3/H4/H7 全 Go 后启动 Stage 0 工程基线
> - **想 fork 自己启动？** 先读 [PoC 验证报告](./docs/architecture/poc-verification-report.md) + [DeepSeek 对接](./docs/third-party-integration/deepseek-api.md)，需自备 `DEEPSEEK_API_KEY`
>
> 下面"快速开始"段是 **Stage 0 完成后**才会激活——当前 `infra/docker-compose.yml` / `backend/pyproject.toml` / `scripts/check.sh` 均未创建。

---

## 快速开始

### 前置
- Python 3.11+、Node 20+、Docker、PostgreSQL 16（含 pgvector）或用 Docker Compose

### 后端
```bash
cp .env.example .env          # 填入 DEEPSEEK_API_KEY 等
docker compose -f infra/docker-compose.yml up -d postgres
pip install -e "backend[dev]"
uvicorn app.main:app --reload --app-dir backend
# 访问 http://localhost:8000/health
```

### 前端
```bash
cd frontend && npm install && npm run dev
# 访问 http://localhost:5173
```

### 门禁
```bash
bash scripts/check.sh         # CI 硬阻断入口（架构 / 契约 / 文档 / Eval 全检）
pytest                         # Python 测试
```

---

## 仓库结构（5 圈层）

```
dazi/
├── docs/                       ① 文档（8 类，spec 根据地）
├── backend/                    ② 后端代码（FastAPI 六层 + Providers 横切）
├── frontend/                   ② 前端代码（React + TS）
├── scripts/                    ③ 工程门禁（check-*.sh）
├── infra/                      ④ 部署（Docker / Caddy）
├── .github/workflows/          ④ CI（GitHub Actions）
├── AGENTS.md / AGENTS.zh-CN.md ⑤ AI 协作入口（双语，规则强制）
└── README.md                   本文件
```

详见各目录 README。

---

## 多人协作约定

### 必读
1. [AGENTS.md](./AGENTS.md)（英文）/ [AGENTS.zh-CN.md](./AGENTS.zh-CN.md)（中文）—— AI 协作宪章 + Non-Negotiable Rules
2. [docs/README.md](./docs/README.md) —— 文档总索引
3. [docs/governance/development-workflow.md](./docs/governance/development-workflow.md) —— 开发流程
4. [docs/governance/spec-driven-workflow.md](./docs/governance/spec-driven-workflow.md) —— 改动前的 Clarify→Plan→Tasks
5. [docs/governance/stage-delivery-definition.md](./docs/governance/stage-delivery-definition.md) —— 阶段编号与退出条件

### Spec-Driven 强制流程
跨模块 / 改状态机 / 新增 API / 新增表 / 新增节点的改动**必须**先在 `docs/requirements/<feature>/` 写 clarify.md + plan.md（含 mermaid 图），由 `scripts/check-plan.sh` 机器校验。

### 分支与提交
- `main` 受保护，只接 PR
- 分支命名：`feat/<scope>` / `fix/<scope>` / `docs/<scope>`
- PR 必须 CI 全绿 (`scripts/check.sh`) + 至少 1 个 reviewer
- 提交前自查：[use-case-development-checklist](./docs/governance/use-case-development-checklist.md)

### 任务认领
按根 README 的当前状态和 [stage-delivery-definition](./docs/governance/stage-delivery-definition.md) 的阶段退出条件认领任务，退出条件不达标不进下一阶段。

---

## 核心架构决策（9 条，详见 [docs/architecture/adr.md](./docs/architecture/adr.md)）

| ADR | 主题 | 结论 |
|---|---|---|
| 001 | 整体架构 | FastAPI 单后端 + React + PostgreSQL |
| 002 | Agent 编排 | 单核心 Agent + 受控节点（非多 Agent）|
| 003 | 分层架构 | 六层（Types→Config→Repo→Service→Runtime→API）+ Providers 横切 |
| 004 | 数据存储 | PostgreSQL + pgvector（不引入 Redis）|
| 005 | LLM 与 Provider | DeepSeek V4 + 五类 Provider Protocol（待 spike）|
| 006 | 记忆系统 | 五类分层 + 敏感内容用户确认 |
| 007 | 并发 | FastAPI async + SSE + Background Tasks |
| 008 | 工程治理 | Spec-Driven + 阶段化交付 + 门禁脚本 |
| 009 | Agent 编排器 | LangGraph 1.x |

---

## 当前进度

📍 **Pre-Stage 0：SDD 文档收敛 + Provider PoC 准备**（spec 已就绪 / 代码未启动）

下一步关键路径（按依赖顺序）：

| # | 动作 | 文档依据 | 前置 |
|---|---|---|---|
| 1 | 跑 Pre-Stage 0 Provider PoC（脚本验证 7 项假设） | [PoC 验证报告 §4 执行计划](./docs/architecture/poc-verification-report.md) | 取得 `DEEPSEEK_API_KEY` |
| 2 | spike 全部 Go（H1-H4 + H7 通过） → ADR-005 升号 "Accepted（已验证）" | 同上 §6 Go/No-Go 矩阵 | 1 |
| 3 | 启动 **Stage 0 工程基线**：FastAPI `/health` + Docker + Alembic + `scripts/check.sh` | [stage-delivery-definition.md §阶段 0](./docs/governance/stage-delivery-definition.md) | 2 |
| 4 | Stage 1 契约冻结：Pydantic + Alembic 迁移 + Provider Protocol + 状态机枚举 | 同上 §阶段 1 | 3 |
| 5 | Stage 2 纵切 Mock 跑通：LangGraph + 11 节点 Mock + Trace 表有数据 | 同上 §阶段 2 | 4 |

> **重要**：在 Provider PoC 全 Go 之前，任何 `backend/` 业务代码不应启动。否则地基不稳。

Harness 分阶段落地：
- Stage 1：冻结 Trace / Replay / Eval 的 schema 与协议。
- Stage 2：Mock 纵切写入最小 Trace。
- Stage 3：真实模型接入后补 Provider trace、Budget、Guard。
- Stage 5：Replay / Eval / Bad Case 闭环完整化。

---

## 许可与贡献

- 代码私有（秋招作品）
- 协作流程： Fork → PR → CI → Review
- 改文档：先看 [docs/README.md §写作约定](./docs/README.md)
