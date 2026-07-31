# Replay 设计

Replay 创建一个新 Run，并记录 `replay_of_run_id`。

可变项：model、prompt_version。默认使用原始业务输入和 Tool fixture。

Tool fixture key：`tool_name + args_hash`。缺 fixture 时：

- strict 模式失败；
- live 模式真实调用并标记 non_deterministic。

对比：最终计划 diff、规则通过率、Token、成本、延迟、fallback。Replay 不修改原 Run 和原计划。
