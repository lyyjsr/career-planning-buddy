# Replay V2 目标契约

> 当前 `POST /api/v1/dev/runs/{run_id}/replay` 仅是兼容入口，实际执行种类为
> `legacy_trace_clone`：复制已持久化的 Run/Step/Tool/结果，不执行 Graph、Provider 或结果
> diff，因此不得称为真实 Replay。响应会显式返回 `execution_kind=legacy_trace_clone`。

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

## V2 完成条件

只有同时满足以下条件，才可把执行种类标记为 Replay：从不可变 input/config snapshot
重建上下文；按 fixture contract 执行 Tool；重新运行 Graph/Provider；生成独立结果；对新旧
输出、规则、成本和 Trace 做 diff。复制旧结果不属于 Replay。

## Eval Harness V2 编排入口

Eval 控制面通过 `run_type=fixture_replay` 和必填的
`fixture_source_experiment_id` 创建回放实验。创建阶段按
`case_id + trial_index + variant` 将每个新 Trial 绑定到一个已完成、同数据集、
非回放且拥有唯一 Fixture Bundle 的源 Trial，并把绑定持久化到
`eval_trials.fixture_source_trial_id`。ExperimentRunner 只读取该冻结绑定，不在执行时猜测来源。

CLI 等价参数为：

```text
python -m evals.v2 run --provider-mode fixture --run-type fixture_replay \
  --fixture-source-experiment-id <uuid>
```
