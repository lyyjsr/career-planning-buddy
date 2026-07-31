# Harness 设计

Harness 是围绕 Agent Runtime 的工程控制，不是额外 Agent。

| 模块 | 作用 | Stage |
|---|---|---:|
| Events | SSE 持久化与续传 | 2 |
| Trace | Run/Step/Tool 记录 | 2 |
| Budget | 次数、Token、超时 | 2 |
| Replay | 固定输入和 Tool fixture 重跑 | 5 |
| Eval | 固定数据集和 Grader | 5 |

- [总览](./harness-overview.md)
- [实现结构](./implementation-structure.md)
- [Replay](./replay.md)
- [Eval](./eval-system.md)
