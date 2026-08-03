# 当前实现缺口与改进路线

> 评估时间：2026-08-03
> 评估视角：产品经理 / 开发工程师 / 架构师 / Agent 算法四个维度
> 基线：`feat/sdd-docs-migration-ly-dev` 分支（已含 docker 部署、真模型接入、产品 UI、18 个新增测试）
> 评估方法：基于实际代码行号、文档、测试、CI 配置的人工静态审查 + 真模型 E2E 跑通验证

本文件不重复 `docs/review/revision-report.md` 的早期设计稿一致性审查，只记录**当前交付版本的真实缺口**，用于指导后续迭代。

> **更新日志**
> - 2026-08-03 (初版)：9 个 commit 基线评估。
> - 2026-08-03 (增量)：commit `9a9b1c2` / `a382247` 后再次核对前端，**P-3、E-2 已做掉；P-0、E-3 部分缓解；E-6 未动。详见各表格的"最新状态"列**。

---

## 0. 基线状态摘要

| 维度 | 现状 |
|---|---|
| 后端代码 | ~10000 行 Python，101 个 pytest 全绿 |
| 前端代码 | ~3000 行 TypeScript，6 个 vitest 全绿 |
| Agent 链路 | 10 节点 workflow + 单一受控 LLM 节点，真模型 GLM-4.7 已端到端 completed |
| Eval | 30 条固定 dataset + 12 个确定性 grader |
| CI | 每次 push 跑全套（ruff/mypy/pytest/eval/build），但 LLM/Search/Embedding 全程 mock |
| 文档 | 116 个 markdown 文件，覆盖 SRS / TDD / API / 状态机 / Agent 节点 spec |

---

## 1. 产品视角

### 1.1 产品 sense 评估：MVP 形态可跑通，但未经过任何用户检验

**做对的产品决策**：

- 正确的产品克制：锁定"方向 → 计划 → 任务 → 复盘 → 重规划"单一回路，避免功能蔓延
- `safe_response` 分支文案克制（先安抚情绪而非显示警告色），契合"求职焦虑"语境
- Run 终态四态（completed/degraded/failed/cancelled）+ degraded 时仍给保底计划，让用户永远拿到可执行结果
- `memory_candidates` 隐私确认机制：敏感信息需用户显式同意才进长期记忆

### 1.2 产品缺口（按优先级）

| ID | 优先级 | 缺口 | 影响 | 最新状态 (2026-08-03 增量) |
|---|---|---|---|---|
| P-0 | P0 | 无 landing page / 无 demo 入口 / guest 登录是隐藏的 | 无法做用户测试，没人能自然进入产品 | 🟡 部分：新增 `/me`（MyPage）作为个人 dashboard，提供导航枢纽 + 计划数/任务数汇总；但仍非面向新用户的 landing page，guest 登录仍自动触发 |
| P-1 | P0 | `MemoryCandidatesPage` 永远空（`distill_evidence` 未实现） | 用户看到的"记忆"页面永远无数据，强破坏产品承诺 | ❌ 未动 |
| P-2 | P1 | "今天"之外的"未来 N 周"无 sense-making 可视化，`weekly_focus` 只在 Plan 详情里列文本 | 产品退化为 Todo + LLM，体现不出"规划"价值 | ❌ 未动 |
| P-3 | P1 | API error_code 直接打给用户（`PROVIDER_RATE_LIMITED` 等） | 无产品化错误恢复、无重试倒计时 | ✅ **已闭环**：`frontend/src/lib/errors.ts` 把后端 error_code 映射到中文友好提示 + 重试建议，3 个 vitest 守护；各 page 改用 `toUserMessage()` |
| P-4 | P1 | SSE 断线重连 UI 无视觉提示 | 用户无法感知 "重连中…" | ❌ 未动 |
| P-5 | P2 | 无 analytics 埋点 | 无法做漏斗分析、无法 measure iterate | ❌ 未动 |
| P-6 | P2 | `evals/datasets/stage5-v1.jsonl` 30 条固定 case 是开发者测试 | 不是真实用户 case 库，会过拟合 | ❌ 未动 |

### 1.3 流程完善度（PM 视角）

