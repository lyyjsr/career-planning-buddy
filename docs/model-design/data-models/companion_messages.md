# companion_messages.md — 陪伴话术存储

状态：本轮实现。

> 解决 [gap-analysis §8.4](../feature-flows/gap-analysis.md) 的"companion_message 归属"问题：plan/review/task 三处都可能触发 companion_response 节点产生话术，统一存本表，前端按主实体查询时 JOIN 拼接到响应视图。

## 字段

| 字段 | 类型 | NULL | 默认 | 约束 | 说明 |
|---|---|---|---|---|---|
| id | `uuid` | NO | `gen_random_uuid()` | PK | —— |
| user_id | `uuid` | NO | — | FK→users.id ON DELETE CASCADE | —— |
| run_id | `uuid` | YES | NULL | FK→agent_runs.id ON DELETE SET NULL | 关联 run（plan_run 内生成时填）|
| plan_id | `uuid` | YES | NULL | FK→plans.id ON DELETE CASCADE | 关联 plan |
| review_id | `uuid` | YES | NULL | FK→reviews.id ON DELETE CASCADE | 关联 review（复盘触发的陪伴）|
| task_id | `uuid` | YES | NULL | FK→tasks.id ON DELETE CASCADE | 关联 task（任务完成/放弃触发的陪伴）|
| trigger_tag | `varchar(8)` | NO | — | CHECK ∈ {`T1`,`T2`,`T3`,`T4`,`T5`,`T6`} | 6 触发时刻（[companion_response.spec.md §1](../agent-nodes/companion_response.spec.md)）|
| tone | `varchar(16)` | NO | — | CHECK ∈ {`empathetic`,`encouraging`,`celebrating`,`calming`} | —— |
| message | `text` | NO | — | max 500 | 实际话术内容 |
| fallback_used | `boolean` | NO | `false` | —— | 是否用模板兜底（LLM 失败时） |
| created_at | `timestamptz` | NO | `now()` | —— | —— |

## 索引

| 名 | 字段 | 用途 |
|---|---|---|
| PK | id | —— |
| idx_cm_user_created | (user_id, created_at DESC) | 用户最近话术历史 |
| idx_cm_plan | (plan_id, created_at DESC) WHERE plan_id IS NOT NULL | plan 视图组装 |
| idx_cm_review | (review_id) WHERE review_id IS NOT NULL | review 视图组装 |
| idx_cm_task | (task_id) WHERE task_id IS NOT NULL | task 视图组装 |

## 约束（对应 companion_response INV）

| ID | 不变量 | DB 落地方式 |
|---|---|---|
| INV-1 | trigger_tag=T2 → tone ∈ {empathetic, calming} | 应用层 Service 守（DB CHECK 难表达跨字段） |
| INV-2 | trigger_tag=T3 → tone=celebrating | 同上 |
| INV-3 | 不得包含内疚诱导词 | 应用层校验（写前正则） |
| INV-4 | 不得加量 | 应用层（companion_response 节点输出时已守） |

## 主实体优先级

由于 plan/review/task 三者都可能为 null（除 user_id 外），但实际语义是一次话术关联到**正好 1 个主实体**（plan 或 review 或 task）。Service 写入时校验：

```text
assert (plan_id is None) + (review_id is None) + (task_id is None) == 2  # 恰好一个非空
```

或用 CHECK 约束（PostgreSQL 15+）：

```sql
ALTER TABLE companion_messages ADD CONSTRAINT chk_exactly_one_subject CHECK (
  (plan_id IS NOT NULL)::int + (review_id IS NOT NULL)::int + (task_id IS NOT NULL)::int = 1
);
```

## 示例行

```sql
-- plan 创建时的欢迎话术
INSERT INTO companion_messages (id, user_id, run_id, plan_id, trigger_tag, tone, message)
VALUES ('cm-1...', 'u-7c3e...', 'r-2a8f...', 'p-9e2a...', 'T6', 'encouraging',
        '欢迎！我会基于你的目标先给 3 个可启动任务，今天先完成 1 个就够。');

-- 任务完成时的庆祝
INSERT INTO companion_messages (id, user_id, task_id, trigger_tag, tone, message)
VALUES ('cm-2...', 'u-7c3e...', 't-1a8b...', 'T3', 'celebrating',
        '你已经完成了第 1 个任务「整理技术难点」。这是后续面试讲故事的关键素材，做得很扎实。');

-- 复盘触发的减量共情
INSERT INTO companion_messages (id, user_id, review_id, trigger_tag, tone, message)
VALUES ('cm-3...', 'u-7c3e...', 'rv-3b4f...', 'T2', 'empathetic',
        '昨天太累没做完很正常，今天任务给你减量了。');
```

## 关联

- 节点：[companion_response.spec.md](../agent-nodes/companion_response.spec.md)
- 写入入口：仅 `services.companion.write_message()`（在企业事务内调用，受 persist 节点 INV-1 守护）+ task/review service 副作用调用
- 视图组装：PlanDetail / ReviewResult / UpdateTaskResponse 都用它做 `companion_message` 字段投影

## 与现有 spec 的对齐

- [api-and-data-contracts.md §5.2 PlanDetail.companion_message](../../architecture/api-and-data-contracts.md)：本表中 plan_id 关联行的最近一条 `message`
- [api-spec/tasks.md UpdateTaskResponse.companion_message](../api-spec/tasks.md)：本表中 task_id 关联行的最近一条 `message`
- [api-spec/reviews.md ReviewResult.companion_message](../api-spec/reviews.md)：本表中 review_id 关联行的最近一条 `message`
