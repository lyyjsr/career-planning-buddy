# memories — 已激活长期记忆

| 字段 | 类型 | NULL | 默认/约束 | 说明 |
|---|---|---:|---|---|
| id | uuid | NO | PK | |
| user_id | uuid | NO | FK users.id ON DELETE CASCADE | |
| memory_type | varchar(32) | NO | profile_fact/stable_preference/execution_pattern | |
| summary | varchar(500) | NO | | 检索展示文本 |
| content_json | jsonb | NO | | 结构化内容 |
| sensitivity | varchar(16) | NO | normal/sensitive | 敏感项必须经过候选确认 |
| status | varchar(16) | NO | active/closed | |
| embedding | vector(1024) | YES | | 维度由配置和迁移锁定 |
| source_run_id | uuid | YES | FK agent_runs.id | 来源 |
| version | integer | NO | default 1 | 乐观锁 |
| last_used_at | timestamptz | YES | | |
| created_at | timestamptz | NO | now() | |
| updated_at | timestamptz | NO | now() | |

索引：`(user_id, status, memory_type)`；向量索引只对 active 且 embedding 非空数据建立。
