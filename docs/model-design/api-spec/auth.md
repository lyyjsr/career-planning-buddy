# auth.md — 鉴权与当前用户端点

状态：本轮实现。

> MVP 简化版：无 OAuth、无刷新 token；Bearer JWT 唯一。生产演进路径见 ADR-001 / 阶段 7。

## 端点：POST /auth/login

**请求 Schema** `app.schemas.auth.LoginRequest`：
| 字段 | 类型 | 必填 | 约束 |
|---|---|---|---|
| `token` | `str` | ✅ | OAuth state 或临时 guest token |

**成功响应 200** `LoginResponse`：
| 字段 | 类型 |
|---|---|
| `access_token` | `str`（JWT） |
| `token_type` | `Literal["bearer"]` |
| `expires_in` | `int`（秒，默认 86400） |
| `user_id` | `str` |

**错误**：
| HTTP | code | 触发 |
|---|---|---|
| 401 | AUTH_INVALID_TOKEN | token 无效 |
| 429 | RATE_LIMITED_AUTH | 同 IP > 10 次/分钟 |

**示例**：
```http
POST /auth/login
{"token":"guest-7c3e2f1a"}
```
```json
{
  "access_token": "eyJhb...",
  "token_type": "bearer",
  "expires_in": 86400,
  "user_id": "u-7c3e2f1a"
}
```

## 端点：GET /api/v1/me

读当前 token 对应的用户（**使用 /me 路径，不信任前端传入 user_id**）。

**成功响应** `UserProfile`（参 [profile.md](./profile.md) §`MeResponse`）。

**错误**：
| HTTP | code | 触发 |
|---|---|---|
| 401 | AUTH_TOKEN_EXPIRED | token 过期 |

## 安全要求

- 密码 bcrypt（如未来加 email login）
- HTTPS 强制（Caddy 自动 HTTPS）
- JWT secret 见 `.env.example JWT_SECRET`
- `Authorization: Bearer <jwt>` 必填
