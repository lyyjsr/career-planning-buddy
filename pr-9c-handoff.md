# PR-9c Handoff — Pairwise Judge + Calibration

> 状态：交接文档。PR-9a / PR-9b 已合入 `origin/feat/eval`；PR-9c 尚未开工。
> 作者意图：下一会话以此文档作为入口，**不要靠聊天历史翻找上下文**。

---

## 0. 当前状态快照

| 项目 | 值 |
|---|---|
| 分支 | `feat/eval` |
| 最近 commit | `e953e6b PR-9b: failure taxonomy + live lifecycle + cancel/list/progress/regenerate` |
| 父 commit | `eca38d3 PR-9a: multi-trial statistics + report separation` |
| Alembic head | `20260810_0013`（PR-9b 加 `eval_experiments.cancel_requested_at / report_revision / report_content_hash`）|
| 测试 | `278/278 passed`（.env mask `AGENT_FEATURE_STAGE`+`AGENT_MAX_TOOL_ROUNDS` 之后；这两个字面量会让 `Settings()` 报 `Literal` 校验错 — known, 历史真因不在 PR-9b，是 `.env` 加载时 str→int coercion 未做）|
| `.env` | 已还原（`AGENT_FEATURE_STAGE=5`、`AGENT_MAX_TOOL_ROUNDS=0`）|
| 工作区 | clean；本地 == `origin/feat/eval` |

跑全量测试需要 mask `.env` 两个字段（PR-1 起）：
```bash
cp .env .env.backup
sed -i.bak 's/^AGENT_FEATURE_STAGE=/#AGENT_FEATURE_STAGE=/; s/^AGENT_MAX_TOOL_ROUNDS=/#AGENT_MAX_TOOL_ROUNDS=/' .env
cd backend && /opt/anaconda3/envs/cp/bin/python -m pytest tests/ -q
cd .. && mv .env.backup .env && rm -f .env.bak
```

---

## 1. PR-9a 已完成（已 push，SHA `eca38d3`）

### 新增
- `backend/evals/v2/stats.py` — Wilson/Normal CI、`CaseStat`、`ExperimentStat`、`compute_case_stats`、`compute_experiment_stats`。PR-9b 已升级为基于 `app/harness/errors` taxonomy 派生 `RUNTIME_FAILURE_CODES`/`USER_CANCEL_CODES`。
- `backend/tests/evals_v2/test_eval_stats.py`（14 单测）
- `backend/tests/evals_v2/test_eval_stats_integration.py`（2 DB 集成）

### 修改
- `TrialSummary.trial_index: int = 0`（向后兼容 default）。
- `ExperimentReport.case_stats: dict[str, CaseStat]` + `experiment_stats: ExperimentStat | None`。
- `EvalRunReportResponse.case_stats` + `experiment_stats`（默认空，向后兼容）。
- `scripts/generate_openapi` 重生成快照。

PR-9b 已对 `CaseStat` / `ExperimentStat` 增加 `configuration_failure_count` + `cancelled_by_user_count`（向后不兼容的手工构造路径需要补这两字段）。

---

## 2. PR-9b 已完成（已 push，SHA `e953e6b`）

### Cluster A — Failure Taxonomy
- `backend/app/harness/errors.py`（新）— `EvalFailureCode`/`FailureCategory` StrEnum + `normalize_failure_code()` + `RUNTIME_FAILURE_CATEGORIES` + `RUNTIME_FAILURE_CODES`/`USER_CANCEL_CODES`/`CONFIGURATION_FAILURE_CODES` 集合。
- `app/harness/provider_calls/recorder.py` — fix `exc.code` bug（取代 `type(exc).__name__`）。
- `evals/v2/stats.py` — bucket 改派生自 taxonomy；新 bucket 字段在 `CaseStat` / `ExperimentStat`。

⚠️ **架构 invariant**：`app/agent/errors.py` 保持 agent layer 独立，**禁止 import `app/harness/errors`**（依赖方向 Eval Harness -> Agent）。新会话必须保持这条边界。

### Cluster B — alembic 0013 + List/Progress/Regenerate
- `backend/alembic/versions/20260810_0013_eval_live_lifecycle.py` — 3 列 + partial index。
- `EvalExperiment` ORM 加 `cancel_requested_at` / `report_revision` / `report_content_hash`。
- `EvalRepository.list_experiments(status, limit, offset)`。
- 3 新 endpoint：
  - `GET /api/v1/eval/runs`（分页 list）
  - `GET /api/v1/eval/runs/{id}/progress`（轻量进度，不推断 current_step）
  - `POST /api/v1/eval/runs/{id}/report/regenerate`（**纯 SELECT**，content-hash 驱动 revision）
