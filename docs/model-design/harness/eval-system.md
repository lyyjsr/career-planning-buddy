# Eval 系统设计

| 版本 | v1.1 |
|---|---|
| 日期 | 2026-07-24 |
| 状态 | 草稿 |
| 目的 | 把 [TDD §12.5 Eval](../../architecture/tdd.md) 四行概念展开为可实现的 spec：数据集 / grader 接口 / 报告 / Bad Case 回流 / CI 门禁 |
| v1.0 → v1.1 | 明确本系统落地于 `backend/app/evals/`（与 `harness/` 并列，**不嵌套**）。spec 本身仍归 `model-design/harness/` 是因为它是"反馈层"概念体系的一部分；代码位置与 spec 目录是两件事。详见 [implementation-structure.md](./implementation-structure.md) |

---

## 1. 定位

### 1.1 Eval 在反馈层的位置

> **Eval = 把"上线后看效果"前置成"上线前看效果"的离线工程能力。**

**代码落地**：`backend/app/evals/`（与 `harness/` 并列，不嵌套）——理由：
- 运行时反馈（Trace/Budget/Checkpoint/Replay）属 L5 Runtime，每次 plan_run 在线同步跑
- 离线反馈（Eval/Bad Case）属 L6 外部工具链，CI 离线批量跑
- 两套子系统生命周期、失败容忍度、延迟要求、入口都不同，物理分离更工程化（详见 [harness-overview.md §5](./harness-overview.md)）

| 特性 | evals/（离线） | harness/（运行时） |
|---|---|---|
| 运行时机 | CI / dev 手动 | 每次 plan_run 在线 |
| 延迟容忍 | 分钟级 | ≤20s 硬约束 |
| 失败处理 | case fail | degraded + fallback_reason |
| 是否写 trace 表 | 写但用 session_id 隔离 | 写 |
| 是否调真实模型 | 可选（mock 优先） | 必调 |

- 数据：固定数据集（30 case）+ Bad Case 回流（生产失败 case）
- 执行：跑 plan_run（mock tool 优先）→ grader 自动评分
- 输出：报告（每维度 pass rate + 失败 case 清单）
- 触发：CI 自动 + 开发者手动
- 决策：是否允许 Prompt PR 合入

### 1.2 与 Replay / 单测 的边界

| 维度 | Eval | Replay | 单测 |
|---|---|---|---|
| 目的 | 守护"质量不退化" | 守护"行为无偏移" | 守护"代码无 bug" |
| 输入 | 固定 case 集 | 历史真实 run_id | 代码函数 |
| 重现性 | 高（mock tool 固定） | 中（需 fixture） | 极高 |
| 速度 | 慢（一次 N case × 全节点） | 中 | 快 |
| 在 CI 的位置 | check-eval.sh | 不进 CI（dev-only） | check-architecture + check-contracts 之外 |

### 1.3 范围声明

**Eval 系统是 Stage 5 退出条件的核心**（[stage-delivery-definition.md §阶段5](../../governance/stage-delivery-definition.md)）。本 spec 覆盖：

- 数据集 schema（`eval_datasets` / `eval_cases` 两张表）
- Grader 接口与实现
- 报告 schema（`eval_runs` 表）
- Bad Case 回流 API + 数据流
- CI 门禁规则（check-eval.sh 增强）

---

## 2. 数据集设计

### 2.1 数据集版本

每个 dataset 是一份**版本化、不可变**的 case 集合。

| 字段 | 含义 |
|---|---|
| dataset_id | uuid PK |
| version | 形如 `v1.0`、`v1.1`（minor 加 case / patch 修订 case 不允许，必须 minor 升） |
| goal_type | `Literal["ai_backend","agent_app","backend_java","data_engineer","fullstack","all"]` |
| case_count | 案例 数量 |
| archived | boolean（已归档不可评测） |
| created_at | —— |

**不变量**：

| ID | 不变量 |
|---|---|
| INV-D1 | dataset 一旦发布（status=published）→ cases 不可修改（只增新的 minor 版本） |
| INV-D2 | 同 goal_type 同时只能有 1 个 `archived=false` 的 default dataset |

### 2.2 Case schema

每个 case 是一个独立的、端到端的 plan_run 测试场景。

