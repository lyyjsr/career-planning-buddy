# Replay 设计

| 版本 | v1.0 |
|---|---|
| 日期 | 2026-07-24 |
| 状态 | 草稿 |
| 目的 | 把 [TDD §12.2](../../architecture/tdd.md) "Replay" 三行概念展开为可实现的 spec：输入快照、prompt_version 锁定、执行约束、diff 报告 |

---

## 1. 定位与价值

### 1.1 是什么

**Replay** = 给定一个历史 run_id（或等效输入快照），按其原始输入、原始 Prompt 版本、原始模型配置，重跑一次 plan_run，并与原始结果做 **diff**，用于验证 Prompt / 模型 / 工作流改动是否引入"无声回归"。

### 1.2 不是什么

- ❌ 不是**线上重试**：用户感知的"重新规划"应走 `POST /api/v1/agent-runs`（创建新 run）
- ❌ 不是**热切换**：Prompt 默认版本的切换见 [prompt-versioning-standard.md §6](../../standards/prompts/prompt-versioning-standard.md)，不靠 Replay
- ❌ 不是**回放给用户看**：Replay 仅在开发者页面使用（非 prod user 可见）

### 1.3 解决的问题

| 工程问题 | 不用 Replay | 用 Replay |
|---|---|---|
| 改了 `career_planning_agent/task_v1.py` → 想知道对历史产出有什么影响 | 改完上线等线上数据回灌——风险大 | Replay N 个历史 run，看 diff，再决定合入 |
| 升 DeepSeek V4 → V5 | 接入后写个临时脚本对比——易遗漏 | Replay 固定基线集 |
| 调整 Tool 中间件 timeout 5s→10s | 怕"看似改对实际破 case" | Replay 看哪些 run 行为变了 |
| 修改某节点 Spec（比如 rule_validator 加新规则） | 单测覆盖有限 | 全量 Replay 看现实影响 |

### 1.4 与 [Eval](./eval-system.md) 的区别

| 维度 | Replay | Eval |
|---|---|---|
| 输入 | 历史真实 run_id | 固定 30 case（人工 + bad case 沉淀） |
| 输出对比维度 | step 级 diff（before vs after） | 维度级评分 vs 基线 |
| 是否调真实 LLM | 是 | 是 |
| 是否调真实 tool | 是（可强制 mock） | 优先 mock（保证可重现） |
| 触发 | 开发者手动 | CI 自动 / PR 评审 |

**Replay 是"对真实历史的回放"，Eval 是"对固定集的快速试错"。** 两者互补：Eval 防 case 集退化、Replay 防广角行为偏移。

---

## 2. 输入契约

### 2.1 Replay 请求

`POST /api/v1/dev/replays`（dev-only 路由，仅 `env=development` 暴露）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `source_run_id` | `uuid` | ✅ | 历史源 run |
| `prompt_versions_override` | `dict[str, str] \| null` | ❌ | 形如 `{"career_planning_agent": "v2"}`；未指定 → 用 source run 的原版本 |
| `model_override` | `str \| null` | ❌ | 默认用 source run 的原 model |
| `tool_mode` | `Literal["original","mock"]` | ✅ 默认 `"original"` | `"mock"`：所有 tool 用 fixture（避免联网/费用）；`"original"`：按原 run 真调 |
| `timeout_s` | `int` | ✅ 默认 60 | 单次 Replay 上限 |
| `note` | `str \| null` | ❌ | 人工备注（"测试 v2 prompt 优化连续性"） |

**响应 201**：
```json
{
  "replay_id": "rp-...",
  "source_run_id": "r-2a8f-...",
  "status": "completed",
  "diff": { /* 见 §4 */ }
}
```

### 2.2 输入快照重建（Replay 如何"还原"原 run 的输入）

Replay 不依赖额外的"输入快照表"——**`agent_runs` + `agent_steps` + `tool_calls` 三张表本身就是完整的输入快照**（[trace-tables.md](../data-models/trace-tables.md)）。重建算法：

```python
def rebuild_replay_input(source_run_id: str) -> ReplayInput:
    run = repo.get_run(source_run_id)
    steps = repo.list_steps(run_id=source_run_id, order="asc")
    # 从 steps[0..3] 提取前置节点输出（risk_gate / intent_router / context_builder）
    intent = steps[1].trace_data["intent_result"]
    context_blob = steps[2].trace_data["planning_context"]
    # tool_calls 的 args_hash 是只读的——后续 §3.3 解释如何处理
    return ReplayInput(
        user_id=run.user_id,
        message=steps[0].trace_data["original_message"],
        intent_snapshot=intent,
        context_snapshot=context_blob,
        prompt_versions={s.node_name: s.prompt_version for s in steps if s.prompt_version},
        model=run.model,
        budget={... /* TDD §12.4 */},
    )
```