| 阶段 | 状态 |
|---|---|
| 需求 → 设计 → 实现 | ✅ SDD 流程严谨，116 文档可追溯 |
| 单元 + Eval 测试 | ✅ 101 pytest + 30 Eval |
| 真模型 E2E | ⚠️ 本地验证通过，未进 CI |
| 可观测性 | ✅ Trace/Snapshot/Replay 设计完整 |
| 用户验收测试 | ❌ 0 真实用户 |
| 上线 / 运维手册 | ⚠️ compose 能起，无监控、无告警、无 rollout 策略 |
| 数据反馈循环 | ❌ 无埋点、无漏斗 |

---

## 2. 工程视角

### 2.1 实现整齐度评估：MVP 项目里顶级梯队

**做对的工程实践**：

- 9 层分层（api/services/repositories/models/schemas/agent/tools/harness/providers）零循环 import
- 类型严格：后端 `mypy strict` + Pydantic v2，前端 `tsconfig strict + noUncheckedIndexedAccess`
- 测试断言精确（不是 `assert ok`，而是精确比对 `failed check codes`）
- 错误契约统一：`AppError(code, message, status_code)` + `register_exception_handlers`
- 配置在启动时校验，拒绝静默回退 mock

### 2.2 工程层缺口（nit 级，不影响交付，影响长期维护）

| ID | 优先级 | 缺口 | 建议 | 最新状态 (2026-08-03 增量) |
|---|---|---|---|---|
| E-0 | P1 | `agent/graph.py` 709 行，单类塞了拓扑构造 + 10 节点回调 + 候选生成 + repair 全部逻辑 | 拆到 `agent/nodes/` 子模块（设计 §15 自己建议过但未落地）| ❌ 未动 |
| E-1 | P1 | `MockPlanningProvider` 里 `generate_plan` / `generate_agent_turn` 含大段 copy-paste | 抽 `_descent_candidate()` 公共方法 | ❌ 未动 |
| E-2 | P2 | 中文 label 表（`STATUS_LABEL`）散落 4+ 处页面重复 | 提到 `frontend/src/lib/labels.ts` | ✅ **已闭环**：`frontend/src/lib/labels.ts`（47 行）集中了 STATUS / TASK_TYPE / ABANDONED_REASON 等映射，TodayPage / PlanDetailPage / PlansPage / TaskCard 已切换引用 |
| E-3 | P2 | `HomePage.tsx` 当前 router 没人路由到它（已切到 PlansPage），但 `HomePage.test.tsx` 还在测它 | 删除或接回路由 | 🟡 部分：MyPage 接管了"首页 dashboard"角色，HomePage 在 router 里仍无用，但其测试仍跑——仍待清理 |
| E-4 | P2 | 测试基础设施 `runtime_factory` / savepoint 模式在 conftest 和 runtime 测试里重复 | DRY，提 shared fixture | ❌ 未动 |
| E-5 | P2 | OpenAPI snapshot 是手维护，schema 改时无 PR 模板提醒同步 | 加 PR checklist 或 CI 自动 diff | ❌ 未动 |
| E-6 | P3 | 前端 `TodayPage` 240 行手写 5 种 Run 状态条件渲染 | 抽 `useRunLifecycle` hook | ❌ 未动（ThisPage 改用 lib/errors 后略瘦，但仍 200+ 行，未抽 hook） |

---

## 3. 架构视角

### 3.1 架构合理性：主干优秀

**做对的核心架构决策**：

1. **确定性骨架 + 受控 LLM**：这是 production Agent 的正确形态。每步可解释、可回放、可降级
2. **不可变快照支持 Replay**：`RunInputSnapshot + RuntimeConfigSnapshot` 在 Run 启动时冻结；Eval 离线结果可信
3. **事件溯源**：`agent_events.next_event_sequence` 用 `UPDATE … SET seq = seq + 1 RETURNING` 原子递增殖；terminal event 永远同事务最后写
4. **预算管理防御纵深**：`BudgetGuard` 同时管 LLM 调用次数 + Token + deadline + CancellationToken，每节点 `run()` 前检查
5. **Provider Protocol 而非继承**：新增厂商改一个 `base_url` 即可
6. **状态机正确**：Run/Plan/Task 三种状态机在代码与 `docs/model-design/state-machines/*.mmd` 一致

### 3.2 架构缺口（结构性技术债）

