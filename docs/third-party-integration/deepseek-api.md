# DeepSeek API 对接说明

| 版本 | v1.0 |
|---|---|
| 日期 | 2026-07-24 |
| 状态 | 草稿（**对接事实来自官方公开文档**；待 Pre-Stage 0 Provider PoC 跑通后回填实测） |
| 来源 | DeepSeek 官方文档 https://api-docs.deepseek.com/ |
| 关联 | [../architecture/adr.md ADR-005](../architecture/adr.md) · [../standards/error-handling-standard.md](../standards/error-handling-standard.md) |

English summary: External vendor integration spec for DeepSeek LLM. Pins the official HTTP contract (OpenAI-compatible) and maps it to our `LLMProvider` Protocol. Truth about *their* interface; the truth about *ours* lives in `model-design/`.

---

## 1. 对接概览

| 维度 | 事实 |
|---|---|
| Base URL | `https://api.deepseek.com` (国内可直连，未发现 GFW 阻断) |
| 协议形态 | **OpenAI Chat Completions 兼容**（`/v1/chat/completions`）— 支持 openai-sdk 直接对接 |
| 认证 | Bearer Token；`Authorization: Bearer <DEEPSEEK_API_KEY>` |
| 限流 | 按账号 RPM/TPM；MVP 用量预计远低于阈值，**不接速率限制中间件** |
| 价格 | 输入/输出分别计价（详见 §4 cost 估算表）；按 token 计 |
| 国内合规 | DeepSeek 由国内公司提供服务，**数据不出境**，满足本项目合规要求 |

> ⚠️ 价格、限流、模型 ID 等具体字段**以官方文档为唯一真理源**。本文档仅记录与本项目对接相关的关键事实与映射规则。

---

## 2. 模型选型（与 ADR-005 对齐）

ADR-005 决策：核心规划 / 蒸馏用强模型；简单节点（intent_classifier / quality_reviewer / 内容安全）用小模型省钱。

### 2.1 模型清单（**待 spike 验证**）

本项目计划使用的模型 ID（具体名称以 DeepSeek 官方为准）：

| 用途 | 计划模型 | 用在哪个节点 | 状态 |
|---|---|---|---|
| 核心规划 / ReAct | `deepseek-chat`（最新版） | `career_planning_agent` / `distill_evidence` / `companion_response` | 待 spike 验证 |
| 简单分类 / Judge | `deepseek-chat`（降配：低 max_tokens、低 temperature） | `intent_router` / `quality_reviewer` | 待 spike 验证 |
| Embedding | DeepSeek 同厂 Embedding（或备选 `bge-m3`）| `tools/executors/rag_retrieve` | 待 spike 验证 |

**ADR-005 提到的"DeepSeek V4"是项目内代号**——实际发布版本号以 DeepSeek 官方为准，开 spike 验证时优先锁定最新稳定版。

DeepSeek V4 是项目选型候选称呼；代码配置、Trace 示例与 PoC 实测必须使用官方 model id（当前为 `deepseek-chat`），不得把项目代号当作真实 model id。

---

## 3. HTTP 接口契约

### 3.1 Chat Completions（核心接口）

所有 LLM 节点统一走该接口。

```
POST https://api.deepseek.com/v1/chat/completions
Authorization: Bearer <DEEPSEEK_API_KEY>
Content-Type: application/json
```

### 3.2 请求 schema（OpenAI 兼容）

```jsonc
{
  "model": "deepseek-chat",
  "messages": [
    { "role": "system", "content": "..." },
    { "role": "user", "content": "..." }
  ],
  "temperature": 0.0,           // 本项目规划类节点固定 0.0
  "max_tokens": 2000,           // 每个节点按 [TDD §7 上下文预算](../architecture/tdd.md) 配置
  "response_format": {          // 结构化输出关键
    "type": "json_object"       // DeepSeek 支持 JSON mode
  },
  "stream": false               // MVP 全部非流式；SSE 是 service 层做，不是 provider 层
}
```

**本项目固定参数约定**：

| 参数 | 规划类节点（agent）| 分类 / 校验节点 |
|---|---|---|
| `temperature` | 0.0 | 0.0 |
| `top_p` | 1.0 | 1.0 |
| `max_tokens` | 2000 | 500 |
| `response_format` | `{"type": "json_object"}` | `{"type": "json_object"}` |
| `stream` | `false` | `false` |

### 3.3 响应 schema（OpenAI 兼容）

```jsonc
{
  "id": "chatcmpl-...",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "deepseek-chat",
  "choices": [
    {
      "index": 0,
      "message": { "role": "assistant", "content": "{...json string...}" },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 1234,
    "completion_tokens": 567,
    "total_tokens": 1801
  }
}
```

