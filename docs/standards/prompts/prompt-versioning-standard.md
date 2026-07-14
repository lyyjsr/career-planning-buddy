# Prompt 版本化规范

状态：本轮实现。

English summary: File naming, semantic version rules, and Replay dependency. R-Prompt1/2 fallback.

## 1. 文件命名（强制 R-Prompt1）

格式：`backend/app/prompts/{goal_type_or_node}/<purpose>_v<n>.py`

| 例子 | 含义 |
|---|---|
| `prompts/intent_router/system_v1.py` | intent_router 节点的 system prompt v1 |
| `prompts/intent_router/system_v2.py` | 改版后 |
| `prompts/career_planning_agent/task_v1.py` | CareerPlanningAgent 的 task prompt |
| `prompts/companion/empathetic_v1.py` | companion 的共情话术基础版 |

## 2. 版本号语义

| 版本号 | 严格意义（scribe-style） |
|---|---|
| `_v1.py` | 灰度版（Eval 测试中，未默认启用） |
| `_v2.py` | 正式 rollout 版（替换 v1 为生产默认） |
| `_v3.py`+ | 进一步迭代 |

## 3. 修改规则（强制 R-Prompt2）

**永远新增版本文件，不改已发布文件**。

| 是否允许 | 场景 |
|---|---|
| ✅ 修改 `_v1.py` | v1 从未上线过（feature flag off） |
| ❌ 修改 `_v1.py` | v1 已上线（Trace 已记录 `prompt_version=v1`） |
| ✅ 新建 `_v2.py` | 任何上线后的改动 |

## 4. 版本亲和性

Trace 表 `agent_steps.prompt_version` 记录实际调用版本。Replay 重跑需：

| 输入 | Replay 用哪个版本 |
|---|---|
| 同 run_id + 同 trace | 用 trace 记录的版本（默认 v1 → pytest 用 v1） |
| 新 run_id 做对比 | 切到 v2 跑 |

## 5. Eval 中的版本对比

阶段 2 起 CI 跑 Eval。Prompt PR 评审需带：

| 报告项 | 要求 |
|---|---|
| v_old vs v_new 通过率 diff | 不能下降 ≥5 分点 |
| 失败 case 对比 | 失败 case 清单 |
| Token 用量变化 | 增加 < 30% |

## 6. 默认版本热切换

`core/config.py` 维护 `default_prompt_version` 映射：

```python
DEFAULT_PROMPT_VERSIONS = {
    "intent_router": "v1",
    "career_planning_agent": "v1",
    ...
}
```

切换默认版本 = 改 config + 跑 Eval 对比 + 进灰度。

## 7. 引用

- AGENTS.md R-Prompt1/2
- 节点 spec §6 Prompt 模板版本字段：[model-design/agent-nodes/](../../model-design/agent-nodes/)
- Trace 表 prompt_version 字段：[data-models/trace-tables.md](../../model-design/data-models/trace-tables.md)