- `EvalService.regenerate_report()` — borrow `report_content_hash` 比对；变化才 bump。

### Cluster C — Cancel
- `POST /api/v1/eval/runs/{id}/cancel`，返回 202 Accepted + `cancel_requested: bool`。
- `cancel_requested_at` 是 FACT 记录，**不是终态**（`status=='cancelled'` 才是）。
- `EvalRunnerExecutor.recover_interrupted()` crash-evidence 优先：crash 后 experiments = failed + 所有非 terminal trial = `PROCESS_INTERRUPTED`，**即使 cancel_requested_at 已记也不标 cancelled**。

### Cluster D — Live Provider
- Settings: `eval_audit_live_calls: bool = True` / `eval_provider_seed_mode: Literal[...]`（"provider_seed" 默认）。
- `TrialRunner._build_executor` live 分支：audit_live_calls=True 时安装 `ProviderCallRecorder` + `Audit*Provider` wrapper（call shape 与 mock/fixture 同形）。
- `EvalService.create_experiment` 守卫：`execution_mode=live_provider && settings.llm_provider=='mock'` → 409 `EVAL_PROVIDER_MODE_INVALID`。

### 已知 PR-9b 未做（PR-9b.next 或与 PR-9c 协同）
- **RetryingProvider wrapper**（Q3 决策：在 Audit 外层）
- **ProviderCapabilities.supports_seed + SeedContext**（Q7 决策：seed 不强映射 temperature；pass-through to inner provider）
- **`provider_calls.retry_attempt >= 1` 的 ck 迁移**（现在仍 default 0）

---

## 3. PR-9c 待开工（拆两子 PR，已与用户对齐）

### PR-9c.1 — Pairwise Judge Core

**明确范围**：
- Pair contract（baseline + candidate trial_id、case_id、ab_seed、judge_run_id、两个 outcome projection）
- 授权输入投影：Judge 只读 `EvidenceKind.REQUEST_CONSTRAINTS` + `EvidenceKind.PLAN_PROJECTION`，**禁读** transcript / raw LLM response（防泄漏 + 信息最小化）
- A/B 盲化与顺序交换（ab_seed 哈希决定 swap；raw winner 写 DB 时 unswap 到 `(baseline_trial_id, candidate_trial_id)` 真值）
- Judge Provider Protocol：轻量 `EvalPairwiseJudge` 类（直接 httpx + OpenAI-compatible；**不依赖 langchain**）
- Judge result / version contract：`EvalPairwiseScore` ORM + alembic 0014 + 5 维度分数（actionability / alignment / personalization / clarity / consistency，整数 1-5）+ winner ∈ {a, b, tie}
- Fixture Judge（mock）：单测不需要 live LLM 凭据
- agreement 和 position-bias 纯函数（`evals/v2/calibration.py`）
- 最小持久化 + 单元测试
- **不实现** 人工评审 HTTP 和正式校准流程

**迁移**：`alembic/versions/20260812_0014_eval_pairwise_scores.py`（用户习惯是日期 + 序号；下一会话开工时取当天日期，序号 0014）
- 表名建议：`eval_pairwise_scores`
- 字段（抄原 plan）：id（UUID PK）、`baseline_experiment_id` + FK、`candidate_experiment_id` + FK、`baseline_trial_id` + FK、`candidate_trial_id` + FK、`case_id`、`judge_run_id`、`winner` (ck ∈ a/b/tie)、5 × `*_score` (Numeric 4,2 ck between 1 and 5)、`ab_position_swapped` (bool)、`calibrated` (bool default false)、usage token fields、`judge_model`、`judge_latency_ms`、`evidence_json`、`rationale`、`created_at`
- UQ `(baseline_trial_id, candidate_trial_id, judge_run_id)` → 客户端重试幂等
- Index `(baseline_experiment_id)`、`(candidate_experiment_id)`、`(case_id)`

**新文件**：
- `evals/v2/judge.py`（`EvalPairwiseJudge`、`PairwiseJudgePrompt`、`PairwiseJudgeOutput`）
- `evals/v2/calibration.py`（agreement_rate、position_bias_rate 纯函数；κ 留 9c.2）
- `evals/v2/pairwise_loader.py`（Pair contract loader；sources from real Trials，**不手工凭空编**）
- `tests/evals_v2/test_pairwise_judge.py`

