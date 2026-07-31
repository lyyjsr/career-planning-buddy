# context_builder — 上下文构建

## Input

run_id、user_id、resolved_intent、goal_type。

## Output PlanningContext

```python
PlanningContext(
  profile: ProfileContext,
  active_plan: PlanContext | None,
  recent_tasks: list[TaskContext],
  recent_reviews: list[ReviewContext],
  memories: list[MemoryContext],
  experience_atoms: list[EvidenceContext],
  search_sources: list[EvidenceContext],
  token_estimate: int
)
```

## 数据来源

- Profile、最近 7 天 Task/Review：Stage 2；
- Memory、RAG、Search：Stage 4；
- 所有查询必须按 user_id 过滤。

## 预算顺序

Profile > 当前计划 > 最近任务/复盘 > 记忆 > RAG > 搜索。超预算时先丢低可信来源，再做确定性摘要。

本节点只读，不更新 last_used_at；需要统计使用次数时由 Service 单独写入。