**关键决策**：Replay **不重放整条 plan_run，只从 `career_planning_agent` 节点重放**；前置节点（risk_gate / intent_router / context_builder）的输入直接从 Trace 表读 snapshot 使用。理由：

1. 前置节点输出已被 trace 记录，重跑只增成本；
2. Prompt 改动 99% 发生在 `career_planning_agent` / `quality_reviewer` / `revise_or_fallback` 三个节点上，前置节点改动极少；
3. 用户问题（"改 prompt 影响了什么"）大半场景就是要看 agent 节点行为变化。

**例外**：若 `prompt_versions_override` 含前置节点（如 `intent_router`），则从该节点重跑而非用 snapshot——支持追因到前置。

---

## 3. 执行约定

### 3.1 Prompt 版本锁定（强 R-Prompt1）

```python
# 伪代码
for node in nodes_to_replay:
    version = prompt_versions_override.get(node.name) \
              or source_steps[node.name].prompt_version
    prompt = load_prompt(node.name, version=version, frozen=True)
```

- **默认**：未指定 override → 用原 run 记录的版本（即使该版本已 archive）
- **强制 fallback**：若已 archive 不可加载（ 按 [prompt-versioning-standard](../../standards/prompts/prompt-versioning-standard.md) 是不允许的，archive 必须 git 历史可查）→ trace 写 `fallback_reason="prompt_version_unavailable"`，Replay 标 failed

### 3.2 Tool 行为

| `tool_mode` | 行为 | 用途 |
|---|---|---|
| `"original"` | 真调（web_search 真联网、rag_retrieve 真走 pgvector） | 验证 tool 行为变化 |
| `"mock"` | tool 直接返回 source run 的 `args_hash` 对应的 `result_hash` 内容（从 trace 反查） | 隔离模型行为（推荐默认） |

**`"mock"` 模式的实现要点**：tool_calls 表只存 `args_hash` 不存 args 原文——所以 mock 模式需要 tool executor 自带 fixture 库，按 `args_hash → fixture` 查找；若查不到 → 该 tool call 退化为空结果 + trace warn。

> 工件库：`backend/app/harness/replay/fixtures/{tool_name}/{args_hash}.json`。手工维护，缺 fixture 时告警（**Stage 5 才落地**，缺时不阻塞）。

### 3.3 模型调用

| 字段 | 默认 | override |
|---|---|---|
| `model` | source run 记录的 `model` 字段 | 可改 |
| `temperature` | source run 记录值（**若 trace 没存则默认 0.0**） | 可改 |
| `max_tokens` 等 | source run 记录值 | 可改 |

**风险约束**：Replay 总成本必须显式纳入预算（见 [TDD §12.4 Budget](../../architecture/tdd.md)）——Replay 调真实 LLM 产生的 cost 也累加到该 run 当日预算（防止开发者 Replay 刷爆 quota）。

### 3.4 Budget 检查

Replay 启动前校验：

```python
assert source_steps.cardinality <= 11 + max_tools * 2
assert expected_cost_cny <= BUDGET_REPLAY_MAX_CNY  # default 0.5
assert timeout_s <= 120
```

### 3.5 并发约束

- 单个 source_run_id 同时**只能有 1 个**活跃 Replay（避免并发刷数据）
- 这一约束以 Postgres advisory lock 实现：`pg_advisory_xact_lock(hashtext(source_run_id))`

---

## 4. Diff 报告格式

Replay 完成后写 1 行 `replay_runs` 表（**新表，定义见 §5**）并返回 diff JSON。

### 4.1 JSON 结构

