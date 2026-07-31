# companion_response — 陪伴话术

## 策略

模板优先，只有复杂复盘场景才可调用轻量模型。这样降低成本和不稳定性。

## trigger_tag

- plan_ready
- first_task_started
- task_completed
- task_abandoned
- review_saved
- replan_suggested
- next_day

## Output

```python
CompanionMessageCandidate(trigger_tag: str, message: str, template_version: str | None)
```

## 规则

- 引用具体完成内容，不泛泛夸奖；
- 放弃时不评判；
- 连续完成不自动加量；
- 情绪低落时共情但不诊断；
- 最长 500 字；
- 任务 PATCH 的常见话术用模板，不为每次状态更新调用 LLM。
