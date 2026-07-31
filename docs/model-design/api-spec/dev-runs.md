# Developer Run API

全部端点要求 role=dev。

## GET /api/v1/dev/runs

过滤：status、intent、model_id、created_from/to、cursor、limit。

摘要返回：run_id、脱敏 user id、status、intent、model、token、cost、latency、fallback、created_at。

## GET /api/v1/dev/runs/{run_id}

返回：

- Run 元数据；
- agent_steps；
- tool_calls 的脱敏参数和结果摘要；
- agent_events；
- final PlanDetail；
- 不返回 API Key 和未脱敏完整 Prompt。

## POST /api/v1/dev/runs/{run_id}/replay

```json
{
  "target_model": null,
  "target_prompt_version": null,
  "use_tool_fixtures": true
}
```

原 Run 处于终态才允许 Replay。新 Run 写 `replay_of_run_id`。

Replay 不能保证真实联网搜索完全确定；默认使用 Tool fixture。
