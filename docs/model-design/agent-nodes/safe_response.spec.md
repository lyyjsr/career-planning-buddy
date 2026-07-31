# safe_response — 固定安全响应

## 定位

风险分支的终止节点，不调用 LLM。输出内容来自 `SafetyResourceConfig`，按部署地区维护并定期复核，不在多份 spec 中散落硬编码热线或 URL。

## Input

```python
SafeResponseInput(run_id: UUID, category: RiskCategory)
```

## Output

```python
SafeResponse(
  message: str,
  resources: list[SafetyResource],
  disclaimer: str
)
```

## 行为

1. 写 `run.degraded` 事件；
2. Run 状态变为 degraded，fallback_reason=`high_risk_routed`；
3. 不创建计划、任务、记忆候选；
4. 当前 Run 结束；用户下一次输入创建新 Run。

## 安全要求

- 不提供诊断；
- 不让 LLM自由生成紧急资源；
- 资源配置需要人工审核；
- 如果部署地区未知，使用通用的“联系当地紧急服务或可信任的人”提示，不猜号码。
