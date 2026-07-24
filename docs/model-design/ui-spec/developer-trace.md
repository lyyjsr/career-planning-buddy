# Trace / 调试 / Replay / Eval 开发者页面

| 版本 | v1.0 |
|---|---|
| 日期 | 2026-07-24 |
| 状态 | 草稿 |
| 目的 | 把 Stage 5 退出条件 "Trace 调试页可查看 run / step / tool 详情"、"Replay 页面可用"、"Bad Case 一键入评测集" 展开为前端交互 spec |

---

## 1. 定位

### 1.1 是什么

**开发者页面**是仓库内置的一组前端页面（开发环境默认开启，生产行为见 §2.3），用于：

1. 查看 plan_run 的完整 Trace（run / step / tool 三级）
2. 触发 Replay（Prompt A/B）
3. 触发 Eval（手动跑 dataset）
4. 把生产失败 run 加入 Bad Case 评测集
5. 查看 Eval 报告 + 与基线对比

### 1.2 不是什么

- ❌ 不是后台管理面板（用户 / plan / task CRUD 是另一个范围，PRD 标 P1，非本 spec）
- ❌ 不是日志查看器（结构化日志走 [TDD §15.2](../../architecture/tdd.md) `structlog` JSON）
- ❌ 不是监控告警面板（prometheus / sentry 是远期演进，[ADR-001](../../architecture/adr.md)）

### 1.3 路由

前端路由前缀：`/dev/*`（与后端 `/api/v1/dev/*` 对应）。

| 路径 | 页面 |
|---|---|
| `/dev/traces` | Run 列表页 |
| `/dev/traces/:run_id` | Run 详情页 |
| `/dev/replays` | Replay 列表页 + 触发入口（建议合并到 run 详情，§4） |
| `/dev/eval` | Eval 仪表盘 |
| `/dev/eval/runs/:run_id` | Eval Run 详情页 |
| `/dev/eval/cases/:case_id` | Case 详情页（含 grader 历史） |

---

## 2. 全局约定

### 2.1 入口

主菜单（生产 + 开发都展示，但开发路由生产 404）右上角加"开发者"链接 → `/dev/traces`。

### 2.2 数据来源

所有页面只读 `agent_runs` / `agent_steps` / `tool_calls` / `eval_*` / `replay_runs` 表。无独立 ETL。

### 2.3 访问控制

| env | 行为 |
|---|---|
| `development` | 全部路由 + API 可用 |
| `staging` | 全部可用（QA 评估用） |
| `production` | 前端路由不展示 + 后端 `/api/v1/dev/*` 启动时 `assert env != production`（fail-fast） |

理由：避免生产环境泄露用户 trace（含 cost / 输入 hash）。

### 2.4 数据脱敏

| 字段 | 展示 |
|---|---|
| `agent_steps.input_hash` / `output_hash` | 完整展示 sha256 前 12 字符 + tooltip 显示完整 |
| `tool_calls.args_hash` | 同上 |
| `agent_steps.trace_data.original_message` | 仅 dev 模式展示原文（需 dev flag）；production 永远不存 |
| `tool_calls` 任何 `result_*` | hash 展示；详细 result 走"展开"按钮（trace_data 内查） |
| 用户 PII | **绝不展示**（user_email / phone 等） |

---

## 3. 页面一：Run 列表页 `/dev/traces`

### 3.1 目的

快速定位"上次跑的 plan_run"，回溯失败 / 重放 / 入 bad case。

### 3.2 筛选条件

| 筛选 | 类型 | 默认 |
|---|---|---|
| `status` | multi-select `{pending, running, completed, failed, degraded}` | 全选（除 pending） |
| `goal_type` | multi-select | 全选 |
| `intent` | multi-select | 全选 |
| `cost_min / cost_max` | number | — |
| `latency_min / latency_max` | number（ms）| — |
| `from / to` | datetime | 最近 7 天 |
| `q` | text（match run_id / session_id 前缀） | — |

### 3.3 列表字段