| ID | 优先级 | 缺口 | 影响 |
|---|---|---|---|
| A-0 | **P0** | **"幽灵节点"**：spec 的 `agent-nodes/quality_reviewer.spec.md` 和 `distill_evidence.spec.md` 在代码里完全不存在（无节点、无服务）。revision-report 里说"Stage 5 默认离线 shadow"，实际从未实现。文档与实现产生了"声称已闭环、其实未接"的偏差 | 这是 SDD 项目最该避免的诚实问题。要么 spec 标"Stage 6 未交付"，要么补 EvidenceService |
| A-1 | P0 | 单 Worker 是纸面约束。代码里有多个不能多副本运行的埋点：SSE 用 0.05s 轮询 DB（多用户连接池打满）；`recover_interrupted` lifespan 启动跑，多副本会抢救同一批 Run；乐观锁 `version+1` 未处理并发冲突报错 | 上多副本即翻车 |
| A-2 | P1 | `ToolRegistry._reuse` 用 `tool_name + args_hash` 去重，但 args_hash 不含 Tool 内部状态（如 memory 表已更新）。Review → replan 场景下可能返回过期 evidence | ABA 隐患 |
| A-3 | P1 | `BudgetGuard.record_llm_call` 用 `tokens_in + tokens_out > max_total_tokens`，但 reasoning models 的 `reasoning_tokens` 不在 `completion_tokens` 里。`_apply_thinking_disabled` 是治标，模型关不掉 reasoning 时预算账全是错的 | ProviderUsage 应显式收 `reasoning_tokens` |
| A-4 | P1 | Replay ≠ 真复现：`tool_calls` 表里 evidence 是历史 fixture，真模型 replay 时只读旧 fixture，不重新调 Tool。设计文档没显式承认这个落差 | 运维误以为 replay = 真复现 |
| A-5 | P2 | `api/auth.py`（新增 `/me`）跨了 3 个 service（PlanQueryService / AgentRunService / ReviewRepository） | 应有 `MeAggregateService` 集中 |
| A-6 | P2 | 前端缺状态层抽象，每个 page 各自 `useQuery + useState` 处理 Run 状态。`TodayPage` 手写 clarification/plan/safe_response/failed/cancelled 5 种条件渲染 | 应有 `useRunLifecycle` hook |
| A-7 | P3 | `finalizer.py:69` 直接从 `run.config_snapshot_json["provider"]` 读字段（JSON 字段名硬编码） | schema 漂移不会 compile error |

---

## 4. Agent 算法视角

### 4.1 当前形态：**规则-Bounded LLM Workflow**（非真 Agentic）

按 Anthropic "Building effective agents" 分类：

- ✅ Workflow（路径代码写死 + LLM 在固定节点做局部决策）
- ❌ Agent（LLM 自己决定下一步走哪、何时停）

这是 production Agent 的**正确选择**——但代价是算法面被规则框死，留给算法优化的空间有限。

### 4.2 7 层 Agent 全路径 vs 当前实现

```
[L1 输入] 意图识别 + 槽位填充 + query rewriting + 安全过滤
   ↓
[L2 上下文] Profile + History + Memory(RAG) + Tool selection
   ↓
[L3 推理] Plan-and-Execute / ReAct / 单次 generation
   ↓
[L4 验证] Schema validation + Business rules + Safety check
   ↓
[L5 修复] Format repair + Business repair + Self-reflection
   ↓
[L6 输出] Companion message + Evidence citation + Persistence
   ↓
[L7 反馈] User feedback → Memory → Next generation
```

| 层 | 当前状态 | 成熟度 |
|---|---|---|
| L1 输入 | 关键词 `route_intent` + `risk_gate` | ⭐⭐ 规则级，缺 LLM fallback |
| L2 上下文 | `_build_context` 时间倒序堆叠 30 task + 7 review，token 无关性筛选 | ⭐⭐ 堆叠式，无 embedding 检索 |
| L3 推理 | 单次 generation（temperature=0.1）+ 受控 Tool loop（最多 2 轮）| ⭐⭐⭐ 受控 LLM |
| L4 验证 | 13 条 boolean 硬规则 | ⭐⭐⭐ 完整但二值化 |
| L5 修复 | Format repair 1 次 + Business repair 1 次 | ⭐⭐⭐⭐ 完整且分层 |
| L6 输出 | companion + persist + events 全做对 | ⭐⭐⭐⭐ |
| L7 反馈 | 完全缺失 | ⭐ |

