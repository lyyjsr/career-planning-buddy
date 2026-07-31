# risk_gate — 风险分流

## 定位

Graph 第一个节点。先做本地规则判断，疑似风险时可调用 `LLM_ROUTER_MODEL` 做结构化分类。它不是医疗诊断。

## Input

```python
RiskInput(run_id: UUID, message: str)
```

## Output

```python
RiskResult(
  level: Literal["none", "high"],
  category: Literal["self_harm", "mental_health", "legal", "financial", "other"] | None,
  method: Literal["rule", "classifier", "rule_and_classifier"],
  matched_rule_ids: list[str]
)
```

## 不变量

- level=high 直接进入 safe_response，不再生成求职计划；
- Trace 只记录 rule id，不记录命中的敏感原句；
- Provider 失败时采用保守策略：明确命中本地高风险规则则 high，否则继续普通链路并加安全提示；
- 不写 Memory、Plan 和 Task。

## Trace

level、category、method、matched_rule_ids、latency_ms。不得保存完整用户敏感内容。
