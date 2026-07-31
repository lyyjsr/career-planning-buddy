# Harness 代码结构

```text
backend/app/harness/
├── budget.py
├── events.py
├── trace.py
├── redaction.py
└── replay.py

backend/evals/
├── datasets/
│   └── career_plan_v1.jsonl
├── graders/
├── runner.py
└── report.py
```

## 调用位置

- Graph 节点包装器负责 step trace；
- ToolRegistry 包装器负责 tool trace；
- AgentRunService 负责 run 终态；
- EventRecorder 负责持久化并通知 SSE；
- Eval Runner 使用 Mock 或指定真实 Provider，不走生产用户数据。
