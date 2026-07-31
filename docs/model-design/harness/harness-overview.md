# Harness 总览

## 在线控制

```text
BudgetGuard
  - max_llm_calls=4
  - max_tool_rounds=2
  - deadline=45s
  - tool_timeout=8s

TraceRecorder
  - agent_runs
  - agent_steps
  - tool_calls

EventRecorder
  - agent_events
  - sequence
  - SSE replay
```

## 离线反馈

```text
JSONL Dataset → Eval Runner → Rule Graders → Report → Bad Case
```

## 原则

- 每次外部调用可归因；
- 每个终态可解释；
- 不保存 API Key 和未脱敏敏感 Prompt；
- 评测失败不自动篡改 Prompt；
- Replay 不声称真实网络完全确定。
