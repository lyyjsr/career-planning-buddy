# revise_or_fallback — 修复或降级

## 决策

```text
validation pass → companion_response
validation fail + repair_count=0 → 调主模型按 repair_instructions 修复一次
validation fail + repair_count>=1 → 模板降级
```

## Output

```python
ReviseDecision(
  action: Literal["pass", "repair", "fallback"],
  candidate: PlanCandidate | None,
  fallback_reason: str | None,
  repair_count: int
)
```

模板降级仍需生成 1 个符合时间预算的基础任务，并把 Run 终态设为 degraded。不得无限循环。