```python
class EvalCase(BaseModel):
    case_id: uuid
    dataset_id: uuid FK
    case_name: str                 # "high_priority_user_with_3h_budget"
    category: Literal[
        "normal",                  # 正常 plan 10 case
        "replan",                  # 复盘触发重规划 5 case
        "fallback_other",          # goal_type=other 通用兜底 3 case
        "high_risk",               # 安全分流 3 case
        "budget_limited",          # 时段紧张（<30min）3 case
        "edge",                    # 边界（空画像/缺槽位/异常输入/超长 message）3 case
        "bad_case"                 # 生产失败 case 回流 3+ case（动态增长）
    ]
    input: EvalCaseInput           # 输入快照（§2.3）
    expected: EvalCaseExpected     # 期望输出（§2.4）
    rubric_overrides: dict[str, str] | None  # 个别 case 的额外评分细则（覆盖 grader 默认）
    source: Literal["manual","bad_case"]
    created_at: timestamptz
```

### 2.3 `EvalCaseInput` 输入 schema

```python
class EvalCaseInput(BaseModel):
    message: str                            # 用户消息（len ≤ 2000）
    user_profile: UserProfile               # 用户画像（包含 goal_type/stage/available_minutes）
    history_summary: str | None             # 历史 N 天完成/放弃情况（replan case 必填）
    memories_snapshot: list[MemoryAtom]     # 用户已有记忆（mock 列表）
    experience_atoms_mock: list[ExperienceAtom]  # 经验原子 mock（不依赖生产 DB）
    tool_fixtures: dict[ToolName, list[ToolFixture]]  # tool 返回的固定 fixture（mock 模式必需）
```

**关键设计**：case 输入**完全自包含**（self-contained）——不读取生产 DB / memories / experience_atoms，所有依赖都在 `input` 里固化。理由：

1. **可重现**：同样的 input → 同样的 LLM 调用 → 可对比
2. **隔离**：评测不依赖业务数据状态
3. **可移动**：case 集可单独 export/import 到任何环境

### 2.4 `EvalCaseExpected` 期望 schema

```python
class EvalCaseExpected(BaseModel):
    # 任一匹配即通过：
    expected_intent: Literal["plan","replan","fallback_safe","fallback_other"] | None
    expected_status: Literal["completed","degraded"]   # degraded 可（如 high_risk case）
    
    # 结构化期望：
    expected_task_count_range: tuple[int, int] | None  # (1, 4) 任务数应在 1-4
    expected_max_task_minutes: int | None              # 单 task ≤ 60
    must_include_keywords: list[str] | None            # task 字段必须含的关键词
    must_not_include_keywords: list[str] | None        # 不能出现的"AI slop"词
    
    # 高风险分流 case：
    must_route_to_safe_response: bool = False          # True 时期望走 safe_response 节点
    
    # Bad case 来源时回填：
    known_failure_dimension: Literal[
        "dim_1_startable","dim_2_time_match","dim_3_cognitive_load",
        "dim_4_continuity","dim_5_deliverable",
        "intent_misclassification","safety_bypass"
    ] | None
```

### 2.5 初始 30 case 分布（必填）

| category | 数量 | 主要场景 |
|---|---|---|
| `normal` | 10 | 不同 user_profile × 不同 message 的正常 plan |
| `replan` | 5 | history_summary 含连续放弃 / 完成 / 阻碍 → 触发双层调整 |
| `fallback_other` | 3 | goal_type=other → 期望走通用兜底 + 坦诚告知 |
| `high_risk` | 3 | message 含心理危机词 → 期望路由 safe_response |
| `budget_limited` | 3 | available_minutes < 30 → 任务数严格受限 |
| `edge` | 3 | 空画像 + 缺槽位 / 超长 message / 异常字符 |
| `bad_case` | 3+ | 生产失败 case 回流（动态增长） |

---

## 3. Grader 设计

### 3.1 Grader 接口

每个 grader 是一个独立函数（不依赖 LLM 调用的额外成本——除 LLM Judge grader 外）：

```python
class GraderResult(BaseModel):
    grader_name: str                       # "rule_validator_replay"
    passed: bool
    score: float                           # 0.0 - 1.0
    rationale: str                         # 详细原因 max 500
    dimension_scores: dict[str, float] | None  # 五维细项（适用时）

class Grader(Protocol):
    name: str
    def grade(self, actual: PlanRunOutput, expected: EvalCaseExpected, case: EvalCase) -> GraderResult:
        ...
```

### 3.2 六个核心 grader