**编辑**：
- `app/models/eval.py`（+ `EvalPairwiseScore` ORM）
- `app/repositories/evals.py`（`create_pairwise_score` / `list_pairwise_scores`）
- 没有 HTTP endpoint（9c.1 只交付 core + tests）

**退出门禁**：
- alembic 0014 上/下都跑通
- EvalPairwiseJudge.build_prompt 渲染 rubric + true AB swap 被 swap 回来的 unswap 一致（unit test）
- PairwiseJudgeOutput schema 校验 invalid winner 拒绝、dimension 超出 1-5 拒绝（3 tests）
- `agreement_rate` 和 `position_bias_rate` 纯函数算式（4 tests）
- 278 → ~288 全绿

### PR-9c.2 — Calibration Workflow

**明确范围**：
- Calibration JSONL loader + 文件 hash（hash 写进 calibration report，让审计可追溯）
- **人工 label 导入工具**（import 时 `human_label` 字段**单独写表 / 独立字段**，不允许任何代码自动生成冒充）
- agreement / confusion matrix / per-dimension Cohens kappa / per-slice
- position-bias 报告（swap-a-b 的 winner imbalance）
- `calibration_status` enum：`passing | failing | insufficient`（阈值：agreement ≥ 0.70 AND position_bias_rate ≤ 0.15 → passing；< 0.60 agreement → failing；< 10 pair → insufficient）
- HTTP endpoints：`POST /api/v1/eval/runs/{baseline_exp}/pairwise/run` + `GET /api/v1/eval/runs/{exp}/pairwise/result` + `GET /api/v1/eval/pairwise/calibration`
- 集成测试
- **正式人工校准**（≥100 confirmed human-judged pair）

**Calibration 数据分工（用户决策，强制约束）**：
1. Codex 从真实 Baseline/Candidate Trial 生成 **20-30 对 smoke 草稿**；`human_label` 字段保持空或 `null`
2. Codex **可单独生成** `suggested_label`（helps the human reviewer），但**绝对不得写入 `human_label`**
3. 人工负责最终确认和裁决（reviewer 申请 commit 时填 `human_label`）
4. 20-30 对仅用于 **dev smoke**；正式退出门禁仍为 **≥100 个有效人工确认/裁决 Pair**
5. Pair **优先来自真实 Trial**（pull from stages 5 / runtime_smoke 已有 outcome），不得主要依靠手工凭空编造

**新文件**：
- `evals/v2/datasets/pairwise-calibration-v1.jsonl`（20-30 行；**source from real Trials**；`human_label: null`）
- `evals/v2/datasets/pairwise-calibration-labels.jsonl`（reviewer 确认后填，**单独文件 / 单独 commit path**）
- `evals/v2/calibration.py`（扩展：Cohens κ + per-slice + status）
- `tests/evals_v2/test_calibrated_dataset.py`
- `tests/evals_v2/test_pairwise_api.py`

**编辑**：
- `app/api/evals.py`（3 新 endpoint）
- `app/schemas/evals.py`（4 新 schema）
- `app/services/evals.py`（`run_pairwise_judge` + `list_pairwise_scores` + `compute_pairwise_metrics`）
- `tests/conftest.py`（StubEvalRunnerExecutor 扩 + `StubPairwiseJudge` 或单独 stub）
- `tests/snapshots/openapi.json`（auto-regen）

---

## 4. 当前 report / evidence 数据契约（PR-9c 必读）

### AuthorizedView 投影（PR-9c Judge 输入）
- `EvidenceKind.REQUEST_CONSTRAINTS`：含 `expect_constraint` string，case.provider_fixtures 注入
- `EvidenceKind.PLAN_PROJECTION`：完整 PlanCandidate（含 `evidence_refs`、`tasks`、`summary`、`weekly_focus`）
- `EvidenceKind.EVIDENCE_VISIBLE_REFS`：visible refs 集合
- `EvidenceKind.EXPECTED_CITATIONS_MAP`（PR-8b）：fixture_memory_id → Memory UUID map

存储位置：`eval_evidence_items` 表（EvalEvidenceItem），`EvalRepository.list_evidence_items(trial_id)` 拉取；`pr` 数量大致 ~20 行 per trial（含 PLAN_PROJECTION、EVENT_PROJECTION × n、TOOL_CALL_PROJECTION × n、REQUEST_CONSTRAINTS、RUN_METRICS、OUTCOME_STATUS、调 grade 后还加 6 行 EvalScore 行 per grader）。

