# intent_router — 意图分类

## 定位

先规则、后可选轻量结构化模型的受控路由节点。Agent Run 只支持生成初始计划和基于来源计划续接/调整；已有计划查询通过 REST 资源接口完成。

## Input

```python
class IntentInput(BaseModel):
    run_id: UUID
    message: str
    hint_intent: Literal["create_plan", "replan"] | None
    profile_summary: dict | None
    source_plan_id: UUID | None
    source_review_id: UUID | None
```

## Output

```python
class IntentResult(BaseModel):
    intent: Literal["create_plan", "replan", "unsupported"]
    replan_mode: Literal["initial", "continue", "adjust"]
    confidence: float = Field(ge=0, le=1)
    missing_slots: list[Literal[
        "goal_type", "stage", "time_budget_minutes", "skill_level"
    ]]
    effective_goal_type: GoalType | None
    requested_horizon_weeks: int | None = Field(default=None, ge=1, le=8)
    requires_fresh_information: bool
    method: Literal["rule", "model", "rule_fallback"]
```

## 规则

- `hint_intent` 只提高先验，不能绕过服务端校验；
- 规则先解析“未来 N 周/个月”等周期，统一裁剪为 1~8 周；不确定时交给结构化 router；
- 无 source plan 的首次生成：`intent=create_plan, replan_mode=initial`；
- 来源计划存在且用户只要求“继续/明天接着做”：`intent=replan, replan_mode=continue`；
- 来源 Review 建议调整，或用户明确提出减量、换重点、解决阻碍：`intent=replan, replan_mode=adjust`；
- 显式 source_plan 的归属在 Run 启动前由 Service 校验；可使用 generated/active/completed Plan，archived 仅在用户显式指定且属于自己时允许；
- Profile 缺核心字段时输出 missing_slots；
- 用户仅查询现有计划时输出 unsupported，并由 clarification 返回“请进入计划页查看”，不启动生成；
- 模型输出必须 Pydantic 校验，失败时用规则兜底；
- confidence 低于配置阈值且无法规则确定时输出 unsupported。

## Trace

intent、replan_mode、confidence、requested_horizon_weeks、missing_slots、method、model_id、prompt_version、token、latency。用户完整原文不重复写进 trace_data。