| 列 | 说明 | 排序 |
|---|---|---|
| run_id（短） | uuid 前 8 + copy button | —— |
| status | badge（颜色见 [run-status.mmd](../state-machines/run-status.mmd)） | ✅ |
| user_id（短） | 前 8 | —— |
| goal_type | chip | ✅ |
| intent | chip（来自 step[1].trace_data） | ✅ |
| started_at | YYYY-MM-DD HH:mm:ss | ✅ 默认 desc |
| latency_ms | 数字 + 颜色阈值（>15s 黄、>25s 红） | ✅ |
| cost_cny | 0.0xx | ✅ |
| actions | "详情" "Replay" "加 Bad Case" | —— |

### 3.4 行为

- 点击行 → 跳 `/dev/traces/:run_id`
- 行内 actions 下拉 → 跳详情页对应 tab（Replay tab / Bad Case dialog）

---

## 4. 页面二：Run 详情页 `/dev/traces/:run_id`

这是核心页面，**所有后续特性都从这进入**。布局采用上下两段：上半段 run 总览 + 中间 step 时间线 + 下半段 tab 区（选 step 看 detail / Replay 历史 / Eval 关联）。

### 4.1 Run 总览

```
┌────────────────────────────────────────────────────────────────────┐
│ run_id: r-2a8f-...                          [Copy] [Refresh]        │
│ status: ✅ completed    started: 2026-07-24 10:32:11                │
│ user_id: u-7c3e...     ended:   2026-07-24 10:32:30                 │
│ goal_type: ai_backend   session: s-9f4b...                          │
│ intent: plan             latency: 18.3s     cost: ¥0.092            │
│ fallback_reason: —        prompt_versions: see steps                │
│                                                                     │
│ [▶ Replay this run]  [⊕ Add as Bad Case]  [⛓ Open in LangSmith*]    │
└────────────────────────────────────────────────────────────────────┘
* LangSmith 链接仅在 LANGSMITH_PROJECT 环境变量配置时出现
```

### 4.2 Step 时间线（中部主视觉）

水平时间线（不是列表）：

```
risk_gate ──▶ intent_router ──▶ context_builder ──▶ career_planning_agent ─┐
0ms (80)      80ms (1180)        1260ms (4200)       5460ms (22340)        │
                                                                            │
                                       ┌────────────────────────────────────┘
                                       ▼
        persist ◀── companion_response ◀── revise_or_fallback ◀── quality_reviewer ◀── rule_validator
        29000 (1100) 28000 (890)            27000 (1820)               25600 (1140)       23620 (1280)
```

- 每节点矩形含：node_name / latency_ms / status badge
- 失败节点：红色边框 + 点击展示 error_class
- 点击节点 → 下方 step tab 区切到对应 step
- 编排回环（rewrite 触发重跑 career_planning_agent）→ 显示两个 career_planning_agent 节点（带 round 标记）

### 4.3 Tab 区（下半段）

#### Tab 1：Step Detail（默认）

选定 step 后展示该 step 的全部字段（来自 `agent_steps` 表）：

| 展示组 | 字段 |
|---|---|
| 元信息 | node_name / node_index / prompt_version / model / mock_mode |
| 性能 | tokens_in / tokens_out / cost_cny / latency_ms / llm_latency_ms |
| 状态 | success / error_class / fallback_reason |
| trace_data | 渲染为 JSON 树（collapse by default，敏感字段替换为 hash） |
| Tool calls（仅 career_planning_agent step 可见） | 子表：tool_name / round / args_hash / result_token_count / latency_ms / success |

每行 tool call 提供"展开 fixture"按钮（仅 mock_mode 或 dev 模式）→ 调用 `GET /api/v1/dev/tools/fixtures/{tool_name}/{args_hash}` 拉取详情。

#### Tab 2：Replay History

显示该 run 的所有 Replay（来自 `replay_runs` 表 `source_run_id`）：

| 列 | 说明 |
|---|---|
| replay_id | uuid 短 |
| created_at | —— |
| trigger_by | dev 用户 |
| prompt_versions_override | 例如 `{"career_planning_agent":"v2"}` |
| status | identical / changed / failed badge |
| cost_cny_after | —— |
| action | "查看 Diff" |

