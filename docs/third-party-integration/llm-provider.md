# OpenAI-compatible LLM Provider

## 目标

用一个稳定协议隔离业务代码与具体模型厂商。服务层和 Agent 节点只依赖 `LLMProvider`，不引用厂商 SDK 类型。

## 最小接口

```python
class LLMProvider(Protocol):
    async def generate_structured(
        self,
        *,
        messages: list[dict[str, str]],
        response_model: type[BaseModel],
        timeout_seconds: float,
    ) -> LLMResult: ...
```

`LLMResult` 至少包含：解析后的数据、provider、model、usage、latency_ms、request_id。

## 环境变量

```env
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=
LLM_API_KEY=
LLM_MODEL=
LLM_ROUTER_MODEL=
```

## 可靠性规则

- 单次请求有超时；
- 仅对可重试的网络错误执行有限重试；
- Schema 失败最多修复一次；
- 记录实际模型 ID 和用量；
- 不在异常中暴露原始密钥或完整敏感输入；
- Provider 不可用时允许返回显式 degraded 结果或使用模板，不伪造成功。

## Mock Provider

Stage 2 必须先用确定性 Mock 输出跑通完整 Run、SSE、Plan 和 Task。真实模型不得成为工程骨架和契约测试的前置条件。