### ExperimentReport 形状
```
{
  "experiment_id": UUID str,
  "experiment_status": literal["draft","running","completed","failed","cancelled"],
  "trial_count": int,
  "completed_trial_count": int,
  "scored_trial_count": int,
  "hard_gate_pass_fraction": float,
  "any_score_generated": bool,
  "trials": [TrialSummary_dict],
  "counterfactual_pairs": [CounterfactualPairDiff_dict],   # 空 when 无 variant 桩
  "case_stats": {case_id: CaseStat_dict},                  # PR-9a
  "experiment_stats": ExperimentStat_dict | None,          # PR-9a
  # HTTP report layer 额外加：
  "revision": int,                                          # PR-9b
  "cancel_requested_at": datetime | None,                  # PR-9b
}
```

`TrialSummary`：`trial_id, case_id, status, run_status, result_kind, tokens_in, tokens_out, latency_ms, error_code, terminal_event_count, tool_call_count, variant=None, counterfactual_group_id=None, trial_index=0`

**Pairwise Judge 不修改 ExperimentReport 形状**；它在 Pairwise 结果 endpoint 返回单独 schema。但是 `EvalPairwiseScore` 行将持久化在 `eval_pairwise_scores` 表，**绝不混入 eval_scores 表**（避免污染 hard_gate_pass_fraction）。

---

## 5. 待决问题（用户已部分定，但新会话需重新对齐）

| 问题 | 已知偏好 | 需重新对齐的细节 |
|---|---|---|
| Judge LLM 凭据 | 复用 `settings.llm_*` | 是否 Product 环境用 dev-privileged model（避免同一被评模型当 Judge 的 self-评审 bias） |
| Pair output 投影的字段 min-set | summary + evidence_refs + tasks | 是否加 `weekly_focus` / plan JSON 的 keywords |
| Judge prompt 语言 | 简体中文 | system prompt 是否要包含 ab bias detection hint |
| Calibration `calibration_status` 阈值 | spec 默认 agreement ≥ 0.70 / position_bias ≤ 0.15 | 是否 9c.2 落地为 Settings 可调（不硬编码）|
| Pairwise 是否纳入 experiment report response | 9c.1 决策：不纳入 | 复用 `/report/regenerate` endpoint 不动；只通过 `/pairwise/result` 独立返回 |
| Live LLM 调用 cost 来源 | real provider budget（同 PR-9b live） | 是否限制 Judge 在 Candidate Eval phase（避免 prod-运行时调用） |

---

## 6. 命令样例（下一会话复用）

```bash
# Branch + base
cd "/Users/huanqi/Accompany Project/career-planning-buddy-ly"
git checkout feat/eval
git pull

# Pre-test mask .env（每次跑 pytest 前）
cp .env .env.backup
sed -i.bak 's/^AGENT_FEATURE_STAGE=/#AGENT_FEATURE_STAGE=/; s/^AGENT_MAX_TOOL_ROUNDS=/#AGENT_MAX_TOOL_ROUNDS=/' .env

# Run
cd backend && /opt/anaconda3/envs/cp/bin/python -m pytest tests/ -q

# Restore
cd .. && mv .env.backup .env && rm -f .env.bak
```

---

## 7. 下一会话开工 checklist

1. **本文档第 0 节**：复跑 `git status` + `git log --oneline -3` 确认仍 clean + head 仍 `e953e6b`
2. **复跑全量 pytest**：mask `.env` 后跑一次，期望 278/278
3. **确认 alembic head**：`alembic current` 期望显示 `20260810_0013 (head)`
4. **读 PR-9c plan**（旧会话已批准但 9c 未开工；本 handoff §3 含拆分后的范围；plan 不够细需要重进 EnterPlanMode + 用户批准）
5. **不要立即写 code**：先进 EnterPlanMode 写 PR-9c.1 final plan（基于本 handoff §3.1 + recon，避免依赖本会话的 chat history）
6. **Calibration 草稿生成**：PR-9c.1 完成后，下一会话先用真实 Trial 跑 baseline vs candidate，生成 20-30 行 jsonl（`human_label: null`）；**绝不手工 author**；让 reviewer 填 label 是 PR-9c.2 任务
7. **保持架构 invariant**：Agent layer (`app/agent/*`) 不得 import Eval Harness layer (`app/harness/*` / `evals/v2/*`)

---

END
