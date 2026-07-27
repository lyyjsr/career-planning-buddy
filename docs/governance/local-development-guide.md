# 本地开发与调试手册

| 项目 | 内容 |
|---|---|
| 版本 | v1.0 |
| 状态 | 本轮实现 |
| 面向对象 | 开发者、AI 编程助手、评审者 |
| 定位 | 说明 Dazi 在 Stage 0 完成后如何本地启动、调试、切换 Mock/真实 Provider、运行门禁与排查常见问题 |

English summary: Local development and debugging guide for Dazi. It defines the intended local startup flow, environment variables, mock/real provider modes, gates, and troubleshooting path.

---

## 1. 当前状态说明

当前仓库处于 Pre-Stage 0，根 README 已明确说明：`backend/`、`frontend/`、`scripts/`、`infra/` 尚未创建。

因此本文描述的是 Stage 0 工程基线完成后应成立的本地开发方式。AI 编程助手实现 Stage 0 时，应以本文作为目标之一，但不得在代码未存在前虚构命令已可运行。

## 2. 本地开发目标

本地开发环境必须支持三种工作模式：

| 模式 | 用途 | Provider |
|---|---|---|
| `mock` | Stage 2 纵切、CI 稳定测试、前后端联调 | Mock LLM/Search/RAG |
| `poc` | Pre-Stage 0 Provider 验证 | 真实 DeepSeek，最小脚本 |
| `real` | Stage 3+ 真实模型调试 | DeepSeek + Search/RAG |

默认本地模式应为 `mock`，避免开发者一启动就消耗真实模型额度。

## 3. 预期目录

```text
dazi/
├── backend/
│   ├── app/
│   ├── tests/
│   ├── contracts/
│   ├── pyproject.toml
│   └── .importlinter.toml
├── frontend/
│   ├── src/
│   ├── package.json
│   └── vite.config.ts
├── infra/
│   └── docker-compose.yml
├── scripts/
│   ├── check.sh
│   ├── check-architecture.sh
│   ├── check-contract.sh
│   └── check-doc-links.sh
├── .env.example
└── README.md
```

## 4. 环境变量

`.env.example` 至少应包含：

```env
APP_ENV=development
APP_MODE=mock
DATABASE_URL=postgresql+asyncpg://dazi:dazi@localhost:5432/dazi
POSTGRES_DB=dazi
POSTGRES_USER=dazi
POSTGRES_PASSWORD=dazi

DEEPSEEK_API_KEY=
LLM_PROVIDER=mock
SEARCH_PROVIDER=mock
EMBEDDING_PROVIDER=mock

ENABLE_DEV_ROUTES=true
ENABLE_LANGSMITH=false
LANGSMITH_PROJECT=
```

规则：

- `APP_MODE=mock` 时不得要求 `DEEPSEEK_API_KEY`。
- `APP_MODE=real` 时启动前必须校验真实 Provider 必需配置。
- `production` 环境必须关闭 `/api/v1/dev/*`。

## 5. 启动顺序

Stage 0 完成后的预期启动顺序：

```mermaid
flowchart TD
    A[cp .env.example .env] --> B[docker compose up postgres]
    B --> C[alembic upgrade head]
    C --> D[启动 FastAPI]
    D --> E[GET /health]
    E --> F[启动 React]
    F --> G[浏览器访问前端]
```

预期命令形状：

```bash
cp .env.example .env
docker compose -f infra/docker-compose.yml up -d postgres
pip install -e "backend[dev]"
alembic -c backend/alembic.ini upgrade head
uvicorn app.main:app --reload --app-dir backend
cd frontend && npm install && npm run dev
```

注意：当前阶段这些命令尚未全部存在。Stage 0 实现时需要让这些命令逐步变为真实可运行。

## 6. 健康检查

后端 `/health` 最小响应：

```json
{
  "status": "ok",
  "app_env": "development",
  "app_mode": "mock",
  "db": "ok"
}
```

健康检查分层：

