# api-spec/ API 端点 spec 入口

状态：本轮实现。

English summary: Per-resource endpoint specs — path, method, request schema (Pydantic), response schema, status codes, errors, sample payloads. Authoritative for AI writing FastAPI routers and OpenAPI snapshot. Split from architecture/api-and-data-contracts.md for AI context focus.

## 定位

每资源一份 `.md`，给 AI 写 `app/api/routers/<resource>.py`（FastAPI Router）直接照抄。

从 `architecture/api-and-data-contracts.md`（615 行）拆出，避免单文件过长导致 AI context 失焦。

## 端点清单（11 份）

| # | 资源 | 关键端点 | spec | 对应功能模块 |
|---|---|---|---|---|
| 1 | auth | POST /auth/login（MVP 简化）/ GET /me 摘要 | [auth.md](./auth.md) | 首次建档 |
| 2 | profile | GET / PUT / PATCH /api/v1/profile | [profile.md](./profile.md) | 首次建档 |
| 3 | agent-runs | POST + GET + SSE + cancel | [agent-runs.md](./agent-runs.md) ⭐最复杂 | 生成规划 / 安全分流（高风险） |
| 4 | plans | GET active / list / {id} / sources | [plans.md](./plans.md) | 生成规划 / 今日任务（视图） |
| 5 | tasks | GET /today / list / PATCH /tasks/{id} | [tasks.md](./tasks.md) | 今日任务推进 |
| 6 | reviews | POST + GET + accept-replan | [reviews.md](./reviews.md) | 每日复盘 + 调整闭环 |
| 7 | memories | GET / POST / DELETE / PATCH | [memories.md](./memories.md) | 记忆管理 |
| 8 | clarification | SSE 事件 `clarification.requested`（不另起 REST）| [clarification.md](./clarification.md) | 首次建档澄清 |
| 9 | errors | 统一错误响应格式 + 业务码表 | [errors.md](./errors.md) | 全部模块 |
| 10 | dev-runs | /dev/runs (list/detail/replay) | [dev-runs.md](./dev-runs.md) | Harness |
| 11 | dev-evals | /dev/evals/datasets + experiments | [dev-evals.md](./dev-evals.md) | Harness |

## 与 architecture/api-and-data-contracts.md 关系

| 文档 | 角色 |
|---|---|
| architecture/api-and-data-contracts.md | **协议级**（通用 Header、错误码、分页、幂等、版本契约、Schema 概要） |
| model-design/api-spec/*.md | **端点级**（每端点的具体 Request/Response payload、状态码、错误响应） |

两者职责不重叠。通用规范读 architecture/，单端点详细信息读本目录。

## 端点 spec 模板

```markdown
## 端点：METHOD /path
- 请求 Schema（借鉴 Pydantic 类）
- 成功响应 Schema
- 错误响应（哪些业务码 + HTTP 状态）
- 状态变更（触发的状态机）
- 示例 payload
- 副作用（容器/Service 调用/事件）
```

## 引用

- 来源：[architecture/api-and-data-contracts.md](../../architecture/api-and-data-contracts.md)
- Pydantic 写法：[standards/python-coding-standards.md §3](../../standards/python-coding-standards.md)
- 表字段：[model-design/data-models/](../data-models/README.md)
