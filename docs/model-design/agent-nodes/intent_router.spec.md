# intent_router — 意图分类

## Input

```python
IntentInput(
  run_id: UUID,
  message: str,
  hint_intent: Literal["create_plan", "replan", "query_plan"] | None,
  profile_summary: dict | None,
  source_plan_id: UUID | None
)
```

## Output

```python
IntentResult(
  intent: Literal["create_plan", "replan", "query_plan", "unsupported"],
  confidence: float,
  missing_slots: list[Literal["goal_type", "stage", "time_budget_minutes", "skill_level"]],
  goal_type: GoalType | None,
  requires_fresh_information: bool
)
```

## 规则

- `hint_intent` 只能提高先验，不能绕过校验；
- replan 必须能解析到属于当前用户的 source_plan_id；
- Profile 缺核心字段时输出 missing_slots；
- query_plan 走只读 Service，不进入生成 Graph；
- 模型输出必须 Pydantic 校验，失败时用规则兜底。

## Trace

intent、confidence、missing_slots、model_id、prompt_version、token、latency。
