# Developer Trace 页面

## 列表

展示：Run ID、状态、意图、模型、成本、Token、耗时、fallback、时间。

## 详情

时间轴：

```text
run.created
risk_gate
intent_router
context_builder
career_planning_agent
rule_validator
persist
run.completed
```

每个 Step 展示脱敏输入摘要、输出摘要、模型、Token、耗时和错误。Tool 展示参数 hash、结果摘要和 latency。

开发者可发起 Replay，但必须明确显示是否使用 Tool fixture、是否真实联网以及目标 model/prompt version。
