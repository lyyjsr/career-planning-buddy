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
| 当前阶段 | 📍 阶段 0：工程基线 |

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
5. [docs/governance/stage-delivery-definition.md](./docs/governance/stage-delivery-definition.md) —— 当前阶段与退出条件

### Spec-Driven 强制流程
跨模块 / 改状态机 / 新增 API / 新增表 / 新增节点的改动**必须**先在 `docs/requirements/<feature>/` 写 clarify.md + plan.md（含 mermaid 图），由 `scripts/check-plan.sh` 机器校验。

### 分支与提交
- `main` 受保护，只接 PR
- 分支命名：`feat/<scope>` / `fix/<scope>` / `docs/<scope>`
- PR 必须 CI 全绿 (`scripts/check.sh`) + 至少 1 个 reviewer
- 提交前自查：[use-case-development-checklist](./docs/governance/use-case-development-checklist.md)

### 任务认领
按 [stage-delivery-definition](./docs/governance/stage-delivery-definition.md) 当前阶段的退出条件认领任务，退出条件不达标不进下一阶段。

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

📍 **阶段 0：工程基线**

退出条件：
- [x] 仓库初始化（backend / frontend / docs / scripts / infra 五圈层）
- [x] FastAPI 空骨架 + `/health` 返回 200
- [x] React 空骨架首屏显示标题
- [x] Docker Compose 模板（postgres + backend + caddy）
- [x] import-linter 配置就位
- [x] `scripts/check.sh` 总入口
- [x] `docs/` 八类目录就位
- [x] `.env.example` + `.gitignore`
- [x] 根 README + 多人协作约定
- [ ] 本地实测：fastapi 起动 + import-linter 绿 + pytest 绿
- [ ] Alembic 第一条迁移（pgvector 扩展 + users 表）

下一步：[docs/governance/stage-delivery-definition.md](./docs/governance/stage-delivery-definition.md) 阶段 1 契约冻结。

---

## 许可与贡献

- 代码私有（秋招作品）
- 协作流程： Fork → PR → CI → Review
- 改文档：先看 [docs/README.md §写作约定](./docs/README.md)
