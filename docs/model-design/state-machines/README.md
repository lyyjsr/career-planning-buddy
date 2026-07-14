# state-machines/ 状态机 spec 入口

状态：本轮实现。

English summary: Each state machine has its own .mmd file (mermaid diagram) + a transition matrix. Authoritative single source for legal state transitions to be encoded in Pydantic validators and Service layer.

## 定位

每个关键状态机单文件，作为单一事实源；不在 TDD/API 契约/节点 spec 重复定义，引用本目录即可。

## 状态机清单

| # | 实体 | 关键状态 | mmd |
|---|---|---|---|
| 1 | plan_run | pending → running → completed/failed/degraded | [run-status.mmd](./run-status.mmd) |
| 2 | task | pending → in_progress → completed/abandoned/expired | [task-state.mmd](./task-state.mmd) |
| 3 | plan | pending → active → archived | [plan-status.mmd](./plan-status.mmd) |
| 4 | intent_router 路由 | intent 4 路分支 | [intent-routing-flow.mmd](./intent-routing-flow.mmd) |

## mmd 文件格式

每份包含：
```mermaid
stateDiagram-v2
    [*] --> S1
    S1 --> S2: 触发条件
    S2 --> [*]
```

加上"合法转移矩阵"表（一行一转移）+ 非法转移响应表。

## 引用

- 表字段：参 [data-models/ 各表](../data-models/)
- API 行为：参 [api-spec/ 各端点](../api-spec/)
- Service 校验：`services/<feature>.py` 内 `assert_valid_transition()` 函数