```jsonc
{
  "replay_id": "rp-...",
  "source_run_id": "r-...",
  "summary": {
    "status": "changed",           // "identical" | "changed" | "failed"
    "steps_total": 11,
    "steps_changed": 2,
    "validation_before": { "dim_1": "pass", "dim_4": "pass", "all_pass": true },
    "validation_after":  { "dim_1": "pass", "dim_4": "fail", "all_pass": false },
    "cost_cny_before": 0.092,
    "cost_cny_after":  0.108,
    "tokens_before":   5020,
    "tokens_after":    6440,
    "latency_ms_before": 18340,
    "latency_ms_after":  22980
  },
  "steps_diff": [
    {
      "node_name": "career_planning_agent",
      "status_before": "ok",
      "status_after": "ok",
      "output_hash_before": "sha256:aaa...",
      "output_hash_after":  "sha256:bbb...",
      "changed_fields": ["candidate.tasks[0].starter_action", "candidate.tasks[1].deliverable"]
    },
    {
      "node_name": "quality_reviewer",
      "status_before": "ok",
      "status_after": "ok",
      "dim_4_before": "pass",
      "dim_4_after":  "fail",
      "rationale_after": "task 1 与昨日 context 无关联..."
    }
  ]
}
```

### 4.2 status 判定

| status | 条件 |
|---|---|
| `"identical"` | 所有 step output_hash 一致 + validation 全 pass 状态一致 |
| `"changed"` | 任一 step 产出 hash 不一致 OR validation pass/fail 翻转 |
| `"failed"` | Replay 中任一节点抛出未恢复异常 |

### 4.3 字段级 diff 算法

为避免输出超大字符串全 diff，分两步：

1. **第一遍**：所有 step 算 `output_hash = sha256(json.dumps(output, sort_keys=True))`，对比 hash。全等 → `identical`。
2. **第二遍**（仅 hash 不等时）：对不等 step 做结构化 diff（基于 dict 路径），只记录 changed_fields 列表——不存完整 before/after 文本。

详细字符串对比在开发者页面提供"点开看完整 diff"功能（见 [developer-trace.md](../ui-spec/developer-trace.md)）。

---

## 5. 数据表

### 5.1 新增 `replay_runs` 表

| 字段 | 类型 | NULL | 默认 | 约束 | 说明 |
|---|---|---|---|---|---|
| `id` | `uuid` | NO | `gen_random_uuid()` | PK | —— |
| `source_run_id` | `uuid` | NO | — | FK→agent_runs.id | 源 run |
| `created_by` | `uuid` | NO | — | FK→users.id | 触发 Replay 的 dev 用户 |
| `prompt_versions_override` | `jsonb` | YES | NULL | —— | 形如 `{"career_planning_agent":"v2"}` |
| `model_override` | `varchar(64)` | YES | NULL | —— | —— |
| `tool_mode` | `varchar(16)` | NO | `'original'` | CHECK ∈ `{"original","mock"}` | —— |
| `status` | `varchar(16)` | NO | `'pending'` | CHECK ∈ `{pending,running,completed,failed}` | 比运行级状态机简单（Replay 不写 plan_run 的事务） |
| `diff_summary` | `jsonb` | YES | NULL | —— | §4.1 summary 段 |
| `diff_steps` | `jsonb` | YES | NULL | —— | §4.1 steps_diff 段 |
| `cost_cny` | `float` | NO | `0.0` | `ge=0` | —— |
| `note` | `text` | YES | NULL | —— | 人工备注 |
| `created_at` | `timestamptz` | NO | `now()` | —— | —— |
| `finished_at` | `timestamptz` | YES | NULL | —— | —— |

**索引**：
- `idx_replays_source(source_run_id, created_at DESC)` — 看某源 run 的所有 Replay 历史
- `idx_replays_status(status) WHERE status IN ('pending','running')` — 调度

### 5.2 与已有 trace 表的关系

- `replay_runs.source_run_id` → `agent_runs.id`：读输入快照来源
- Replay 内部产生的 trace **不写入** `agent_steps` / `tool_calls`（避免污染生产 trace 流）——只写到 `replay_runs.diff_steps`
- 若需要详细 step trace：可在请求加 `?detailed=true`，把每个 replay step 也写到独立 `replay_steps` 表（v2 扩展，MVP 不做）

---

## 6. 路由与时序

### 6.1 端点汇总（dev-only）

| 方法 | 路径 | 用途 |
|---|---|---|
| `POST` | `/api/v1/dev/replays` | 触发一次 Replay，返回 replay_id |
| `GET` | `/api/v1/dev/replays/{replay_id}` | 拉取 diff 结果 |
| `GET` | `/api/v1/dev/replays?source_run_id={id}` | 列某 run 的所有 Replay |

**dev-only 守护**：所有路由注册由 `core/config.env == "development"` 守。生产暴露 → fail-fast（启动时 assert）。

### 6.2 时序

