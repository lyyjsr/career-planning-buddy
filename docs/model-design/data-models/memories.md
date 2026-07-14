# memories.md — 长期记忆（5 类分层）

状态：本轮实现。

## 字段

| 字段 | 类型 | NULL | 默认 | 约束 | 说明 |
|---|---|---|---|---|---|
| id | `uuid` | NO | `gen_random_uuid()` | PK | —— |
| user_id | `uuid` | NO | — | FK→users.id | —— |
| memory_type | `varchar(32)` | NO | — | CHECK ∈ {`profile_fact`,`stable_preference`,`execution_pattern`,`session_temp`} | 4 类型（敏感内容不入此表，走 memory_candidates） |
| content_json | `jsonb` | NO | — | —— | 按 type 不同结构 |
| sensitivity | `varchar(16)` | NO | `'none'` | CHECK ∈ {`none`,`sensitive`} | 标记 |
| embedding | `vector(1024)` | YES | NULL | —— | DeepSeek Embedding 1024 维（仅 type=execution_pattern 等需要检索的类型） |
| confidence | `float` | NO | `1.0` | CHECK between 0 and 1 | 行为挖掘的置信度（profile_fact=1.0） |
| expires_at | `timestamptz` | YES | NULL | —— | type=session_temp 24h 后自动过期；execution_pattern 90 天归档 |
| created_at | `timestamptz` | NO | `now()` | —— | —— |
| last_used_at | `timestamptz` | YES | NULL | —— | 检索访问时间（按时间降权用） |
| source | `varchar(16)` | NO | `'user'` | CHECK ∈ {`user`,`agent_proposal`,`agent_observed`} | 来源标记 |

## 索引

| 名 | 字段 | 类型 | 用途 |
|---|---|---|---|
| idx_memory_user_type | (user_id, memory_type) | btree | 类型筛选 + 同类内查 |
| idx_memory_embedding | embedding | **ivfflat** (pgvector) | 余弦相似度 RAG |
| idx_memory_expires | (expires_at) WHERE expires_at IS NOT NULL | btree | TTL 清理任务 |

## 外键

`user_id → users.id ON DELETE CASCADE`

## 示例行

```sql
INSERT INTO memories (id, user_id, memory_type, content_json, sensitivity, confidence, source)
VALUES ('m-5e6f-...', 'u-7c3e2f1a-...', 'stable_preference',
        '{"key":"task_count","value":2,"note":"用户偏好每日 2 个任务"}',
        'none', 0.85, 'agent_observed');
```

## 关联

- 敏感记忆（health/finance/family/strong_emotion）默认不入此表，走 [memory_candidates（候选池）](./memory_candidates.md)，用户确认后才激活
- Embedding 1024 维严格校验（DeepSeek Embedding 维度）
- 5 类生命周期见 [ADR-006 记忆系统](../../architecture/adr.md)
- 检索于 [intent_router 之后的 context_builder 节点](../agent-nodes/context_builder.spec.md) 通过 Tool `memory_lookup`
