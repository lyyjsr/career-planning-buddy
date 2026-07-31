# clarification — 澄清信息

## 定位

程序节点，不调用 LLM。根据 missing_slots 选择固定问题和选项。

## Output

```python
ClarificationRequest(
  questions: list[str],
  slot_names: list[str],
  hint_options: dict[str, list[str]]
)
```

## MVP 行为

- 发 `clarification.requested`；
- 当前 Run 标记 degraded，fallback_reason=`profile_incomplete`；
- 前端补 Profile 后创建新 Run；
- 不增加 waiting_input/checkpoint 状态。

问题最多 3 个，不能询问与本次规划无关的敏感信息。
