# 测试与 TDD

状态：本轮实现。

English summary: Testing strategy — pytest layering, contract tests, fault injection, eval regression.

---

## 0. 测试分层

测试文件跟随被测代码，放 `backend/tests/<对应包>/`。

| 层 | 测试位置 | 工具 |
|---|---|---|
| `schemas/` | `tests/schemas/` | pytest + Pydantic 校验 |
| `services/` | `tests/services/` | pytest + Mock Repository |
| `repositories/` | `tests/repositories/` | testcontainers python (Postgres) |
| `agent/` | `tests/agent/` | pytest + Mock Provider |
| `api/` | `tests/api/` | FastAPI TestClient |
| `providers/` | `tests/providers/` | Mock 与真实 Provider 共享契约 |
| `evals/` | `tests/eval/` | 固定数据集 + 自动 grader |

---

## 1. Schema 测试

- 每个 Pydantic 模型至少测：
  - 必填缺失 → `ValidationError`
  - `extra="forbid"` → 多余字段报错
  - 枚举非法值 → 报错
  - 约束边界（max_length / ge / le）

```python
import pytest
from pydantic import ValidationError
from app.schemas.agent_run import IntentResult, IntentType

def test_intent_result_missing_intent():
    with pytest.raises(ValidationError):
        IntentResult(confidence=0.8, needs_clarification=False)

def test_intent_result_confidence_out_of_range():
    with pytest.raises(ValidationError):
        IntentResult(intent=IntentType.CREATE_PLAN, confidence=1.5, needs_clarification=False)
```

---

## 2. Service 测试

- 用 Mock Repository 注入。
- 覆盖 happy path + 非法状态转移 + 降级路径。

```python
class FakeAgentRunRepository:
    def __init__(self): self.saved = []
    async def save(self, run, session): self.saved.append(run); return run

async def test_start_run_persists_initial_state():
    repo = FakeAgentRunRepository()
    svc = AgentRunService(repo, graph=MockGraph())
    run = await svc.start_run(StartRunRequest(...))
    assert run.status == RunStatus.PENDING
    assert len(repo.saved) == 1
```

---

## 3. Repository 测试

- 用 `testcontainers-python` 起真实 PostgreSQL。
- 覆盖 save / get / update / 分页。
- 验证 Alembic 迁移在干净库上可执行。

```python
from testcontainers.postgres import PostgresContainer

@pytest.fixture(scope="module")
def pg():
    with PostgresContainer("pgvector/pgvector:pg16") as pc:
        yield pc
```

---

## 4. Agent / 节点测试

- 每个 `.spec.md` 的不变量应翻译成断言。
- 用 MockLLMProvider 返回预设响应，覆盖 happy/fail/降级。
- 故障注入：Provider 超时 / 返回非 schema / 空结果。

```python
class MockLLMProvider:
    def __init__(self, response): self.response = response
    async def complete(self, messages, schema, tools, budget):
        return self.response

async def test_intent_router_invalid_output_retries():
    provider = MockLLMProvider(response={"invalid": "json"})
    node = IntentRouter(provider)
    result = await node.run(...)
    assert result.status == NodeStatus.DEGRADED
    assert result.fallback_reason is not None
```

---

## 5. API 测试

- 用 `httpx.AsyncClient` + FastAPI `TestClient`。
- 覆盖：成功、校验失败、未认证、错误码、SSE 事件流。

```python
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_create_agent_run_returns_202():
    resp = client.post("/api/v1/agent-runs", json={...})
    assert resp.status_code == 202
    assert "run_id" in resp.json()
```

---

## 6. 契约测试（OpenAPI snapshot）

- `check-contracts.sh` 比对 `app.api.openapi_gen` 输出与 Git snapshot。
- 破坏性变更必须显式更新 snapshot；兼容性（新增字段）自动通过。

---

## 7. 故障注入

- 用 `pytest.mark.parametrize` 覆盖：
  - LLM 超时（> 3s）
  - LLM 返回不符 schema
  - Search 超时
  - DB 连接失败
- 期望：节点 degrade / fail，带 `fallback_reason`，不静默。

---

## 8. Eval 回归（阶段 5）

- 固定数据集（30 case，含正常 / 异常 / 边界）。
- 自动 grader：5 维质量评分 + 任务结构校验 + 来源覆盖率。
- 通过率阈值：≥ 85%，低于则 CI 阻断。
- Bad Case 一键加入评测集（闭环）。

---

## 9. 覆盖率

- 目标：schemas/services ≥ 90%，agent/nodes ≥ 80%。
- `pytest --cov=app --cov-report=term-missing`。
- 覆盖率不达标不阻断 CI（避免假阳），但进 PR 报告供 review。

---

## 10. AI 临时测试

- AI 为验证实现临时编写的测试，默认**不得暂存、提交或推送**。
- 用户明确要求"作为正式测试提交"时才纳入版本控制。