行操作"查看 Diff" → 调用 expand `/dev/replays/:id` 弹窗展示 [replay.md §4.1](../harness/replay.md) 的 diff 结构化字段 + 每变化 step 的 changed_fields 详情（点开看完整 JSON diff）。

#### Tab 3：Eval Associations

显示该 run 关联的 eval run（来自 `eval_cases_verdicts.run_id` —— 即这个 run 是某个 eval case 跑出来的）：

| 列 | 说明 |
|---|---|
| eval_run_id | uuid 短 → 跳 `/dev/eval/runs/:id` |
| case_id | uuid 短 → 跳 `/dev/eval/cases/:id` |
| case_name | —— |
| passed | badge |
| aggregate_score | 0.xxx |

### 4.4 入口按钮（总览区段）

#### 4.4.1 Replay this run

点击 → 模态对话框：

```
Replay run r-2a8f-...
─────────────────────────────────────
对该 run 进行 Replay（使用相同输入 + 选定 Prompt 版本重跑）

源信息：
  source status: completed
  original prompt_versions:
    intent_router:           v1
    career_planning_agent:   v1
    quality_reviewer:        v1

Prompt 版本覆盖（留空=用原版本）：
  career_planning_agent:  [v1 ▾]   ☑ 用 v2
  quality_reviewer:       [v1 ▾]   ☐ 不改

Model Override：      [deepseek-chat ▾]
Tool mode：           ◉ mock（推荐）  ◯ original（联网，¥）
Note（可选）：        [输入...]

[Cancel]  [Start Replay →]
```

提交后调用 `POST /api/v1/dev/replays`（[replay.md §6.1](../harness/replay.md)）。完成后 toast "Replay 完成，结果：changed"，切到 Tab 2 显示新行。

#### 4.4.2 Add as Bad Case

点击 → 模态对话框：

```
加入 Bad Case 评测集
─────────────────────────────────────
从 r-2a8f-... 转换为评测 case。

Case Name（必填）：     [replan_with_contradictory_history]
Known Failure Dim：     [Dim 4 连续性 ▾]   (查看 5 维定义)

Expected Overrides（可选，留空自动推断）：
  expected_intent：        [plan ▾]
  expected_task_count：    [1] - [3]
  must_include_keywords：  [输入]
  must_not_include：       [输入]

Note（可选）：           [输入...]

⚠ 转换后 dataset version: v1.2 → v1.3
[Cancel]  [Add to Dataset →]
```

提交后调用 `POST /api/v1/dev/eval/bad-cases`（[eval-system.md §5.2](../harness/eval-system.md)）。完成后 toast "已加入 default dataset v1.3"。

---

## 5. 页面三：Eval 仪表盘 `/dev/eval`

### 5.1 顶部 KPI 卡片

```
┌─ Default Dataset ─────────┐  ┌─ Latest Run ─────────────┐  ┌─ CI Trend ─────────┐
│ v1.3  / 31 cases          │  │ er-9c2  PR #124          │  │ 最近 10 PR 趋势线  │
│ ▲ +1 (bad case added)     │  │ pass_rate 0.903 ▲ +0.036 │  │ y: pass_rate       │
│ categories: 7 类          │  │ 基线 er-8f1 (0.867)      │  │ x: PR #            │
└───────────────────────────┘  └──────────────────────────┘  └────────────────────┘
```

### 5.2 主体三段

#### 5.2.1 最新 Run 摘要卡片

```
Latest Run (er-9c2-...)
  triggered by: ci_pull_request (PR #124)
  git_sha: abc1234
  duration: 4m 32s     cost: ¥1.83    baseline: er-8f1
  pass_rate: 90.3% (28/31)    delta: +3.6%

  Dimensions pass rate:
    dim_1_startable: 0.97 (基线 0.93) ▲
    dim_2_time_match: 0.93 (基线 0.93) ━
    dim_3_cognitive_load: 0.90 (基线 0.87) ▲
    dim_4_continuity:  0.83 (基线 0.80) ▲
    dim_5_deliverable: 0.93 (基线 0.90) ▲

  Failed cases (3):
    c-bad-1  bad_case      dim_4_continuity  ⚠ known
    c-edge-2 edge          intent_misclassification ❓ new regression
    c-5      normal        output_grader (LLM Judge warn)

  [View Full Report →]
```

