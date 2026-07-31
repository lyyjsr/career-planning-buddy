# career_planning_agent — 核心规划 Agent

## 定位

系统唯一真 Agent。根据 PlanningContext 选择白名单 Tool 并生成结构化计划候选，不直接写数据库。

## 预算

| 项 | 上限 |
|---|---:|
| Tool Calling 轮次 | 2 |
| Tool 调用总数 | 4 |
| 主模型调用总数 | 3（含最终生成） |
| 单 Tool 超时 | 8s |
| Agent 节点超时 | 30s |

## 可用 Tool

- Stage 2：context_summarize（可选，确定性实现）；
- Stage 4：memory_lookup、web_search、rag_retrieve。

## Output

```python
PlanCandidate(
  summary: str,
  rationale: str,
  adjustment_reason: str | None,
  assumptions: list[str],
  tasks: list[TaskCandidate],
  source_ids: list[UUID]
)

TaskCandidate(
  title: str,
  task_type: TaskType,
  scheduled_date: date,
  starter_action: str,
  deliverable: str,
  estimated_minutes: int,
  rationale: str | None
)
```

## 不变量

- 任务 1~3 个；
- source_ids 只能来自 Tool 结果；
- 不允许自行改变用户 goal_type；
- replan 不得删除已完成事实；
- 不输出 SQL、命令或业务写入指令；
- Pydantic 解析失败最多修复一次。

## Prompt

Prompt 代码位于 `backend/app/prompts/career_planning/`，使用显式 version。Trace 记录实际 `LLM_MODEL`，不得写死项目代号。
