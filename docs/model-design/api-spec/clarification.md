# clarification.md — 澄清端点（不另起 REST 端点）

状态：本轮实现。

> **决策 9**：澄清流程**不另起 REST 端点**。用户首条消息进入 POST /agent-runs 后，由 risk_gate → intent_router 判定若缺槽 → 路由到 clarification 节点 → 通过 SSE 事件 `clarification.requested` 把要问的问题回推给前端；前端展示问卷后通过 PUT /profile（缺的字段）或下一条 POST /agent-runs 的 `message` 文本回答。本文件用于固化这条链路的字段契约。

## 触发位置

| 阶段 | 行为 | 出处 |
|---|---|---|
| 首次建档 | POST /agent-runs 后 SSE 收到 `clarification.requested` | [intent_router.spec.md §5](../agent-nodes/intent_router.spec.md) 路由 + [clarification.spec.md §2](../agent-nodes/clarification.spec.md) 节点输出 |
| 已有 profile 但更新方向 | 同上 | 同上 |
| Agent 中途 | MVP 不做（≤3 轮兜底：见 clarification.spec.md §4 `clarification_overflow`） | — |

## SSE 事件：clarification.requested

```json
{
  "event": "clarification.requested",
  "data": {
    "run_id": "r-2a8f-...",
    "questions": ["你希望秋招的目标方向是？"],
    "slot_names": ["goal"],
    "hint_options": { "goal": ["AI 后端", "Agent 应用", "数据分析"] },
    "fallback_reason": null
  },
  "id": "evt-c4d1"
}
```

| 字段 | 类型 | 必填 | 约束 |
|---|---|---|---|
| `run_id` | str | ✅ | 当前 run |
| `questions` | list[str] | ✅ | `min_length=1, max_length=3`，每条 `max_length=200` |
| `slot_names` | list[str] | ✅ | 与 questions 一一对应；值限定于 `["goal","stage","time_budget","skill_level"]` |
| `hint_options` | dict[str, list[str]] | ❌ | 每槽位 2-4 个候选提示（max_length=4） |
| `fallback_reason` | str? | ❌ | `clarification_overflow` 时填，前端需切换为 query_plan 兜底 |

> 同时 run 自身状态从 `running` 转 `degraded`（fallback_reason=clarification_overflow 时）或保持 `running`（等待下一次 POST /agent-runs），见 [run-status.mmd](../state-machines/run-status.mmd)。

## 前端响应路径

前端收到此事件后，按 `slot_names` 渲染对应表单。用户提交时分两种路径：

### 路径 A：补全 profile（推荐用于"首次建档"场景）

直接走 [PUT /profile](./profile.md)（任一缺失字段就 upsert），成功后再 POST /agent-runs 发起新 run（无需 hint_intent，LLM 会自动判定为 create_plan）。

```http
PUT /api/v1/profile
Idempotency-Key: idem-9af2-bc11
{"goal_type":"agent_app","stage":"mid","time_budget_minutes":180,"skill_level":"intermediate"}
```

### 路径 B：直接回答问题（推荐用于"已有 profile、本轮消息模糊"场景）

POST /agent-runs，把答案作为 `message` 发出，参考 `hint_intent` 给服务端提示：

```http
POST /api/v1/agent-runs
Idempotency-Key: idem-b41f-c2d1
{"message":"我秋招方向是后端 Java，每周可投入 10 小时","hint_intent":"create_plan"}
```

## 关联

- 节点：[clarification.spec.md](../agent-nodes/clarification.spec.md)（程序节点，不调 LLM）
- 上游：[intent_router.spec.md §5](../agent-nodes/intent_router.spec.md)
- 错误码：`VALIDATION_PROFILE_INCOMPLETE`（[profile.md PUT](./profile.md)）+ `clarification_overflow`（节点 fallback_reason）
