# dev-evals.md — 开发者评测端点

状态：本轮实现。

> 评测体系前置 spec。固定数据集 + 自动 grader（PRD §6 P1：`Eval 固定数据集 + 自动 grader`）。功能完整定义见 [harness/eval-system.md](../harness/eval-system.md)。

## 端点：GET /api/v1/dev/evals/datasets

列出评测数据集。

**成功响应 200** `DatasetListResponse`：`{items: [DatasetSummary], next_cursor?}`。

`DatasetSummary`: `dataset_id / name / case_count / created_at / tags[]`。

## 端点：POST /api/v1/dev/evals/datasets

创建数据集。**必填 Idempotency-Key**。

**请求 Schema** `CreateDatasetRequest`：

| 字段 | 类型 | 必填 |
|---|---|---|
| `name` | str | ✅ max 100 |
| `description` | str? | ❌ |
| `tags` | list[str]? | ❌ |
| `cases` | list[EvalCaseInput] | ✅ min 1 |

`EvalCaseInput`: `name / user_message / expected_intent / expected_goal_type / rubric（dict）`。

**成功响应 201** `DatasetSummary` + `dataset_id`。

## 端点：GET /api/v1/dev/evals/datasets/{dataset_id}

读数据集详情（含全部 case）。

## 端点：POST /api/v1/dev/evals/experiments

启动评测实验。**必填 Idempotency-Key**。

**请求 Schema** `StartExperimentRequest`：

| 字段 | 类型 | 必填 |
|---|---|---|
| `dataset_id` | uuid | ✅ |
| `prompt_version` | str? | ❌（缺省用产线） |
| `model_override` | str? | ❌ |
| `parallelism` | int | ❌ 默认 4（`Field(ge=1, le=16)`） |

**成功响应 202** `ExperimentAcceptedResponse`：

| 字段 | 类型 |
|---|---|
| `experiment_id` | str |
| `status` | Literal["pending"] |
| `poll_url` | str（轮询地址） |

## 端点：GET /api/v1/dev/evals/experiments/{experiment_id}

查询实验结果。

**成功响应 200** `ExperimentResult`：

| 字段 | 类型 |
|---|---|
| `experiment_id` | str |
| `status` | `pending / running / completed / failed` |
| `total_cases` | int |
| `completed_cases` | int |
| `pass_rate` | float? |
| `case_results` | list[EvalCaseResult]? |
| `aggregate_metrics` | dict? |

`EvalCaseResult`: `case_id / run_id / passed (bool) / rubric_breakdown (dict) / latency_ms / cost_cny`。

## 关联

- 表：[trace-tables.md](../data-models/trace-tables.md)（eval_datasets / eval_cases / eval_experiments / eval_case_results，需补 schema——见阶段五 TODO）
- Harness 设计：[harness/eval-system.md](../harness/eval-system.md)
- PRD §6 P1