```mermaid
sequenceDiagram
    participant DEV as Developer
    participant API as FastAPI /dev/replays
    participant SVC as ReplayService
    participant DB as PostgreSQL
    participant GRAPH as LangGraph
    participant LLM as Provider

    DEV->>API: POST replay (source_run_id, prompt_v2)
    API->>SVC: invoke()
    SVC->>DB: 读 agent_runs + steps + tool_calls
    SAC: Note over SVC: rebuild_replay_input()
    SVC->>SVC: 校验 Budget/并发锁
    SVC->>GRAPH: invoke(ReplayPlanRun, input)
    GRAPH->>LLM: 按 prompt_v2 调 LLM
    GRAPH-->>SVC: 新产出
    SVC->>SVC: 与 source hash diff
    SVC->>DB: 写 replay_runs.diff_*
    API-->>DEV: 201 + diff JSON
```

---

## 7. 实施约束

| 约束 | 值 | 依据 |
|---|---|---|
| 单次 Replay 总成本上限 | ¥0.5 | 防滥用；与 [TDD §12.4](../../architecture/tdd.md) 0.2 同量级 +30% buffer |
| 单次 Replay 超时 | 60s（可调到 120s） | 比生产 20s 宽松（容忍模型慢） |
| 并发 | 单 source_run_id 1 个 | advisory lock |
| 路由可见性 | 仅 dev env | config 启动 assert |
| 写入生产 trace 表 | ❌ 不写 | 避免 agent_runs 表被 replay 数据污染 |
| 默认 tool_mode | `"mock"` | 节省联网费用 + 可重现 |

---

## 8. 不变量

| ID | 不变量 |
|---|---|
| INV-1 | Replay 不产生任何 `plans` / `tasks` / `memories` / `memory_candidates` 写入（持久化旁路） |
| INV-2 | Replay 不修改 source_run 的任何字段（只读） |
| INV-3 | 若 `prompt_versions_override` 未指定 → replay 必须用原 run 记录的 prompt_version（不可"用最新") |
| INV-4 | `status=identical` 当且仅当所有 step hash + validation 翻转状态全等 |
| INV-5 | `agent_runs` 表中 `status=pending` 或 `running` 的 run，**不可**被 Replay（防重入） |

---

## 9. 错误边界

| 错误 | 处理 |
|---|---|
| source_run_id 不存在 | 404 `REPLAY_SOURCE_NOT_FOUND` |
| source run status ∈ {pending, running} | 409 `REPLAY_SOURCE_STILL_RUNNING` |
| `prompt_versions_override` 指定的版本加载失败 | 422 `REPLAY_PROMPT_VERSION_UNAVAILABLE` + trace 留底 |
| Replay 自身超时 | status=failed + `diff_summary.error="timeout"` |
| LLM/Tool 调用失败 | status=failed + delay_summary.error 字段，maxRetries=1 后失败 |
| 并发冲突（同 source 已有活跃 replay） | 409 `REPLAY_ALREADY_IN_PROGRESS` |

---

## 10. 实施顺序

1. **Stage 1 契约冻结**：`replay_runs` 表迁移 + Alembic + Pydantic 模型
2. **Stage 5 启动前置**：ReplayService 实现（输入快照重建 + diff）
3. **Stage 5 落地**：dev-only 路由 + 开发者页面集成（[developer-trace.md §4 Replay 入口](../ui-spec/developer-trace.md)）
4. **Stage 5 验证**：故障注入测试（mock LLM 超时、tool fixture 缺失、并发请求同 source_run）

---

## 11. 参考依据

| 来源 | 用于本文 § |
|---|---|
| [TDD §12.2 Replay](../../architecture/tdd.md) | §1.1 |
| [trace-tables.md](../data-models/trace-tables.md) | §2.2, §5.2 |
| [prompt-versioning-standard.md §4 版本亲和性](../../standards/prompts/prompt-versioning-standard.md) | §3.1 |
| [check-scripts-spec.md §6 `scripts/replay.sh`](../../governance/check-scripts-spec.md) | §6.1（CLI 入口） |
| Claude Code `/rewind` + checkpoint（Anthropic 2025） | §1.1 设计灵感 |
| LangGraph Checkpointer（Postgres backend） | §3 |
| [run-status.mmd](../state-machines/run-status.mmd) | §3.4 并发约束 |

---

*本 Replay spec 与 [eval-system.md](./eval-system.md)、[harness-overview.md](./harness-overview.md) 共同构成 harness 反馈层 spec 集。*
