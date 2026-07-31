# Plans API

## GET /api/v1/plans/active

返回状态为 generated 或 active 的当前计划。无计划返回 404。

## GET /api/v1/plans

Query：`status`, `cursor`, `limit`。返回 Cursor 分页历史。

## GET /api/v1/plans/{plan_id}

返回 PlanDetail 视图：

```json
{
  "plan_id": "c91f8734-2839-4f55-9db1-1c39b8a410f2",
  "status": "active",
  "summary": "本周优先把 Agent 项目做成可演示闭环",
  "rationale": "...",
  "adjustment_reason": null,
  "tasks": [],
  "sources": [],
  "companion_message": "...",
  "version": 2,
  "adopted_at": "...",
  "created_at": "..."
}
```

PlanDetail 由 plans、tasks、search_sources、companion_messages 拼装。

## GET /api/v1/plans/{plan_id}/sources

返回该计划产生 Run 的证据来源。

## 规则

- 用户只能读取自己的计划；
- 活跃计划定义为 generated/active；
- 新 replan 成功后旧活跃计划转 archived；
- 无单独“采纳”接口，首个任务开始即视为采纳。
