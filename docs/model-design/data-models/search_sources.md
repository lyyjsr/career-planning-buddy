# search_sources.md — 联网搜索结果快照

状态：本轮实现。

## 字段

| 字段 | 类型 | NULL | 默认 | 约束 | 说明 |
|---|---|---|---|---|---|
| id | `uuid` | NO | `gen_random_uuid()` | PK | —— |
| run_id | `uuid` | YES | NULL | FK→agent_runs.id | 来源所属 run（可空表示离线蒸馏） |
| query | `text` | NO | — | max 200 | 触发该结果的搜索 query |
| url | `text` | NO | — | NOT NULL | 原文 URL |
| title | `text` | NO | — | max 200 | 标题 |
| snippet | `text` | NO | — | max 500 | 内容摘要 |
| source_type | `varchar(16)` | NO | `'unknown'` | CHECK ∈ {`official`,`community`,`news`,`blog`,`unknown`} | 来源类型 |
| reliability | `float` | NO | `0.5` | CHECK between 0 and 1 | 可靠度评分（来自 Tavily 或自评估） |
| retrieved_at | `timestamptz` | NO | `now()` | —— | 检索时间 |
| expires_at | `timestamptz` | NO | `now() + interval '90 days'` | —— | 90 天后归档不再进上下文（与 experience_atoms 同策略） |

## 索引

| 名 | 字段 | 用途 |
|---|---|---|
| idx_sources_run | (run_id, retrieved_at) | run 内溯源 |
| idx_sources_url | url | 同 URL 去重 |

## 外键

`run_id → agent_runs.id ON DELETE SET NULL`

## 示例行

```sql
INSERT INTO search_sources (id, run_id, query, url, title, snippet, source_type, reliability)
VALUES ('ss-9a8b-...', 'r-2a8f-...', 'DeepSeek V4 工具调用 API',
        'https://api-docs.deepseek.com/guides/function_calling',
        'Function Calling - DeepSeek API',
        'DeepSeek 支持 OpenAI 兼容的 function calling...',
        'official', 0.95);
```

## 关联

- `distill_evidence` 节点（[spec](../agent-nodes/distill_evidence.spec.md)）读此表，蒸馏为 `experience_atoms`
- web_search Tool 输出（[TDD §6.1](../../architecture/tdd.md)）
- 动态结论必须带来源（[PRD §6 来源标注](../../overview/product-overview.md)）
