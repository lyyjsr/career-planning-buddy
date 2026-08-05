# Developer Run API

全部端点要求 role=dev。

## GET /api/v1/dev/runs

过滤：status、intent、result_kind、graph_version、model_id、created_from/to、cursor、limit。

摘要返回：run_id、脱敏 user id、status、result_kind、intent、graph version、model、token、cost、latency、fallback、created_at。

## GET /api/v1/dev/runs/{run_id}

返回：

- Run 元数据、result_kind 和终态 payload 摘要；
- graph/config/input snapshot 的脱敏视图与 hash；
- agent_steps；
- tool_calls 的脱敏参数、contract version、fixture 是否存在和结果摘要；
- agent_events 与 terminal event 检查；
- final PlanDetail（存在时）；
- 不返回 API Key、Authorization Header、未脱敏完整 Prompt 和完整网页正文。

## POST /api/v1/dev/runs/{run_id}/replay

PR-0 兼容语义：当前端点只创建 `legacy_trace_clone`，不会重新执行 Agent。响应包含：

```json
{
  "run_id": "...",
  "replay_of_run_id": "...",
  "status": "completed",
  "deterministic": true,
  "execution_kind": "legacy_trace_clone"
}
```

请求体中的 V2 字段和下列真实 Replay 行为是目标契约；在重执行引擎交付前不得据此声称
端点已经完成 Replay。

```json
{
  "target_model": null,
  "target_prompt_versions": null,
  "tool_mode": "fixture",
  "quality_reviewer_mode": "offline_shadow"
}
```

字段：

- `tool_mode=fixture`：默认；缺 fixture 返回 REPLAY_FIXTURE_MISSING；
- `tool_mode=live`：显式真实访问 Provider，结果标记 non_deterministic；
- target model/prompt 为空时使用原 config snapshot；
- Replay 使用原 input snapshot，不读取当前用户画像；
- 原 Run 必须处于终态；
- 新 Run 写 replay_of_run_id，不修改原 Plan 和原 Trace。
