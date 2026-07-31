# quality_reviewer — 可选 LLM Judge

Stage 5 增强节点，不属于 MVP 纵切的必经路径。

## 作用

评价难以完全程序化的维度：连续性、理由充分性、语气压力、证据与结论一致性。

## Output

```python
QualityReview(
  passed: bool,
  score: float,
  issues: list[str],
  repair_instructions: list[str]
)
```

## 约束

- Judge 不修改 Candidate；
- Judge 失败不等于业务失败，记录 Trace 后以 rule_validator 为底线；
- Prompt 与主 Agent 分离版本；
- 禁止用同一次 Judge 输出作为唯一 Eval 真值。
