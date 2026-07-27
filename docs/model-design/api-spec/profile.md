# profile.md — 用户画像端点

状态：本轮实现。

## 端点：GET /api/v1/profile

读当前用户画像（一对一）。

**成功响应 200** `UserProfile`（参 [user_profiles.md](../data-models/user_profiles.md)）：
| 字段 | 类型 |
|---|---|
| `goal_type` | `Literal["ai_backend","agent_app","backend_java","data_engineer","fullstack","other"]` |
| `stage` | `Literal["early","mid","late","unknown"]` |
| `time_budget_minutes` | `int 15-480` |
| `skill_level` | `Literal["beginner","intermediate","advanced"]` |
| `skill_summary` | `str \| null` |
| `employment_status` | `Literal["student_year_4","fresher","working","gap"] \| null` |
| `deadline` | `date \| null` | 求职截止日（如"2026-10-31秋招"） |
| `target_companies` | `list[str] \| null` | 由 `profile_preferences.target_companies` 投影 |
| `preferences` | `dict \| null` | 透传 `profile_preferences` jsonb |

**错误**：
| HTTP | code |
|---|---|
| 401 | AUTH_TOKEN_EXPIRED |
| 404 | NOT_FOUND_PROFILE（用户首次需先 PUT） |

## 端点：PUT /api/v1/profile

upsert 当前用户画像（**首次建档**主路径）。**必填 Idempotency-Key**（R-Fail，状态机 + 版本约束）。

**请求 Schema** `ProfileUpsertRequest`：

| 字段组 | 字段 | 必填 | 备注 |
|---|---|---|---|
| 3 必填（PRD §5.2） | `goal_type` / `stage` / `time_budget_minutes` | ✅ | 不满足返 422 VALIDATION_PROFILE_INCOMPLETE |
| 推荐 | `skill_level` | ✅ | |
| 可选 | `skill_summary` (max 2000) | ❌ | 自由文本（**决策点 7**：以自由文本为唯一入口；如需结构化 tag，由 service 提取入 profile_preferences） |
| 可选 | `employment_status` | ❌ | |
| 可选 | `deadline`（ISO date） | ❌ | 落入 user_profiles.deadline 列（计划计算用） |
| 可选 | `preferences`（jsonb object） | ❌ | 含 target_companies / preferred_time_slot / 等；落入 user_profiles.profile_preferences 列 |

**成功响应 200** 完整 `UserProfile`（含新 version）。

**错误**：
| HTTP | code |
|---|---|
| 422 | VALIDATION_PROFILE_INVALID |
| 422 | VALIDATION_PROFILE_INCOMPLETE（3 必填缺失） |
| 409 | STATE_VERSION_CONFLICT（version 不一致） |

> 注：架构层 [api-and-data-contracts.md §10.2 破坏性变更](../../architecture/api-and-data-contracts.md) 要求 PUT 移除/改名旧字段属于破坏性变更——本 spec 不支持修改既有字段的语义。

## 端点：PATCH /api/v1/profile

更新用户画像的**部分字段**（首次建档后的"可后补"场景，PRD §5.2）。**必填 Idempotency-Key + version**。

**请求 Schema** `ProfilePatchRequest`：任何 UserProfile 字段（除 `version`）的子集 + 必填 `version`。

**成功响应 200** 完整 `UserProfile`（含新 version）。

**错误**：
| HTTP | code |
|---|---|
| 422 | VALIDATION_PROFILE_INVALID |
| 404 | NOT_FOUND_PROFILE（PATCH 不能用于首次建档，需先 PUT）|
| 409 | STATE_VERSION_CONFLICT |

## 示例

```http
PUT /api/v1/profile
Idempotency-Key: idem-9af2-bc11
{
  "goal_type": "agent_app",
  "stage": "mid",
  "time_budget_minutes": 180,
  "skill_level": "intermediate",
  "deadline": "2026-10-31"
}
```

```http
PATCH /api/v1/profile
Idempotency-Key: idem-a41f
If-Match-Version: 3
{"skill_summary":"熟悉 FastAPI/Postgres/LangChain，做过 2 个 RAG 项目",
 "preferences":{"target_companies":["字节","蚂蚁"],"preferred_time_slot":"morning"}}
```

## Service / Repository 调用

- Router → `services.profile.upsert(user_id, request)` → `repositories.user_profile.upsert()`
- Service 守护：goal_type 默认 `unknown`；首次 PUT 必须显式提供

## 关联

- 表：[user_profiles.md](../data-models/user_profiles.md)
- 枚举：[schemas/enums.py GoalType](../../../backend/app/schemas/enums.py)
