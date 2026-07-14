# 契约规范（Pydantic + OpenAPI + 字段约束）

状态：本轮实现。

English summary: Single source for contract-first rules — Pydantic mandatory, OpenAPI snapshot in Git, field constraint patterns, breaking-change discipline.

## 1. 契约优先（R-Contract1）

**先定契约再写实现**，顺序：

```
spec.md / 节点 spec / 数据模型 spec
  ↓
Pydantic Schema (app/schemas/*.py)
  ↓
Mock Provider 契约测试
  ↓
Repository / Service / Router 实现
  ↓
真实 Provider 接入
```

**禁令**：从页面 / ORM 反推契约（[AGENTS.md R-Contract1](../../AGENTS.md)）。

## 2. Pydantic v2 强制

| 规则 | 来源 |
|---|---|
| 默认 `extra="forbid"` | R-Layer3 + python-coding-standards |
| 状态/分类用 `Literal[...]` 而非 `str` | Pydantic 推荐（autocompletion + mypy） |
| 数值约束用 `Annotated[int, Field(ge=0, le=100)]` | —— |
| 跨字段不变量用 `@model_validator(mode="after")` | —— |
| Structured output 复用 `Model.model_json_schema()` 喂给 LLM | [prompt-format-standard.md §3](./prompts/prompt-format-standard.md) |
| 派生字段不暴露给 LLM：用 `@computed_field` 但永远不写 model_json_schema 的 schema 部分（按需） | —— |

## 3. OpenAPI snapshot 入 Git

- 生成命令：`python -m app.api.openapi_gen > backend/contracts/openapi_snapshot.json`
- 每次 Router/Schema 改动 → 必须重新生成 snapshot
- CI 通过 `scripts/check-contracts.sh` 比对（已存在）
- 破坏性变更必须显式更新 snapshot（R-Contract2）

## 4. 字段约束模式（统一）

| 字段类型 | 推荐写法 |
|---|---|
| 字符串（含长度） | `str` + `Field(min_length=1, max_length=200)` |
| 枚举值 | `Literal["A","B","C"]` 不用 `enum.StrEnum` 在 schema 中（兼容性） |
| UUID | `str`（外露）→ 内部转 `uuid.UUID` |
| 时间 | `datetime`（Pydantic 自动 RFC 3339 序列化） |
| 数值（含范围） | `Annotated[int, Field(ge=0, le=100)]` |
| 列表（含数量） | `list[X]` + `Field(min_length=0, max_length=3)` |
| 嵌套对象 | 子 `BaseModel`（独立类，便于单测） |
| Optional | `str \| None = None`（Pydantic v2 语法，不是 `Optional[str]`） |

## 5. 版本演进

| 变更类型 | 是否破坏 | 处理 |
|---|---|---|
| 新增可选字段 | 兼容 | ✅ 自由加，snapshot 自动通过 |
| 新增必填字段 | 破坏 | 必须更新 snapshot + 加版本注释 |
| 删除字段 | 破坏 | 同上 |
| 改 field 类型 | 破坏 | 同上 |
| 改字段约束（缩小范围） | 破坏 | 同上 |
| 改字段约束（放宽范围） | 兼容 | ✅ |

## 6. Mock vs Production 契约一致性

- MockLLMProvider 必须满足 `LLMProvider` Protocol（[providers/protocols.py](../../backend/app/providers/protocols.py)）
- Mock 必须能产 schema_invalid / timeout 两类异常（[testing-and-tdd.md §Mock Provider](./testing-and-tdd.md)）
- Mock 与真实实现共享同一组 contract tests（tests/providers/）

## 7. 引用

- AGENTS.md R-Contract1 / R-Contract2 / R-Layer3
- [python-coding-standards.md §3 Pydantic](./python-coding-standards.md)
- [model-design/api-spec/](../model-design/api-spec/) 端点契约
- [model-design/data-models/](../model-design/data-models/) 表契约
- [testing-and-tdd.md](./testing-and-tdd.md) Pydantic 反例测试
