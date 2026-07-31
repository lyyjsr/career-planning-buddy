# Eval 系统

## Case 格式

```json
{"id":"case-001","profile":{},"message":"...","expected":{"intent":"create_plan","max_tasks":3,"must_fit_budget":true}}
```

## Grader

1. Intent Grader；
2. Schema Grader；
3. Time Budget Grader；
4. Startability Grader；
5. Deliverable Grader；
6. Source Integrity Grader；
7. Replan Continuity Grader；
8. Safety Routing Grader。

规则可判的指标优先使用程序 Grader。LLM Judge 只作为辅助，不作为唯一真值。

## 报告

输出 pass rate、各 Grader 通过率、平均 Token、成本、延迟、失败 Case 和 diff。CI 默认跑 smoke 子集；完整 30 Case 可手动或夜间运行。
