# api-spec/ API 端点 spec 入口

状态：本轮实现。

English summary: Per-resource endpoint specs — path, method, request schema (Pydantic), response schema, status codes, errors, sample payloads. Authoritative for AI writing FastAPI routers and OpenAPI snapshot. Split from architecture/api-and-data-contracts.md for AI context focus.

## 定位

每资源一份 `.md`，给 AI 写 `app/api/routers/<resource>.py`（FastAPI Router）直接照抄。

从 `architecture/api-and-data-contracts.md`（615 行）拆出，避免单文件过长导致 AI context 失焦。

## 端点清单（7 份）

| # | 资源 | 关键端点 | spec |
|---|---|---|---|
| 1 | auth | POST /auth/login（MVP 简化）/ GET /me | [auth.md](./auth.md) |
| 2 | profile | GET/PUT /api/v1/profile | [profile.md](./profile.md) |
| 3 | agent-runs | POST + GET + SSE | [agent-runs.md](./agent-runs.md) ⭐最复杂 |
| 4 | tasks | GET / PATCH /api/v1/tasks/{id} | [tasks.md](./tasks.md) |
| 5 | reviews | POST /api/v1/reviews | [reviews.md](./reviews.md) |
| 6 | memories | GET / POST / DELETE /api/v1/memories | [memories.md](./memories.md) |
| 7 | errors | 统一错误响应格式 + 业务码表 | [errors.md](./errors.md) |

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