| grader_name | 类型 | 实现 | 用于哪个维度 |
|---|---|---|---|
| `status_grader` | 程序 | 比对 run.status vs expected_status | 整体合规 |
| `intent_grader` | 程序 | 比对 intent_result.intent vs expected_intent | 意图识别 |
| `task_structure_grader` | 程序 | 校验 task_count / max_minutes / keywords | 结构合规 |
| `dimensions_grader` | 程序 | 重跑 5 维质量评分（[rule_validator.spec.md §3](../agent-nodes/rule_validator.spec.md) 维度 1/2/3/5 + quality_reviewer 维度 4 简化版） | 质量评分一致性 |
| `safety_grader` | 程序 | 校验是否路由到 safe_response + 是否含 12356 | 安全合规（high_risk case 关键） |
| `output_grader` | LLM Judge | 小模型对比 candidate 与 expected.must_include_keywords 的语义契合度 | 兜底语义检查（仅失败 case 触发，省 token） |

**Grader 顺序**（短路）：

```python
def run_all_graders(actual, expected, case) -> list[GraderResult]:
    results = []
    for G in [status_grader, intent_grader, task_structure_grader, dimensions_grader, safety_grader]:
        r = G.grade(actual, expected, case)
        results.append(r)
        if G.short_circuit_on_fail and not r.passed:
            return results  # 短路：早期 grader 失败 → 不跑后面（省成本）
    if any(not r.passed for r in results):
        results.append(output_grader.grade(actual, expected, case))
    return results
```

### 3.3 case 评分聚合

```python
class CaseVerdict(BaseModel):
    case_id: uuid
    passed: bool
    aggregate_score: float = sum / len(results)
    failed_graders: list[str]
    details: list[GraderResult]
```

case `passed = True` 当且仅当**所有非 LLM grader 通过**（LLM grader 仅告警不阻断）——理由：LLM Judge 有非确定性，不作为硬门禁。

---

## 4. Eval Run 与报告

### 4.1 `eval_runs` 表（[TDD §11.3](../../architecture/tdd.md) 已列，本文展开字段）

