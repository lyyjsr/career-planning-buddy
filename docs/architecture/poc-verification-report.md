# 运行时 Provider Smoke Checklist

本检查不阻塞 Stage 0 和 Stage 1。真实模型只在 Stage 3 接入前完成验证。

## 1. 目标

验证当前配置的 OpenAI-compatible 模型是否满足项目需要，而不是验证某个不存在的“项目代号模型”。

## 2. 必测项

| 编号 | 验证 | 通过标准 |
|---|---|---|
| H1 | 基础 Chat Completion | 返回非空文本 |
| H2 | JSON 结构化输出 | 20 次成功率 ≥ 95% |
| H3 | Tool Calling | 能稳定返回白名单 Tool 名和合法参数 |
| H4 | 流式输出 | chunk 顺序正常，可取消 |
| H5 | 超时和限流错误 | Provider 映射为统一异常 |
| H6 | Token Usage | 能读取或可靠估算输入/输出 Token |
| H7 | 中文计划质量 | 5 个固定 Case 通过规则校验 |

## 3. 配置

```env
LLM_BASE_URL=...
LLM_API_KEY=...
LLM_MODEL=...
LLM_ROUTER_MODEL=...
```

Codex 只用于开发，不需要也不得出现在上述运行时配置中。

## 4. 结论记录模板

```text
日期：
Provider：
Model ID：
SDK/协议：
H1-H7：
已知限制：
是否允许进入 Stage 3：Go / Conditional Go / No-Go
```

失败时先调整 Prompt、Schema 和参数；仍不满足时只更换配置或 Provider 实现，不修改业务层接口。
