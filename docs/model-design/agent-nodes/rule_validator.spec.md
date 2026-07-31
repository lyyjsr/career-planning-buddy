# rule_validator — 计划规则校验

## Input

`PlanCandidate + PlanningContext + evidence_catalog`。

## Output

```python
class ValidationCheck(BaseModel):
    code: str
    passed: bool
    message: str
    task_index: int | None = None

class ValidationReport(BaseModel):
    passed: bool
    checks: list[ValidationCheck]
    repair_instructions: list[str]
```

## 稳定检查码

| code | 规则 |
|---|---|
| HORIZON_MATCH | plan_date/horizon 与 PlanningWindow 完全一致 |
| WEEKLY_FOCUS | 1~8 条、week_index 连续不重复、包含 success_signal |
| TASK_COUNT | 当日任务数量 1~3 |
| TIME_BUDGET | 总预计时间不超过 time_budget_minutes |
| STARTER_ACTION | 每项有明确动作和对象 |
| DELIVERABLE | 每项有可观测产物 |
| SCHEDULE_DATE | 所有 Task 日期必须等于 planning_date |
| RECENT_DUPLICATE | 不重复近期已完成交付物 |
| REPLAN_CONTINUITY | continue 保持方向并推进；adjust 保留 completed facts 并回应 blocker |
| SOURCE_INTEGRITY | evidence_ref 存在于当前 Run evidence_catalog 且类型匹配 |
| GOAL_IMMUTABLE | 不擅自改变 effective_goal_type |
| TEXT_LENGTH | 所有文本满足 Schema 长度 |
| TASK_UNIQUENESS | 本批任务标题/交付物不重复 |

## 实现规则

- 本节点不调用 LLM；
- 所有检查顺序固定，保证测试和 Replay 可比较；
- `repair_instructions` 从检查码映射生成，不把内部异常栈交给模型；
- 必检规则失败时 `passed=false`；
- 连续性中的“方向是否完全合理”等主观质量可交给离线 reviewer，但不得替代确定性检查；
- 验证器不修改 Candidate。

## 测试

每个检查码至少一个独立失败用例，并覆盖多个错误同时返回、evidence id 越权、5 周窗口、今日日期、continue/adjust 连续性和边界时间预算。
