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

**错误**：
| HTTP | code |
|---|---|
| 401 | AUTH_TOKEN_EXPIRED |
| 404 | NOT_FOUND_PROFILE（用户首次需先 PUT） |

## 端点：PUT /api/v1/profile

upsert 当前用户画像。**必填 Idempotency-Key**（R-Fail，状态机 + 版本约束）。

**请求 Schema** `ProfileUpsertRequest`：所有字段必填 OR 用 PATCH。

**成功响应 200** 完整 `UserProfile`。

**错误**：
| HTTP | code |
|---|---|
| 422 | VALIDATION_PROFILE_INVALID |
| 409 | STATE_VERSION_CONFLICT（version 不一致） |

## 示例

```http
PUT /api/v1/profile
Idempotency-Key: idem-9af2-bc11
{
  "goal_type": "agent_app",
  "stage": "mid",
  "time_budget_minutes": 180,
  "skill_level": "intermediate"
}
```

## Service / Repository 调用

- Router → `services.profile.upsert(user_id, request)` → `repositories.user_profile.upsert()`
- Service 守护：goal_type 默认 `unknown`；首次 PUT 必须显式提供

## 关联

- 表：[user_profiles.md](../data-models/user_profiles.md)
- 枚举：[schemas/enums.py GoalType](../../../backend/app/schemas/enums.py)