### 4.3 算法层缺口（按影响排序）

| ID | 优先级 | 缺口 | 算法现状 | 成熟方案 | 改进成本 |
|---|---|---|---|---|---|
| AG-0 | **P0** | **Memory embedding 完全没接通**。`memories.embedding Vector(1024)` + HNSW 索引迁移已建（`20260731_0006`），但 `EvidenceRepository.pinned_memories()` 是按时间倒序的纯 SQL，从没用过向量检索 | 时间倒序堆叠 | pgvector cosine retrieve top-K + 时间衰减 + 相关性加权 | **半天** |
| AG-1 | **P0** | **Prompt 工程深度不足**。`career_planning.py` 111 行 system prompt 无 few-shot、无思考模板、无 reasoning 引导。30 条 Eval case 数据有，可以挑 3 条好例子塞 prompt | 单段硬指令 | Few-shot examples + 思考模板（先复述约束→列候选→选今日任务→输出 JSON）+ 动态注入失败 check_codes | **1 小时** |
| AG-2 | P1 | validator 是 13 条 boolean 强约束，把连续语义强制二值化。超 1 分钟和超 30 分钟都是 same fail | boolean check | soft scoring（severity 0-1 + delta 偏差量）；stricter threshold 对硬失败，soft pass 对边界微差 | 2 天 |
| AG-3 | P1 | `route_intent` 是脆弱关键词匹配（"查看计划"/"调整"等）。设计文档允许了 LLM intent router fallback（"规则无法确定时调用 1 次 model"），代码完全没实现这一路 | 关键词 any-in | 规则高置信命中走规则；不确定时调小模型分类器输出 IntentResult | 半天 |
| AG-4 | P1 | 候选生成是单次 greedy（temp=0.1）。一次 unlucky 就只能走 business_repair → fallback | 单次 greedy | first-attempt 失败时触发 Best-of-3（temp=0.7 × 3 并发，scoring 选最优），成本可控 | 1 天 |
| AG-5 | P1 | 修复策略是"全量重写"prompt。LLM 不知道具体修哪里，会重写整个 plan | 全量重写 | Self-Reflection / Targeted Rewrite（先让 LLM diagnose 错在哪，再 targeted patch） | 半天 |
| AG-6 | P2 | 无 LLM-as-judge Eval。12 个 grader 全是确定性 boolean，测不出"plan 合理吗"这类主观质量 | 30 条固定 dataset + 12 boolean grader | 加 LLM-as-judge grader（让强模型给 plan 打分 1-5），weekly 跑真模型 Eval | 1 天 |
| AG-7 | P3 | 反馈循环完全 cold start。无 `distill_evidence` / `quality_reviewer` 服务实现 | 无 | Review 后异步把 blockers + adjustment_request 写入下次 plan context；失败 task 写记忆候选 | 半天 |

### 4.4 优先级建议

按投入产出比（ROI）排序：

| 优先级 | 改进 | 预期效果 | 实施成本 |
|---|---|---|---|
| **P0** | AG-0 接通 pgvector memory 检索 | 上下文相关性 +50%；首次接通已有基础设施 | 半天 |
| **P0** | AG-1 prompt 加 few-shot + 思考模板 | 通过率 +20%；能力立刻提升 | 1 小时 |
| **P0** | A-0 给 `quality_reviewer` / `distill_evidence` spec 加 `Status: Stage 6 (Not Implemented)` | 架构诚实度提升 | 5 分钟 |
| **P1** | AG-2 validator boolean → scoring | 减少 50% 不必要修复；reviewer 量化指标 | 2 天 |
| **P1** | AG-3 意图路由加 LLM fallback | 解决"查看计划"误判类问题 | 半天 |
| **P1** | A-3 ProviderUsage 显式收 reasoning_tokens，预算计算修正 | 真预算准确 | 半天 |
| **P1** | A-1 文档补"单 Worker 假设"列出不能多副本的代码点 | 运维清晰 | 1 小时 |
| **P2** | AG-4 Best-of-N decoding（仅 first-attempt 失败时触发） | fallback 率 -50% | 1 天 |
| **P2** | AG-5 Targeted Repair（先 diagnose 再 patch） | 修复成功率 +30% | 半天 |
| **P2** | AG-6 LLM-as-judge + weekly 真模型回归 CI | 测出"plan 合理吗" | 1 天 |
| **P3** | AG-7 Feedback Loop（minimal: review → 下次 plan context） | 用户感受"系统懂我" | 半天 |