**关键字段**（本项目的 trace 必须记录）：

- `usage.prompt_tokens` → `agent_steps.tokens_in`
- `usage.completion_tokens` → `agent_steps.tokens_out`
- `choices[0].finish_reason` → `stop / length / content_filter`（影响 trace 的 fallback_reason）
- `choices[0].message.content` → 解析为 Pydantic schema（失败即触发 `revise_or_fallback`）

---

## 4. 成本估算（**规划值，未实测**）

> ADR-005 要求 **单 run 总成本 ≤ ¥0.2**。下面表格是推算依据，跑完 spike 后用 `trace-tables` 写真实数据替换。

| 节点 | 模型 | 估算 input | 估算 output | 估算单价（CNY/1K token）| 估算单次成本 |
|---|---|---|---|---|---|
| `intent_router` | deepseek-chat | 1.5K | 0.1K | 输 ¥0.001 / 输 ¥0.002（待实测） | ¥0.0017 |
| `context_builder` | 无 LLM | - | - | - | - |
| `career_planning_agent`（含 ReAct 2 轮 + 4 工具）| deepseek-chat | 8K | 2K | 同上 | **¥0.012** |
| `rule_validator` | 无 LLM（程序判定） | - | - | - | - |
| `quality_reviewer` | deepseek-chat | 1.5K | 0.3K | 同上 | ¥0.0021 |
| `companion_response` | deepseek-chat | 1.5K | 0.5K | 同上 | ¥0.0025 |
| **不含 tool call 的 LLM 总成本** | | | | | **≈ ¥0.018** |
| web_search（Tavily，详见 `third-party-integration/tavily-api.md`，**待补，阶段 4**）| - | - | - | - | ≤ ¥0.10 |
| **单 run 估算总成本** | | | | | **≈ ¥0.12** ✅ 低于 ¥0.2 |

> ⚠️ 上述数字**未跑过 spike**。若实测超出 ¥0.2，则触发 [ADR-005 降级链](../architecture/adr.md)：减少 ReAct 轮次 / 关 web_search 走缓存 / 简单节点换更小模型。

---

## 5. 与本项目 `LLMProvider` Protocol 的对接

### 5.1 Protocol 定义（已在 [tdd.md](../architecture/tdd.md) §3.2.1 定稿）

```python
class LLMProvider(Protocol):
    model: str
    async def chat_complete(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.0,
        max_tokens: int = 2000,
        response_format: type[BaseModel] | None = None,
    ) -> LLMResponse: ...
```

### 5.2 DeepSeek 实现（`backend/app/providers/llm/deepseek.py`，Stage 3 真实模型注入时落地）

```python
# 伪代码——Stage 3 落地
class DeepSeekLLMProvider:
    def __init__(self, api_key: str, model: str = "deepseek-chat"):
        self._client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
        )
        self.model = model

    async def chat_complete(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.0,
        max_tokens: int = 2000,
        response_format: type[BaseModel] | None = None,
    ) -> LLMResponse:
        # 1. 序列化 messages
        # 2. 调 self._client.chat.completions.create(...)
        # 3. retry on 5xx/429（不超过 2 次）
        # 4. 解析 choices[0].message.content
        # 5. 若 response_format 指定，做 Pydantic 反序列化 + 校验
        # 6. 包装为 LLMResponse(tokens_in, tokens_out, cost_cny, finish_reason)
        ...
```

### 5.3 契约测试（`backend/app/providers/tests/test_llm_contract.py`）

`MockLLMProvider`（Stage 2 用）与 `DeepSeekLLMProvider`（Stage 3 用）必须通过同一套契约测试：

- 相同 messages 输入 → 相同 `LLMResponse` schema 形态
- 相同 response_format → 必须解析成功或抛 `SchemaValidationError`
- 超时 / 5xx 重试逻辑一致

---

## 6. 错误码映射（DeepSeek → 项目错误码）

DeepSeek 错误与 [error-handling-standard.md](../standards/error-handling-standard.md) 项目错误码的映射：

| DeepSeek 错误 | 项目 `error_class` | 处理 | trace.fallback_reason |
|---|---|---|---|
| `401 Unauthorized`（API Key 错） | `provider_auth_failed` | 当次 run fail，不重试 | `provider_auth_failed` |
| `429 Rate limit` | `provider_rate_limited` | 退避重试 ≤2 次；仍失败 degrade | `provider_rate_limited` |
| `400 invalid_request`（schema 不合规） | `provider_schema_invalid` | 不重试；触发 `revise_or_fallback` | `provider_schema_invalid` |
| `5xx server error` | `provider_5xx` | 退避重试 ≤2 次；仍失败 degrade | `provider_5xx` |
| 连接超时 | `provider_timeout` | 不重试；触发 degrade | `provider_timeout` |
| `finish_reason=length` | `truncated_output` | 业务判定是否可接受，不可接受即重写 | `truncated_output` |
| `finish_reason=content_filter` | `content_filtered` | 不重试；走 `safe_response` | `content_filtered` |
| Pydantic schema 不匹配 | `schema_mismatch` | 触发 `revise_or_fallback` 重写 | `schema_mismatch` |