| 字段 | 类型 | NULL | 约束 | 说明 |
|---|---|---|---|---|
| `id` | `uuid` | NO | PK | —— |
| `dataset_id` | `uuid` | NO | FK→eval_datasets.id | —— |
| `dataset_version` | `varchar(16)` | NO | —— | 形如 `v1.2`（dataset 后续归档时仍可读） |
| `trigger` | `varchar(32)` | NO | CHECK ∈ `{ci_manual, ci_pull_request, ci_main, dev_manual, bad_case_add}` | 触发方式 |
| `git_sha` | `varchar(40)` | YES | —— | 触发时的 HEAD（CI 用）|
| `prompt_versions` | `jsonb` | NO | —— | 形如 `{"career_planning_agent":"v1","quality_reviewer":"v1"}` |
| `model` | `varchar(64)` | NO | —— | —— |
| `status` | `varchar(16)` | NO | CHECK ∈ `{running,completed,failed}` | —— |
| `case_count_total` | `integer` | NO | —— | —— |
| `case_count_passed` | `integer` | NO | —— | —— |
| `pass_rate` | `float` | NO | `ge=0, le=1` | passed/total |
| `dimensions_summary` | `jsonb` | NO | —— | `{"dim_1_pass_rate":0.97,"dim_2_pass_rate":0.93,...}` |
| `failed_cases` | `jsonb` | NO | —— | 失败 case_id + brief 上下文（详情查 eval_cases_verdicts） |
| `cost_cny_total` | `float` | NO | —— | —— |
| `latency_ms_total` | `integer` | NO | —— | —— |
| `baseline_run_id` | `uuid` | YES | FK→eval_runs.id | 用来 diff（[§7.2](#72-基线对比规则)） |
| `diff_vs_baseline` | `jsonb` | YES | —— | pass_rate diff / 维度 diff / 新失败 case / 新通过 case |
| `created_at` | `timestamptz` | NO | DEFAULT now() | —— |
| `completed_at` | `timestamptz` | YES | —— | —— |

**索引**：
- `idx_evalruns_dataset(dataset_id, created_at DESC)` — 看某数据集最近 runs
- `idx_evalruns_trigger(trigger, created_at DESC)` — CI 历史溯源

### 4.2 `eval_cases_verdicts` 子表（每个 case 一行）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | `uuid` | PK | —— |
| `eval_run_id` | `uuid` | FK→eval_runs.id ON DELETE CASCADE | —— |
| `case_id` | `uuid` | FK→eval_cases.id | —— |
| `run_id` | `uuid` | FK→agent_runs.id | 该 case 跑出的 plan_run（写入正常 trace 表）|
| `passed` | `boolean` | NO | —— |
| `aggregate_score` | `float` | NO | —— |
| `grader_results_json` | `jsonb` | NO | list[GraderResult] 序列化 |
| `latency_ms` | `integer` | NO | —— |
| `cost_cny` | `float` | NO | —— |

### 4.3 报告示例

```jsonc
{
  "eval_run_id": "er-...",
  "dataset_version": "v1.0",
  "trigger": "ci_pull_request",
  "git_sha": "abc1234",
  "prompt_versions": {"career_planning_agent":"v2","quality_reviewer":"v1"},
  "status": "completed",
  "pass_rate": 0.833,
  "case_count": {"total":30,"passed":25,"failed":5},
  "dimensions_summary": {
    "dim_1_startable": 0.97,    // 29/30 pass
    "dim_2_time_match": 0.93,
    "dim_3_cognitive_load": 0.90,
    "dim_4_continuity": 0.83,   // 维度 4 在 v2 prompt 下下降
    "dim_5_deliverable": 0.93
  },
  "failed_cases": [
    {"case_id":"c-bad-1","category":"replan","failed_graders":["dimensions_grader"],"known":true},
    {"case_id":"c-edge-2","category":"edge","failed_graders":["status_grader"],"known":false}
  ],
  "diff_vs_baseline": {
    "pass_rate_delta": -0.067,
    "regressed_dims": ["dim_4_continuity"],
    "new_failed": ["c-7","c-12"],
    "new_passed": []
  }
}
```

---

## 5. Bad Case 回流

### 5.1 流程

```mermaid
flowchart TD
    PROD([生产 plan_run<br/>status=degraded|failed]) --> REVIEW[开发者查看 Trace 页]
    REVIEW --> CLICK([点"加入 Bad Case 评测集"]) 
    CLICK --> API["POST /api/v1/dev/eval/bad-cases"]
    API --> XFORM[EvalCase transform<br/>从 run agent_steps / tool_calls 重建 input]
    XFORM --> EXPECTED[人工填 expected + known_failure_dimension]
    EXPECTED --> ADD[加入 default dataset next minor<br/>version bump]
    ADD --> CI([下次 CI 拉新版本 dataset 跑])
```

### 5.2 API

`POST /api/v1/dev/eval/bad-cases`（dev-only）

**Request**：
```json
{
  "source_run_id": "r-...",
  "known_failure_dimension": "dim_4_continuity",
  "expected_overrides": {
    "expected_intent": "plan",
    "expected_task_count_range": [1, 3]
  },
  "case_name": "replan_with_contradictory_history",
  "note": "v1 prompt 忽略昨日阻碍"
}
```

**Response 201**：
```json
{
  "case_id": "c-bad-...",
  "dataset_version": "v1.3",
  "warning": null
}
```

### 5.3 transform 实现（source run → EvalCaseInput）

```python
def transform_run_to_case(run_id: str) -> EvalCaseInput:
    run = repo.get_run(run_id)
    steps = repo.list_steps(run_id)
    
    # 从 step 0 提取原始 message
    message = steps[0].trace_data["original_message"]
    
    # 从 step 1 提取 user_profile（intent_router 的输入快照）
    profile = steps[1].trace_data["user_profile_snapshot"]
    
    # 历史 + 记忆从 context_builder step 提取（已有 snapshot）
    history = steps[2].trace_data["history_summary"]
    memories = steps[2].trace_data["memories_snapshot"]
    
    # tool fixtures：从 tool_calls 表的 args_hash → result_hash → 反查 fixture 库
    tool_fixtures = {}
    for tc in repo.list_tool_calls(run_id):
        fixture = lookup_fixture(tc.tool_name, tc.args_hash)
        if fixture: tool_fixtures[tc.tool_name].append(fixture)
    
    return EvalCaseInput(...)
```

### 5.4 自动 categorize + version bump

- 加入时自动 `category="bad_case"` + `source="bad_case"` + `known_failure_dimension`
- dataset next minor version bump（`v1.0` → `v1.1`）
- 若有 default dataset 已 archived → 创建新 default（不允许写入 archived dataset）

### 5.5 不变量

| ID | 不变量 |
|---|---|
| INV-B1 | Bad case 从 source_run_id transform 时，**只读** agent_steps / tool_calls（不修改原 run） |
| INV-B2 | transform 后的 case 必须**自包含**（不依赖 source_run_id 仍可独立运行） |
| INV-B3 | 加入 dataset 后，case 永久保留（不删）—— dataset 版本化保证可重现历史评测 |

---

## 6. CI 门禁接入

### 6.1 在 [check-scripts-spec.md](../../governance/check-scripts-spec.md) §5 基础上的增强

`scripts/check-eval.sh` 当前规则摘要：

```bash
pytest tests/eval/ -v --eval-dataset=defaults
# 评测通过率 <85% 时阻断
```

**本 spec 增强规则**：

```bash
#!/bin/bash
set -e
cd backend

# 1. 拉取 default dataset 当前版本
DATASET_VERSION=$(python -m app.evals.cli get-default-version)

# 2. 跑全套 eval
python -m app.evals.runner \
  --dataset=default \
  --trigger=ci_${CI_EVENT:-manual} \
  --git-sha=${GITHUB_SHA:-unknown} \
  --baseline=${EVAL_BASELINE_RUN_ID:-""} \
  --output=/tmp/eval_report.json

# 3. 判定门禁
python -m app.evals.judge /tmp/eval_report.json
#   fail conditions (任一即非 0 退出):
#     - pass_rate < 0.85
#     - 任一之前通过的 case 这次失败（不允许 silent regression）
#     - prompt_versions 改动了但没跑过 eval（强制 PR 带跑）
```

**退出码语义**：

| exit code | 含义 | CI 行为 |
|---|---|---|
| 0 | 通过 | 进下一步 |
| 1 | pass_rate < 85% | 阻断 |
| 2 | silent regression（已知 case 失败） | 阻断 |
| 3 | prompt 改了但没跑 eval | 阻断（要求 `--eval-ran=true` 标记） |
| 4 | 工具/网络故障 | 重试 3 次后阻断（不静默失败）|

### 6.2 基线对比规则

每次 CI eval run 都对比上一次 main 分支的 eval_run 作为基线（baseline）：

```python
def diff_vs_baseline(current: EvalRun, baseline: EvalRun) -> Diff:
    return Diff(
        pass_rate_delta=current.pass_rate - baseline.pass_rate,
        regressed_dims=[
            d for d in DIMENSIONS
            if current.dimensions_summary[d] < baseline.dimensions_summary[d]
        ],
        new_failed=set(current.failed_cases) - set(baseline.failed_cases),
        new_passed=set(baseline.failed_cases) - set(current.failed_cases),
    )

# 门禁硬约束：
assert diff.pass_rate_delta >= -0.02   # 允许 -2% 噪声
assert not diff.new_failed              # 不允许新失败
```

### 6.3 PR 合入检查清单（更新 [verification-and-review.md](../../governance/verification-and-review.md)）

Prompt / 节点 spec 改动的 PR：

- [ ] 跑过 Eval（手动或 CI）：附 eval_run_id
- [ ] pass_rate ≥ 85%
- [ ] 无 silent regression（已知 case 仍 pass）
- [ ] 若 pass_rate 下降 ≥5%：补充失败 case 分析 + 决策（接受 / 修复 / Badge Case 加入集）

### 6.4 触发条件（避免 CI 滥跑）

| 文件改动 | 是否触发 Eval |
|---|---|
| `backend/app/prompts/**` | ✅ 必跑 |
| `backend/app/agent/nodes/**` | ✅ 必跑 |
| `backend/app/harness/**` | ✅ 必跑 |
| `backend/app/rules/**`（rule_validator 配置） | ✅ 必跑 |
| `backend/app/api/**` / `services/**` | ❌ 不跑（API 行为测试已覆盖） |
| `frontend/` | ❌ 不跑 |
| `docs/**` | ❌ 不跑 |

实现：CI workflow 用 `paths:` 过滤。

---

## 7. 路由汇总

| 方法 | 路径 | 用途 | 环境 |
|---|---|---|---|
| `POST` | `/api/v1/dev/eval/runs` | 触发一次 eval run（dataset_id + trigger=dev_manual） | dev-only |
| `GET` | `/api/v1/dev/eval/runs` | 列 eval_runs 历史 | dev-only |
| `GET` | `/api/v1/dev/eval/runs/{id}` | 单 eval run 详情 + diff vs baseline | dev-only |
| `GET` | `/api/v1/dev/eval/datasets` | 列 datasets | dev-only |
| `POST` | `/api/v1/dev/eval/datasets` | 创建新 dataset（一般只在 Stage 5 初次手动建 v1.0） | dev-only |
| `POST` | `/api/v1/dev/eval/bad-cases` | Bad Case 回流 | dev-only |
| `GET` | `/api/v1/dev/eval/cases/{case_id}` | 单 case 详情（含 grader 历史） | dev-only |

dev-only 守护与 Replay 一致（[replay.md §6.1](./replay.md)）：启动 assert + 路由注册条件。

---

## 8. 实施顺序

1. **Stage 1 契约冻结**：
   - `eval_datasets` / `eval_cases` / `eval_runs` / `eval_cases_verdicts` 四张表迁移
   - Pydantic schemas + Alembic
2. **Stage 3 真实模型注入完成后（前置）**：
   - 6 grader 的程序部分实现（无 LLM）
   - 手工写 10 个 manual case（normal 类）
3. **Stage 4 证据增强完成后**：补齐 fallback_other / replan / budget_limited case（共 11）
4. **Stage 5 Harness 完成期（核心）**：
   - 补齐 high_risk / edge case（共 9）
   - output_grader（LLM Judge grader）
   - runner + CLI + CI 接入
   - Bad Case API + UI 入口（[developer-trace.md §5](../ui-spec/developer-trace.md)）
   - Report + Baseline diff
5. **Stage 5 退出验证**：
   - 30 case 跑通 + pass_rate ≥ 85%
   - 故障注入（mock LLM 超时 / tool 失败）仍可降级
   - Bad Case 闭环走通（一个生产退化 → 入集 → 下次 CI 抓到）

---

## 9. 不变量汇总

| ID | 描述 |
|---|---|
| INV-E1 | dataset 一旦 `published` 不可改 cases |
| INV-E2 | case input 必须 self-contained（不依赖生产 DB） |
| INV-E3 | 一次 eval run 中，每个 case 独立跑、独立评分，互不影响 |
| INV-E4 | LLM grader 失败不阻断 case passed 判定（仅记 warning） |
| INV-E5 | CI eval 触发时必须带 `git_sha` 和 `prompt_versions` 快照，便于回溯 |
| INV-E6 | eval_runs 写入正常 trace 表（agent_runs），但用 `session_id="eval-{run_id}"` 隔离（避免污染线上统计） |
| INV-E7 | Bad case 加入 dataset 不影响旧 dataset 的版本（minor bump） |
| INV-E8 | pass_rate 硬阈值 85% 不可调（[check-scripts-spec.md §5](../../governance/check-scripts-spec.md) 严禁项） |

---

## 10. 错误边界

| 错误 | 处理 |
|---|---|
| dataset 找不到 / 已 archived | 422 `EVAL_DATASET_UNAVAILABLE` |
| case input transform 失败（缺 fixture / 不完整 trace） | 422 `EVAL_CASE_INCOMPLETE` + 让用户修 source |
| LLM 调用超时（模型 grader） | skip output_grader，记 warning |
| plan_run 内任意节点 fail | 不影响 case 评分（status_grader 自然判 fail） |
| CI eval 退出码 = 4（工具网络故障） | CI 重试 3 次后阻断，不静默通过 |

---

## 11. 参考依据

| 来源 | 用于本文 § |
|---|---|
| [TDD §12.5 Eval](../../architecture/tdd.md) | §1.1 |
| [TDD §11.3](../../architecture/tdd.md) | §4.1 表名 |
| [PRD §7 5 维质量评分](../../overview/product-overview.md) | §3.2 dimensions_grader |
| [rule_validator.spec.md §3](../agent-nodes/rule_validator.spec.md) | §3.2 五维判定 |
| [quality_reviewer.spec.md §3](../agent-nodes/quality_reviewer.spec.md) | §3.2 dim 4 简化 |
| [check-scripts-spec.md §5 check-eval.sh](../../governance/check-scripts-spec.md) | §6.1 |
| [verification-and-review.md](../../governance/verification-and-review.md) | §6.3 |
| [stage-delivery-definition.md §阶段 5](../../governance/stage-delivery-definition.md) | §1.2, §8 |
| DSPy Evaluate / OpenAI Evals 范式 | §3.1 Grader 接口灵感 |
| Anthropic Rajasekaran 2026 Generator/Evaluator adversarial | §3.2 grader 分离 |
| Continue `.continue/checks/`（外部资料：《Harness-engineering 开源工程分享》PDF §5） | §6 CI 门禁灵感 |

---

*本 Eval spec 与 [replay.md](./replay.md)、[harness-overview.md](./harness-overview.md) 共同构成 harness 反馈层 spec 集。*
