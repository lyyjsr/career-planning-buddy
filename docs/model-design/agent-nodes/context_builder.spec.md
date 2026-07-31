# context_builder — 上下文构建

## 定位

确定性只读节点。负责把数据库事实转换成受预算约束、可序列化、可回放的 `PlanningContext`。它不调用主模型，不执行 Web Search，也不写业务状态。

## Input

```python
class ContextBuilderInput(BaseModel):
    run_id: UUID
    user_id: UUID
    intent: Literal["create_plan", "replan"]
    replan_mode: Literal["initial", "continue", "adjust"]
    effective_goal_type: GoalType
    source_plan_id: UUID | None
    requested_horizon_weeks: int | None
```

## Output

```python
class PlanningWindow(BaseModel):
    planning_date: date
    horizon_start: date
    horizon_end: date
    horizon_weeks: int = Field(ge=1, le=8)

class PlanningContext(BaseModel):
    profile: ProfileContext
    planning_window: PlanningWindow
    active_plan: PlanContext | None
    source_plan: PlanContext | None
    source_review: ReviewContext | None
    recent_tasks: list[TaskContext]
    recent_reviews: list[ReviewContext]
    pinned_memories: list[MemoryContext]
    completed_facts: list[CompletedFact]
    blockers: list[str]
    timezone: str
    time_budget_minutes: int
    token_estimate: int
```

## 规划窗口

- 首次规划或用户手动即时调整时，`planning_date` 使用用户时区的本地日期；
- 从 Review 执行 `start-next-plan` 时，`planning_date=max(用户本地今日, review_date + 1 天)`，避免复盘后又生成同一天任务；
- 用户明确“未来 N 周”时，规则解析 `requested_horizon_weeks`，范围 1~8；
- 未明确时，优先根据 profile.deadline 计算，最多展开 8 周；
- 没有 deadline 时默认 4 周；
- `horizon_start=planning_date`，`horizon_end` 按周数确定并冻结到 input snapshot；
- Agent 不得自行扩大或缩短窗口。

## 数据来源与上限

| 数据 | 上限 | 规则 |
|---|---:|---|
| Profile | 1 | 必须是当前用户最新 version |
| Active/Source Plan | 各 1 | replan 的 source_plan 必须属于当前用户，可为 generated/active/completed |
| Source Review | 1 | 从 `/reviews/{id}/start-next-plan` 创建时注入 |
| Recent Tasks | 14 天内最多 30 | 优先 completed/abandoned/in_progress |
| Recent Reviews | 最近 7 条 | 只取规划相关字段 |
| Pinned Memories | 最多 5 | 仅 active、已确认、当前用户 |
| Completed Facts | 最多 20 | 从任务事实确定性生成 |
| Blockers | 最多 10 | 从 abandoned/review 结构化字段提取 |

Stage 4 的更多 Memory/RAG/Search 由 Agent 通过 Tool 按需获取，避免 `context_builder` 与 Tool 重复检索。

## 预算和裁剪顺序

Profile > planning window > source/active plan > completed facts > 当前未完成任务 > source/recent review > blockers > pinned memories。

超预算时：

1. 删除低优先级和重复项；
2. 对历史文本做确定性字段投影，不调用 LLM；
3. 仍超预算则只保留最近和最相关记录；
4. 记录 dropped counts 和 token_estimate 到 Trace。

## 快照

节点完成后由 SnapshotService 幂等写入 `agent_runs.input_snapshot_json`。快照存 id/version、planning window 和必要字段，不保存 ORM 对象、无关隐私和 Provider 凭据。Replay 使用快照，不重新读取用户当前画像。

## 不变量

- 所有查询按 user_id 过滤；
- 不更新 memory.last_used_at 等业务字段；
- 不把高风险原文写入上下文快照；
- 不把搜索结果或模型输出伪装成数据库事实；
- replan 必须包含 source_plan、completed_facts 与 blockers；
- continue 模式优先使用最近完成 Plan，adjust 模式优先使用触发调整的 Review。

## 测试

- 用户隔离；
- create_plan/continue/adjust 三种上下文；
- source_plan 越权；
- 5 周解析、deadline 推导、默认 4 周与 8 周上限；
- 当天 Review 触发 next plan 时 planning_date 自动进入次日；
- 预算裁剪稳定且确定；
- 快照在原数据改变后仍不变；
- 高风险敏感字段不进入 snapshot。
