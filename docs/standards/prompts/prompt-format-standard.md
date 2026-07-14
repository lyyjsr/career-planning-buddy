# Prompt 格式规范

状态：本轮实现。

English summary: Standardized prompt format — message array structure, System/Task/User message hierarchy, structured output binding, few-shot usage rules.

## 1. 消息数组结构

所有 Prompt 调用统一用 [OpenAI messages 格式](https://platform.openai.com/docs/guides/text-generation) 的 list[dict]，**不**用 free-text：

```python
messages = [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."},
    {"role": "user", "content": "..."},
]
```

## 2. 三层消息分层（强制）

| Role | 内容 | 谁定 |
|---|---|---|
| `system` | 节点身份 + 不可协商硬约束 + 工具结果防护（参 [security-and-compliance §4](../security-and-compliance.md)） | 版本化 prompt 文件 |
| `user` (第 1 条) | 任务描述（"根据上下文生成 plan..."） | 版本化 prompt 文件 |
| `user` (第 N 条) | 业务输入（用户原文 / memory / search_results） | 节点代码动态拼装 |

**禁令**：业务输入不得放进 system 消息（防 Prompt 注入）；工具结果（含外部 URL 内容）必须包 `<evidence>...</evidence>` 标签（[security-and-compliance §4](../security-and-compliance.md)）。

## 3. Structured Output 绑定（必填）

调用 LLM 时传 `response_model: type[BaseModel]`（Pydantic）。Provider 内部：

```python
schema_for_llm = response_model.model_json_schema()
# 把 schema 作为约束喂给 DeepSeek structured output
```

**禁令**：不用 dict schema，不用 str JSON 解析（R-Contract1）。所有 structured output 必须有对应 Pydantic 类。

## 4. Few-shot 写法

允许，但必须：
- ≤2 个示例
- 示例放在 system 之后、用户消息之前
- 示例不能含真实用户敏感数据（用脱敏数据）
- 示例必须标注 `示例，非真实用户`

## 5. Token 预算

| 节点 | budget 上限 | 来源 |
|---|---|---|
| intent_router | 4K | 小模型够用 |
| career_planning_agent | 8K | [TDD §7 上下文工程](../../architecture/tdd.md) |
| quality_reviewer | 3K | —— |
| distill_evidence | 6K | —— |
| companion_response | 2K | —— |

## 6. 引用

- 节点 prompt 实际内容（版本化的文件）：`backend/app/prompts/{goal_type}/*.py`
- 各节点 spec §6 依赖与副作用：[model-design/agent-nodes/](../../model-design/agent-nodes/)