---

## 7. 环境变量

`backend/.env.example`（Stage 0 落地）：

```bash
# LLM Provider
DEEPSEEK_API_KEY=sk-xxxxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL_PLANNER=deepseek-chat      # 核心规划节点
DEEPSEEK_MODEL_JUDGE=deepseek-chat        # 分类 / 校验节点
DEEPSEEK_MODEL_EMBEDDING=                 # 待 spike，可能用 bge

# 成本 / 限流保护
DEEPSEEK_BUDGET_MAX_COST_CNY_PER_RUN=0.20
DEEPSEEK_REQUEST_TIMEOUT_S=15
DEEPSEEK_RETRY_MAX=2
```

---

## 8. Pre-Stage 0 Provider PoC 的具体动作（与 [../architecture/poc-verification-report.md](../architecture/poc-verification-report.md) 对齐）

1. 写 50 行 Python 脚本（不经 FastAPI）：

   ```python
   # scripts/poc_deepseek.py（Pre-Stage 0 Provider PoC 落地）
   import openai, json
   client = openai.AsyncOpenAI(api_key="...", base_url="https://api.deepseek.com")
   for case in load_cases():  # 5-10 个金标 case
       resp = await client.chat.completions.create(
           model="deepseek-chat",
           messages=case.messages,
           response_format={"type": "json_object"},
       )
       result = IntentResult.parse_raw(resp.choices[0].message.content)
       validate(result, case.expected)
   ```

2. 跑完填 [poc-verification-report.md §3 实测数据表](../architecture/poc-verification-report.md)

3. 若通过率不达标，触发 [ADR-005 备选方案](../architecture/adr.md)（GLM-4.5 降级或换 Claude）

---

## 9. 不在本 spec 范围的

| 不含 | 为什么 |
|---|---|
| DeepSeek 后台账号 / 计费配置 | 由产品负责人私下管理，不进 spec |
| Prompt 文本 | 见 [../standards/prompts/prompt-versioning-standard.md](../standards/prompts/prompt-versioning-standard.md) |
| Tool 实现逻辑 | 见 [tdd.md §6 Tool 系统](../architecture/tdd.md) |
| Vector Embedding 选型实证 | 单独 spec，跟进 spike 后决策 |

---

## 10. 不变量

| ID | 描述 |
|---|---|
| INV-DS1 | 任何调用 DeepSeek 的代码**必须经 `LLMProvider` Protocol**，禁止直接构造 HTTP 请求 |
| INV-DS2 | 调用产生的 `tokens_in / tokens_out / cost_cny` **必须写到 `agent_steps` trace 表**（见 [../model-design/data-models/trace-tables.md](../model-design/data-models/trace-tables.md)） |
| INV-DS3 | API Key 不得出现在任何 spec / prompt / trace_data 字段；只走环境变量 |
| INV-DS4 | 同一 case 多次重跑（Replay 场景）必须显式传 `temperature=0` + 固定 seed（DeepSeek 支持时）|
| INV-DS5 | 出现 `content_filter` 一律走项目 `safe_response` 节点，不重试 |

---

## 11. 参考依据

| 来源 | 用于本文 § |
|---|---|
| [DeepSeek 官方 API 文档](https://api-docs.deepseek.com/) | §3 HTTP 契约 |
| [ADR-005 LLM 与 Provider](../architecture/adr.md) | §2 模型选型 + §5 Protocol + §6 降级链 |
| [TDD §3.2.1 Provider Protocol](../architecture/tdd.md) | §5 Protocol 定义 |
| [TDD §7 上下文预算](../architecture/tdd.md) | §4 成本估算 |
| [TDD §12.4 Budget](../architecture/tdd.md) | §4 单 run 成本约束 |
| [trace-tables.md](../model-design/data-models/trace-tables.md) | §3.3 tokens 字段写表 |
| [error-handling-standard.md](../standards/error-handling-standard.md) | §6 错误码映射 |
| [PoC 验证报告（同批次新增）](../architecture/poc-verification-report.md) | §8 spike 动作 |

---

*本文件是 DeepSeek 接口的"对方契约 + 本项目对接规则"。任何 API 字段变更以 DeepSeek 官方为唯一真理源；本 spec 只承担"对接规则"。*
