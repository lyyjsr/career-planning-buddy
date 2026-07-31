# Developer Eval API

Stage 5 实现。固定数据集文件位于 `backend/evals/datasets/*.jsonl`。

## GET /api/v1/dev/evals/datasets

返回可用 JSONL 数据集和 case 数量。

## POST /api/v1/dev/evals/experiments

```json
{
  "dataset": "career_plan_v1",
  "model_override": null,
  "prompt_version": null,
  "parallelism": 4
}
```

Response 202：experiment_id、status、poll_url。

## GET /api/v1/dev/evals/experiments/{id}

返回：总 case、完成数、通过率、平均延迟、平均成本、各 grader 分数和失败 case。

第一版可将实验结果保存为 JSON Artifact；需要多人共享历史后再增加 Eval 表迁移。