#### 5.2.2 最近 Runs 列表

| 列 | 说明 |
|---|---|
| eval_run_id | uuid 短 |
| created_at | —— |
| trigger | badge（ci_pull_request / ci_main / dev_manual / bad_case_add） |
| git_sha | 前 7 |
| prompt_versions | 折叠 JSON |
| pass_rate | 0.xxx + 与基线 delta（▲▼━） |
| status | completed / failed |
| actions | "查看详情" |

#### 5.2.3 Case 浏览

表格列出当前 default dataset 的所有 case：

| 列 | 说明 |
|---|---|
| case_id（短） | —— |
| case_name | —— |
| category | badge |
| source | manual / bad_case |
| last_passed | ✅/❌（最近一次 run） |
| known_failure_dimension | 显示（bad_case 必填） |
| actions | "查看详情" / "编辑"（mock_mode 可改 expected_overrides） |

---

## 6. 页面四：Eval Run 详情 `/dev/eval/runs/:id`

### 6.1 顶部

- 元信息（trigger / git_sha / prompt_versions / model / created_at / completed_at / cost / latency）
- baseline run 选择器（可手动对比任意历史 run 而非默认 main）

### 6.2 主体

#### 6.2.1 Cases 表

每个 case 一行：

| 列 | 说明 |
|---|---|
| case_name | —— |
| category | —— |
| passed | ✅/❌ |
| aggregate_score | 0.xxx |
| failed_graders | 列表（点击展开 rationale） |
| latency_ms / cost_cny | —— |
| actions | "跳到 plan_run 详情"（→ `/dev/traces/:run_id`） |

#### 6.2.2 Diff vs Baseline

```
Diff vs baseline (er-8f1 → er-9c2)
─────────────────────────────────────
pass_rate: 0.867 → 0.903  (+0.036)
Dimensions:
  dim_1 ▲   dim_2 ━   dim_3 ▲   dim_4 ▲   dim_5 ▲

New passed (2):
  c-7  normal        previously dim_4 fail
  c-12 replan        previously intent fail

New failed (1): ⚠ silent regression
  c-edge-2 edge     intent_misclassification
  [⊕ Add to focus list]  [View case detail]
```

#### 6.2.3 Dimensions 时间趋势

