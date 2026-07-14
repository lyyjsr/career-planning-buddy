# 开发流程

状态：本轮实现。

English summary: New features follow layer selection, contract definition, repository/service/agent/api ordering, tests, and review.

---

## 第 0 步：Clarify → Plan（前置，不可跳过）

任何使用 AI（或人工）开始一个改动前，先按 [spec-driven-workflow](./spec-driven-workflow.md) 完成澄清与计划：

1. **Clarify**：就需求边界、成功条件、隐含假设向用户逐问澄清，把答复与未澄清假设登记到 `docs/requirements/<feature>/clarify.md`。
2. **Plan / Tasks**：按 spec-driven-workflow 第 3 节判定矩阵决定是否持久化。命中任一阈值时，写 `docs/requirements/<feature>/plan.md`（第 3 节 ` ```mermaid ` 交互流程图必填）。跨上下文/新增表/新增 API/新增节点 还要写 `tasks.md`。
3. 例外：Bug fix < 30 行 + 单模块、不触状态机/schema/API，可在对话内口头澄清、不必持久化。

下面的"新增功能顺序"在第 0 步完成后启动，不是替代关系。

---

## 新增功能顺序

1. 判断所属逻辑模块（建档 / 规划 / 任务 / 复盘 / 记忆 / 来源 / Agent Runtime）。
2. 按 `api / schemas / services / agent / tools / repositories / providers / harness` 确认落位（对应 TDD 六层）。
3. 判断是否属于 Agent 自主决策（真 Agent）或确定性节点。
4. 设计 Pydantic Schema（输入/输出，参考 [spec-writing-guide](../standards/spec-writing-guide.md)）。
5. 设计 Service 用例与状态机。
6. 设计 Repository 接口。
7. 设计基础设施实现（ORM Model、Alembic 迁移）。
8. 设计 Tool / Provider Protocol（若涉及外部调用）。
9. 编写单测（schemas/services/repository）。
10. 编写 Agent 节点 / FastAPI Router。
11. 编写集成测试。

## 开发前阅读

- 新增业务能力：[project-overview](../overview/product-overview.md)、[tdd](../architecture/tdd.md)、[adr](../architecture/adr.md)。
- Python / FastAPI 代码：[python-coding-standards](../standards/python-coding-standards.md)。
- Agent 节点 spec：[spec-writing-guide](../standards/spec-writing-guide.md)。
- 安全与审计：[security-and-compliance](../standards/security-and-compliance.md)。
- 测试：[testing-and-tdd](../standards/testing-and-tdd.md)。
- 新增用例自查：[use-case-development-checklist](./use-case-development-checklist.md)。

---

## 技术纵切样例

创建一次 plan_run 的链路（阶段 2 纵切骨架）：

```text
POST /api/v1/agent-runs
  -> api/routers/agent_runs.py（Router）
  -> schemas/agent_run.py（Pydantic Request）
  -> services/agent_run_service.py（Service，编排 + 事务）
  -> agent/graph.py（LangGraph 工作流）
  -> agent/nodes/*.py（各节点）
  -> repositories/agent_run_repository.py（Repository）
  -> models/agent_run.py（SQLAlchemy ORM）
  -> agent_runs 表（PostgreSQL）
```

样板约束：

- Router 放 `app/api/`，只处理 HTTP、DTO 校验、响应状态码、错误映射。
- Request/Response 放 `app/schemas/`，Pydantic 模型 + `model_config = ConfigDict(extra="forbid")`。
- Service 放 `app/services/`，只编排用例与状态机。
- Agent / 节点放 `app/agent/`，LangGraph 工作流 + harness。
- ORM Model 放 `app/models/`；Repository 放 `app/repositories/`。
- Provider 实现放 `app/providers/`，只暴露 Protocol 接口给上层。
- 测试按层跟随代码：`backend/tests/<对应包>/`。

---

## 命令与查询

- 命令（写）必须走 Service + Repository 事务，Agent 只生成候选不直接写。
- 查询可以轻量（直接 Repository 读模型），但不得修改领域状态。
- 查询服务不得偷偷写入业务事实。

---

## 模块落位（对应 TDD 六层）

| 层 | 放什么 | 不放什么 |
|---|---|---|
| `app/schemas/` (L1) | Pydantic 模型、枚举、错误码 | DB 会话、SDK、HTTP |
| `app/core/` (L2) | 配置、Feature Flag、预算 | 业务查询、Agent 决策 |
| `app/repositories/` (L3) | ORM 查询、事务持久化实现 | Prompt、LLM 调用、HTTP 响应 |
| `app/services/` (L4) | 业务规则、状态机、用例编排 | LangGraph 节点顺序、厂商 SDK |
| `app/agent/` + `app/tools/` + `app/harness/` (L5) | Agent Graph、Tool Registry、Trace/Eval | 直接 ORM 查询、绕过 Service 写库 |
| `app/api/` (L6) | FastAPI Router、SSE、错误映射 | 核心业务规则、Prompt |
| `app/providers/`（横切） | LLM/Search/Embedding/Cache/Storage Protocol + 实现 | 向上暴露厂商对象 |
| `app/prompts/{goal_type}/` | Prompt 模板（带版本号） | 业务规则 |

---

## 测试落位

| 被测代码 | 测试文件位置 |
|---|---|
| `schemas/` 中的 Pydantic 校验 | `backend/tests/schemas/` |
| `services/` 中的用例、状态机 | `backend/tests/services/` |
| `repositories/` 中的 Repository 实现 | `backend/tests/repositories/`（用 testcontainers postgres） |
| `agent/` 中的节点、graph | `backend/tests/agent/`（Mock Provider） |
| `api/` 中的 Router | `backend/tests/api/`（FastAPI TestClient） |
| `providers/` 的 Mock 契约 | `backend/tests/providers/` |
| `evals/` 固定数据集 | `backend/tests/eval/` |

> AI 为验证实现临时编写的测试文件，默认不得暂存、提交或推送到远程；用户明确要求"作为正式测试提交"时才纳入。

---

## 收尾

提交前：

- 运行 `bash scripts/check.sh`，或说明无法执行的具体原因。
- 确认 AI 临时测试文件没有被暂存、提交或推送。
- 按 [verification-and-review](./verification-and-review.md) 自查。
- 确认没有修改无关文件。
- 更新受影响文档。
- 运行 `bash scripts/check-doc-links.sh` 确认文档路由有效。

---

## AI 提交硬门禁

AI 生成或辅助生成的代码必须接受与人工提交相同的门禁：

- 本地优先运行 `bash scripts/check.sh`。
- 可机器判定的规则进入 pytest / import-linter / ruff / check-plan.sh。
- 需要人工判断的规则进入 PR review。
- 涉及 LLM 调用、高风险分流、记忆写入时，必须声明审计点。
- 合入以 CI required checks 和 review 为准，不以 AI 自述为准。
