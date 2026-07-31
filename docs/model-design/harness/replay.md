# Replay

## 默认输入

Replay 新建独立 Run，并使用原 Run 保存的：

- `input_snapshot_json`；
- `config_snapshot_json`；
- `graph_version`；
- `tool_calls.result_json` fixture。

可变项：model、prompt_version、quality reviewer 模式。默认不读取用户当前 Profile/Plan/Memory，避免历史输入漂移。

## Tool Fixture

Fixture key：

```text
tool_name + args_hash + tool_contract_version
```

缺 fixture 时：

- deterministic 模式：失败并返回 `REPLAY_FIXTURE_MISSING`；
- live 模式：仅开发者显式选择时访问 Provider，并标记 `non_deterministic=true`；
- 不允许静默回退到真实网络。

## 输出对比

至少对比：

- resolved_intent；
- result_kind/status/fallback_reason；
- PlanCandidate Schema；
- 各规则 Grader；
- source integrity；
- token、cost、latency；
- 节点和 Tool 调用差异。

Replay 不修改原 Run、原 Plan、原 Trace。默认只保存实验结果，不替换用户当前计划。
