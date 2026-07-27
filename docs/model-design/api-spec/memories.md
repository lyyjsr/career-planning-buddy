# memories.md — 记忆端点

状态：本轮实现。

## 端点：GET /api/v1/memories

列当前用户的记忆（按 type 分组）。

**Query 参数**：
| 参数 | 类型 | 默认 |
|---|---|---|
| `type` | `Literal["profile_fact","stable_preference","execution_pattern","session_temp"] \| null` | null |
| `include_sensitive` | `bool` | `false`（敏感内容默认不显示）|
| `cursor` | `str \| null` | null |
| `limit` | `int` | 50 |

**成功响应** `MemoryListResponse`：`{items: [Memory], next_cursor}`。

## 端点：DELETE /api/v1/memories/{memory_id}

用户删除自己的记忆（删除权 15 个工作日内响应，ADR-006）。

**成功响应 204**（无 body）。

**错误**：
| HTTP | code |
|---|---|
| 404 | NOT_FOUND_MEMORY |
| 403 | AUTH_NOT_OWN_MEMORY |

## 端点：PATCH /api/v1/memories/{memory_id}

切换记忆状态（关闭/激活）。**必填 Idempotency-Key + version**。

**请求 Schema** `UpdateMemoryRequest`：
| 字段 | 类型 | 必填 |
|---|---|---|
| `status` | `Literal["active","closed"]` | ✅ |
| `version` | `int` | ✅（乐观锁） |

**成功响应 200** 完整 `Memory`（新 version）。

**错误**：
| HTTP | code |
|---|---|
| 404 | NOT_FOUND_MEMORY |
| 403 | AUTH_NOT_OWN_MEMORY |
| 409 | STATE_VERSION_CONFLICT |
| 422 | VALIDATION_MEMORY_INVALID |

## 端点：GET /api/v1/memory-candidates

列待用户确认的记忆候选（来自 memory_candidates 表）。

**成功响应** `MemoryCandidateListResponse`。

## 端点：POST /api/v1/memory-candidates/{candidate_id}/confirm

用户确认候选。候选拷贝到 memories 激活。

**成功响应 200** `Memory`。

## 端点：POST /api/v1/memory-candidates/{candidate_id}/reject

用户拒绝。candidate 状态改 rejected。

**成功响应 200** `{status: "rejected"}`。

## 安全要求

- 敏感记忆默认不返回（`include_sensitive=true` 时额外鉴权）
- 用户只能看 / 改自己的记忆（user_id 严格校验，**不信任前端传入 user_id** [api-and-data-contracts §2](../../architecture/api-and-data-contracts.md)）

## 关联

- 表：[memories.md](../data-models/memories.md) + [memory_candidates.md](../data-models/memory_candidates.md)
- ADR-006：5 类记忆分层 + 敏感内容用户确认
- 写入：仅 persist 节点写 memories（R-IO2）；用户通过这些端点只能改/删