---

## 5. CI / 测试视角

### 5.1 当前 CI 形态

`.github/workflows/ci.yml` 每次 push 跑：ruff → mypy → alembic upgrade → pytest → offline eval → frontend build。所有步骤钉死 `LLM_PROVIDER=mock`。

**含义**：CI 验证的是"代码 vs 设计"的自洽性，**验不了"代码 vs 真实世界"**。本次 PR 修的 3 个 bug（horizon parser 漏「两」、validator SCHEDULE_DATE 错耦合、plan-path 短路）都是 CI 全绿但真模型全崩。

### 5.2 CI/测试缺口

| ID | 优先级 | 缺口 | 建议 |
|---|---|---|---|
| CI-0 | P1 | 无真模型回归。GLM 升级输出结构变了 → 项目静默 degraded，用户报错才知道 | 加 `weekly-real-llm.yml`（每周定时，secrets 存 LLM key，跑真模型 30 条 Eval）成本几毛/周 |
| CI-1 | P2 | snapshot 是手维护，schema 没动也偶尔漂移 | CI 加 `--snapshot-diff` 自动 fail |
| CI-2 | P3 | 无 coverage 阈值 | 加 pytest-cov + 子模块 thresholds |

---

## 6. 安全与运维视角（次要但需记录）

| ID | 优先级 | 缺口 |
|---|---|---|
| SEC-0 | P1 | `.env` 当前含真实 GLM API key（已 gitignore 不会进 git，但 key 暴露在开发环境） |
| SEC-1 | P2 | `risk_gate` 只识别自杀类关键词，无 sexual / violence / PII 检查 |
| SEC-2 | P2 | SSE token 走 query 参数（`?access_token=`），日志/代理可能记录 URL |
| OPS-0 | P1 | 无监控（Prometheus/exporter / OpenTelemetry） |
| OPS-1 | P2 | 无 graceful drain（kill 进程时丢活跃 Run） |
| OPS-2 | P2 | 无 DB 备份策略 |

---

## 7. 综合判断

### 一句话

**这是一个"工程完美但产品未成型、文档领先代码、算法骨架对但深度欠"的高质量 MVP。**

- 作为代码仓库，它打败 90% 同类开源 Agent 项目
- 作为产品，它还停留在 demo 阶段，0 真实用户
- 作为架构，它画饼比吃饼厉害（spec 12 节点只接 10 个）
- 作为 Agent 算法，它是规则-Bounded LLM Workflow（生产正确选择），但上下文/记忆/验证/修复四面都还有明显的算法优化空间

### 推荐的下一步（按时间窗口）

**1 周内**（快速提升算法面 + 架构诚实度）：
1. AG-0 接通 pgvector memory 检索（半天）
2. AG-1 prompt 加 few-shot（1 小时）
3. A-0 spec 标 Stage 6 未交付（5 分钟）
4. CI-0 加 weekly 真模型回归（半天）
5. E-3 删除 HomePage dead code + 测试（5 分钟）

**2-4 周**（产品化）：
6. P-0 真正的 landing page + demo 入口（MyPage 已是 dashboard，但缺面向新用户的入口）
7. P-1 接通 distill_evidence 让 MemoryCandidates 有数据
8. AG-3 意图路由 LLM fallback
9. AG-6 LLM-as-judge Eval

**1-3 个月**（品质化）：
10. AG-2 validator 改 scoring
11. AG-4 Best-of-N decoding
12. AG-5 Targeted Repair
13. 多副本 / 监控 / 备份

> **已完成（2026-08-03 增量）**
> - ✅ P-3：API error_code → 中文友好提示（`lib/errors.ts`）
> - ✅ E-2：中文 label 集中（`lib/labels.ts`）
> - 🟡 P-0 部分：MyPage 接管 dashboard 角色
> - 🟡 E-3 部分：MyPage 接管后再清理 HomePage 即可闭环
