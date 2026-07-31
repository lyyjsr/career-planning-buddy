# rule_validator — 计划规则校验

## Input

PlanCandidate + PlanningContext。

## Output

```python
ValidationReport(
  passed: bool,
  checks: list[ValidationCheck],
  repair_instructions: list[str]
)
```

## 必检规则

1. 任务数量 1~3；
2. 当日总预计时间不超过 time_budget_minutes；
3. starter_action 以明确动作开头且含具体对象；
4. deliverable 可观测；
5. scheduled_date 合理；
6. 不重复最近已完成任务；
7. replan 体现 blocker/adjustment_request；
8. source_id 都存在且属于当前 Run；
9. 不擅自改目标方向；
10. 文本字段长度符合 Schema。

本节点不调用 LLM。连续性无法确定时可在 Stage 5 交给 quality_reviewer，但不能阻塞基础规则。