折线图：该 dataset 最近 10 次 eval_run 每维度 pass_rate（用 [recharts](https://recharts.org) 之类）。

---

## 7. 页面五：Case 详情 `/dev/eval/cases/:case_id`

### 7.1 顶部

- case 元信息（name / category / source / known_failure_dimension）
- input 展示（[eval-system.md §2.3](../harness/eval-system.md) EvalCaseInput 完整 JSON 树）
- expected 展示（同上）

### 7.2 Grader 历史时序

最近 10 次 eval_run 中该 case 的表现：

| 列 | 说明 |
|---|---|
| eval_run_id（短） | —— |
| created_at | —— |
| passed | ✅/❌ |
| aggregate_score | 0.xxx |
| failed_graders | —— |
| grader_results 详情（展开） | 每个 grader 的 rationale |

### 7.3 行为

- "查看当前实现 case 输入" → 调 `POST /api/v1/dev/eval/runs?case_id=...` 单 case 实跑（避免重跑整个 dataset）

---

## 8. 入口导览汇总（cross-link）

| 入口 | 跳到 |
|---|---|
| Run 详情页 "Replay this run" | Replay 历史显示在 same page Tab 2 |
| Run 详情页 "Add as Bad Case" | dataset version bump，Eval 仪表盘 KPI 卡片下次刷新反映 |
| Eval Run 详情 "View case detail" | Case 详情页 |
| Case 详情 "View run_id plan trace" | Run 详情页 |
| Eval Run 详情 "跳到 plan_run 详情" | Run 详情页 |

这构成 Trace ↔ Replay ↔ Eval 的完整闭环。

---

## 9. 实现约定

### 9.1 技术栈

- 与主前端一致：React + TS + Vite（[ADR-001](../../architecture/adr.md)）
- 图表：recharts（轻量，无重型依赖）
- 时间线：自绘 SVG / flexbox（不引专门组件）
- 表格：[tanstack/table](https://tanstack.com/table)（与主前端一致）

### 9.2 dev-only 路由保护

```typescript
// frontend/src/routes/dev/guard.ts
export const devGuard: RouteGuard = ({ env }) => {
  if (env !== 'production') return true;
  return redirect('/404');
};
```

### 9.3 性能

- 列表分页：30 行 / 页（与 Agent run 列表一致）
- 时间线 step 数 ≤ 11 → 不需虚拟化
- JSON 树渲染 collapse 默认（避免一次性渲染 huge trace_data）

### 9.4 错误处理

- dev API 5xx：toast "Dev API 错误，请看 backend log"（不重试，让开发者去查）
- 404：明确指出 trace / replay / eval_run 不存在
- 权限错误：dev flag 关时直接 redirect `/404`

---

## 10. 不变量

| ID | 描述 |
|---|---|
| INV-UI1 | 所有页面只读，**不修改** agent_runs / agent_steps / tool_calls |
| INV-UI2 | 修改操作走 POST / PUT API（Replay / Bad Case），不通过 GET 变更状态 |
| INV-UI3 | production env 下 dev 路由必须 404（前端 + 后端双重保护） |
| INV-UI4 | 用户 PII 字段**绝不**展示（即使有也要 redact）|
| INV-UI5 | 列表筛选 ≤ 7 天为默认（避免大数据量） |

---

## 11. 与 Stage 退出条件对齐

来自 [stage-delivery-definition.md](../../governance/stage-delivery-definition.md)：

| Stage | 涉及本 spec 哪一节 | 退出条件摘 |
|---|---|---|
| 2 纵切（Mock） | §3, §4.1, §4.2, §4.3 Tab1 | Trace 开发者页面可查看 Mock run 的 step 详情 |
| 5 Harness 完成 | §4.1 入口 / §4.4 / §5 / §6 / §7 | Replay 页可用（同输入重跑 → 展示差异）<br>Eval 系统可用（30 case + 自动 grader + 报告）<br>Bad Case 修复闭环（失败 trace 一键加入评测集） |

**Stage 2 退出条件**只需完成「Run 列表 + Run 详情 + Step Detail Tab」——不需要 Replay / Eval / Bad Case 入口。该部分开发可在 Stage 2 Mock 跑通后启动，不阻塞主路径。

---

## 12. 参考依据

| 来源 | 用于本文 § |
|---|---|
| [TDD §12.1-12.5](../../architecture/tdd.md) | §1 全局数据来源 |
| [trace-tables.md](../data-models/trace-tables.md) | §4 step / tool 字段 |
| [state-machines/run-status.mmd](../state-machines/run-status.mmd) | §3.3 status badge 颜色 |
| [replay.md](../harness/replay.md) | §4.2 Replay tab / §4.4.1 入口 |
| [eval-system.md](../harness/eval-system.md) | §4.4.2 Bad Case / §5 / §6 / §7 |
| [stage-delivery-definition.md](../../governance/stage-delivery-definition.md) | §11 实施阶段 |
| [api-and-data-contracts.md](../../architecture/api-and-data-contracts.md) SSE | §4 step 时间线 |
| LangSmith UI / LangFuse UI（业界） | §4 时间线 + §6 趋势图设计灵感 |
| Claude Code `/rewind` UI（Anthropic 2025） | §4.4.1 Replay 模态对话框灵感 |

---

*本 Developer Trace spec 与 [harness-overview.md](../harness/harness-overview.md)、[replay.md](../harness/replay.md)、[eval-system.md](../harness/eval-system.md) 共同构成 harness 反馈层 spec 集。*
