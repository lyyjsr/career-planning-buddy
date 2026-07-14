# users.md — 用户基本信息

状态：本轮实现。

## 字段

| 字段 | 类型 | NULL | 默认 | 约束 | 说明 |
|---|---|---|---|---|---|
| id | `uuid` | NO | `gen_random_uuid()` | PK | UUIDv4 |
| brief_login_type | `varchar(32)` | NO | `'guest'` | CHECK ∈ {`guest`,`email`,`oauth_wechat`,`oauth_github`} | 登录方式（MVP 多为 guest） |
| email | `varchar(255)` | YES | NULL | UNIQUE IF NOT NULL | 邮箱（可选） |
| display_name | `varchar(64)` | YES | NULL | — | 显示名（可空） |
| is_active | `boolean` | NO | `true` | — | 软删除用 |
| created_at | `timestamptz` | NO | `now()` | — | UTC |
| updated_at | `timestamptz` | NO | `now()` | 触发器自动更新 | UTC |
| deleted_at | `timestamptz` | YES | NULL | — | 软删除时间（15 天清除） |

## 索引

| 索引名 | 字段 | 类型 | 用途 |
|---|---|---|---|
| `users_pkey` | id | btree | PK |
| `users_email_idx` | email | btree | 唯一（partial WHERE NOT NULL） |

## 外键

无（顶层实体）。

## 示例行

```sql
INSERT INTO users (id, brief_login_type, email, display_name)
VALUES ('u-7c3e2f1a-...', 'oauth_github', 'alice@example.com', 'Alice');
```

## 命名约定

- 主键统一 `id` 不带表名前缀（除 agent_steps.id 等使用 step_id 等业务名时）
- snake_case 字段名
- `created_at`/`updated_at`/`deleted_at` 三件套用于所有表