| 检查 | Stage | 说明 |
|---|---|---|
| app alive | Stage 0 | FastAPI 进程可响应 |
| db connect | Stage 0 | 数据库可连接 |
| migration current | Stage 1 | Alembic head 一致 |
| provider ready | Stage 3 | 真实 Provider 配置可用 |

## 7. Mock/真实 Provider 切换

Provider 必须通过配置切换，不允许业务代码里写死厂商。

```text
APP_MODE=mock
LLM_PROVIDER=mock
SEARCH_PROVIDER=mock
EMBEDDING_PROVIDER=mock
```

```text
APP_MODE=real
LLM_PROVIDER=deepseek
SEARCH_PROVIDER=tavily
EMBEDDING_PROVIDER=local_or_vendor
```

切换规则：

- Mock 和真实 Provider 必须实现同一 Protocol。
- Mock 与真实 Provider 必须共享契约测试。
- Mock fixture 必须标记 `data_origin: "mock"`。
- 真实 Provider 失败必须返回显式错误或降级，不得静默兜底。

## 8. 门禁命令

总入口：

```bash
bash scripts/check.sh
```

子门禁建议：

| 脚本 | 目标 |
|---|---|
| `scripts/check-architecture.sh` | import-linter 层依赖 |
| `scripts/check-contract.sh` | OpenAPI snapshot / Pydantic / 状态机 |
| `scripts/check-doc-links.sh` | 文档链接和索引 |
| `scripts/check-tests.sh` | pytest / frontend test |
| `scripts/check-eval.sh` | Eval smoke 或固定数据集 |

Stage 0 可以先实现 `check.sh` 的空骨架和基础 lint；Stage 1 后逐步变严。

## 9. 常见调试路径

### 9.1 `/health` 不通

检查：

1. FastAPI 是否启动。
2. `--app-dir backend` 是否正确。
3. `.env` 是否被加载。
4. 端口是否被占用。

### 9.2 数据库连接失败

检查：

1. Postgres 容器是否启动。
2. `DATABASE_URL` 是否与 compose 配置一致。
3. pgvector extension 是否安装。
4. Alembic migration 是否已执行。

### 9.3 SSE 没有事件

检查：

1. `POST /agent-runs` 是否返回 `events_url`。
2. `EventSource` 是否连接正确路径。
3. 后端 async generator 是否 yield。
4. run 是否卡在 pending。
5. Mock graph 是否实际推进到 `run.completed`。

### 9.4 前端页面有数据但状态不更新

检查：

1. TanStack Query key 是否稳定。
2. mutation 后是否 invalidate 对应 query。
3. 乐观更新是否回滚。
4. SSE 事件是否更新本地 run 状态。

### 9.5 真实 LLM 输出 schema 不合法

检查：

1. Provider 是否开启 structured output。
2. Pydantic schema 是否过严或字段名不一致。
3. 是否执行了 1 次重试。
4. 是否记录 `fallback_reason="agent_schema_invalid"`。

## 10. 本地最小验收

Stage 2 Mock 纵切完成后，本地必须能跑通：

1. 前端打开 `/`。
2. `GET /me` 成功。
3. 用户补 profile。
4. 用户发起规划。
5. SSE 显示进度。
6. 生成 1-3 个今日任务。
7. 用户开始/完成任务。
8. 用户提交复盘。
9. 开发者 Trace 页能看到 run。
10. `bash scripts/check.sh` 通过。

## 11. 不做

- 不要求本地启动 Kubernetes。
- MVP 不引入 Redis/Celery。
- 不要求开发者默认配置真实模型 key。
- 不在本地开发手册里复制每个 API 字段。

## 12. 关联文档

- [阶段化交付定义](./stage-delivery-definition.md)
- [门禁脚本规范](./check-scripts-spec.md)
- [端到端运行流程](../model-design/end-to-end-runtime-flow.md)
- [API 端点 spec](../model-design/api-spec/README.md)
- [Provider PoC 验证报告](../architecture/poc-verification-report.md)
