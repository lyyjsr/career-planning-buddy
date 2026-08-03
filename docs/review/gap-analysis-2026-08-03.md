# Gap Analysis 与严肃升级路线（严肃版本）

> 评估时间：2026-08-03（含 2026-08-03 增量更新）
> 视角：开发工程师 / 架构师 / **Agent 算法工程师**
> 基线：分支 `feat/sdd-docs-migration-ly-dev`，HEAD `128d35e`：含 docker 部署修复、真模型 GLM-4.7 接入、产品 UI（Today/Plan/Reviews/Memories/MyPage/ProfileSettings）、18 个新增单测、配置/CI 修补
> 评估方法：基于实际代码行号 + 人工静态审查 + 真模型 E2E + 调研论文/成熟项目对照

本文件**不是工程自查 todo 清单**（保留原 gap-analysis 体例），而是严肃的算法/工程升级路线图：每条缺口都对照成熟项目或论文，方案描述可执行（给函数签名/参数/算法步骤），并标了**面向"Agent 研发工程师/算法工程师"岗位作品集**时的展示价值。文档目的是让"做出 MVP 后想再上一个台阶"的迭代可被规划、可被验证、可对外沉淀。

> **更新日志**
> - 2026-08-03 初版：9 commit 4 视角 gap analysis。
> - 2026-08-03 增量：commit `9a9b1c2` / `a382247` 后再核对前端，P-3 / E-2 闭环，P-0 / E-3 部分缓解。
> - **2026-08-03 严肃版（本版）**：整体重写，加入论文引用 + 代码级方案 + 作品集维度。

---

## 0. 基线事实（不写字眼，写证据）

| 维度 | 证据 |
|---|---|
| 后端规模 | 79 个 Python 文件（含 tests/evals），101 个 pytest pass，5 秒内完成 |
| 前端规模 | 12 个业务页面/组件 + 9 个 shadcn 组件 + 7 个 API 模块 + 9 vitest pass |
| Agent 形态 | workflow（10 节点 + 条件边）+ 单一 LLM-生成节点（`app/agent/graph.py` 共 709 行）|
| 向量检索基础设施 | pgvector 迁移（`20260731_0006`）建表 + HNSW 索引；`EvidenceRepository.memory_lookup` **已支持** cosine_distance 查 memory，但 `_build_context` 主链路未调用 → 板凳深度充足（详见 §3） |
| 几个被网络认作"幻觉"的 spec | `quality_reviewer.spec.md` / `distill_evidence.spec.md` 在 `app/` 里 **0 行代码**（grep 全空），属"文档领先代码" |
| 真模型验证 | GLM-4.7 端到端 completed（~15s），但 CI 仍全程 mock |

---

## 1. 产品 / PM 视角（保留原 gap-analysis 主体）

### 1.1 做对的产品决策（已验证）

- 单回路克制："方向 → 计划 → 任务 → 复盘 → 重规划"，没有功能蔓延
- Run 状态四态（completed/degraded/failed/cancelled）+ degraded 时 deterministic fallback，让用户永远拿到可执行结果
- `safe_response` 安抚文案 + calming 色板，契合"求职焦虑"语境
- `memory_candidates` 隐私确认机制：敏感信息需用户显式同意才进 long-term memory

### 1.2 产品缺口（按优先级 + 状态滚动更新）

| ID | 优先级 | 缺口 | 影响 | 最新状态 |
|---|---|---|---|---|
| P-0 | P0 | 无面向新用户的 landing page / demo 入口 / guest 自动登录 | 无法做用户测试 | 🟡 部分：`/me`（MyPage）已承担 dashboard；仍非新用户入口 |
| P-1 | P0 | `MemoryCandidatesPage` 永远空（`distill_evidence` 未实现） | 用户"记忆"页无数据 | ❌ 未动 |
| P-2 | P1 | "未来 N 周"无 sense-making 可视化，`weekly_focus` 只在 Plan 详情里列文本 | 退化为 Todo + LLM | ❌ 未动 |
| P-3 | P1 | API error_code 直接打给用户 | 无产品化错误恢复 | ✅ 已闭环：`frontend/src/lib/errors.ts` 58 行 + 3 vitest |
| P-4 | P1 | SSE 断线重连 UI 无视觉提示 | 用户感知不到重连中 | ❌ 未动 |
| P-5 | P2 | 无 analytics 埋点 | 无漏斗分析 | ❌ 未动 |
| P-6 | P2 | 30 条 Eval 是开发者 fixture，会过拟合 | 不是用户 case 库 | ❌ 未动 |

**作品集建议**：在简历/作品页可强调"**单回路 + 四态降级 + safe_response 安抚设计**"——这是大多数 demo 级 Agent 不会考虑的工程意识。

---

## 2. 工程 / Dev 视角

### 2.1 做对的工程实践

- 9 层分层零循环 import；ORM 实体不外泄到 API
- `mypy strict` + Pydantic v2 + TypeScript strict
- `AppError(code, message, status_code) + register_exception_handlers` 统一错误契约
- Settings `model_validator` **拒绝静默回退 mock**——这是 LLM 应用的安全正确姿势（少见的严谨）
- Event Sourcing：`next_event_sequence` 用 `UPDATE … SET seq = seq + 1 RETURNING` 原子递增，terminal event 同事务最后写

### 2.2 工程缺口

| ID | 优先级 | 缺口 | 建议 | 最新状态 |
|---|---|---|---|---|
| E-0 | P1 | `graph.py` 709 行单类塞拓扑 + 节点 + repair | 拆 `agent/nodes/` 子模块 | ❌ 未动 |
| E-1 | P1 | Mock 在 `generate_plan`/`generate_agent_turn` 含 copy-paste | 抽 `_descent_candidate()` | ❌ 未动 |
| E-2 | P2 | 中文 label 表 4+ 处重复 | 提到 `lib/labels.ts` | ✅ 已闭环 |
| E-3 | P2 | `HomePage.tsx` dead code，但 `HomePage.test.tsx` 仍跑 | 删或接回路由 | 🟡 部分：MyPage 已接管 |
| E-4 | P2 | `runtime_factory` / savepoint 模式重复 | shared fixture | ❌ 未动 |
| E-5 | P2 | OpenAPI snapshot 手维护，易 PR 漂移 | CI `--snapshot-diff` | ❌ 未动 |
| E-6 | P3 | `TodayPage` 240 行 5 种 Run 状态条件渲染 | 抽 `useRunLifecycle` hook | ❌ 未动 |

---

## 3. 架构视角

### 3.1 正确的核心架构决策

| 决策 | 评价 / 对照 |
|---|---|
| 确定性骨架 + 受控 LLM（workflow not agent）| ✅ 与 [Anthropic "Building Effective Agents" (2024)](https://www.anthropic.com/research/building-effective-agents) "选择最简单可行方案"原则一致 |
| 不可变快照（`RunInputSnapshot` + `RuntimeConfigSnapshot`）支持 Replay | ✅ Eval 可信根基，类似 LangSmith / Langfuse 的 trace replay |
| 事件溯源 + 原子序号 + terminal-last 事务 | ✅ 可重新构造 Run 历史；与 LangGraph checkpoint 异曲同工 |
| Budget 防御纵深（LLM 调用次数 + Token + deadline + CT）| ✅ production-grade 思路，绝大多数 demo 不做 |
| Provider Protocol | ✅ 切厂商零代码改动（已实测 DeepSeek↔GLM↔Qwen） |

### 3.2 架构缺口（结构性技术债）

| ID | 优先级 | 缺口 | 影响 | 代码级位置 |
|---|---|---|---|---|
| **A-0** | **P0** | **幽灵 spec 节点** `quality_reviewer.spec.md` / `distill_evidence.spec.md` 在代码里完全不存在 | 严重诚实问题：spec 声称闭环，git grep 0 行实现 | `docs/model-design/agent-nodes/*.spec.md` 对比 `app/agent/graph.py` 节点列表 |
| A-1 | P0 | 单 Worker 假设：SSE 0.05s DB 轮询；`recover_interrupted` 多副本冲突；乐观锁无并发冲突处理 | 多副本即翻车 | `app/services/agent_runs.py:stream_events` |
| A-2 | P1 | `ToolRegistry._reuse` 用 `tool_name + args_hash` 去重，不含 Tool 内部状态（如 memory 已更新）| Review→replan 时返回过期 evidence（ABA 隐患） | `app/tools/registry.py:_reuse` |
| A-3 | P1 | `BudgetGuard.record_llm_call` 用 `tokens_in + tokens_out`，但 reasoning_tokens 不在 completion_tokens 里 | GLM/DeepSeek 关不掉 reasoning 时账错 | `app/harness/budget.py` + `providers/llm.py:_extract_usage` |
| A-4 | P1 | Replay ≠ 真复现：replay 时只读 `tool_calls` 历史 fixture，不重调 Tool | 文档没承认落差 | `evals/runner.py` |
| A-5 | P2 | `api/auth.py:get_me` 跨 3 个 service | 应有 `MeAggregateService` | 我自己引入的债，可清 |
| A-6 | P2 | 前端缺状态层抽象 | `useRunLifecycle` | `TodayPage.tsx:115-180` |

---

## 4. Agent 算法视角（严肃版核心章节）

### 4.1 形态定位：workflow + 单一受控 LLM 节点

按 [Anthropic, 2024] 的分类：本项目属于 **"Evaluator-Optimizer" 工作流**（"LLM 生成，另一组规则做评估与反馈，直到质量满足，否则降级"）。这与中国/海外主流"做事 Agent"（Devin、Manus、Claude Code）不是同一赛道——它们是 [Plan-and-Execute / ReAct] 类真 Agent。选定 workflow 而非 agent 是**正确取舍**：因为本系统**输出 plan 而非执行 action**，可控性 > 自由度。

但形态选对不等于算法层没空间。下面把"7 层 Agent 路径"逐层对照当下 SOTA。

```
[L1 输入] 意图 + 槽位 + 安全过滤
[L2 上下文] Profile + History + Memory(retrieval) + Tool selection
[L3 推理] generation（受控 / 반응 / plan-and-execute / Best-of-N）
[L4 验证] Schema + Business rules + Safety + LLM-judge
[L5 修复] format / business / self-reflection
[L6 输出] companion + persist + events
[L7 反馈] user feedback → Memory → next generation
```

### 4.2 三大算法升级（最高 ROI）

#### **AG-0：Memory Retrieval 接通（已有基础设施）**

**现状实证**：
- ✅ `alembic/versions/20260731_0006_memory_rag.py` 建了 `Memory.embedding Vector(1024)` + HNSW 索引
- ✅ `app/repositories/evidence.py:41` **已实现** `Memory.embedding.cosine_distance(vector)` 查询
- ✅ `memory_lookup` 方法签名完整，自动 fallback 到 ilike 文本搜索
- ❌ `app/agent/graph.py:_build_context` **完全没调** `memory_lookup`，只调 `pinned_memories`（按时间倒序）

**升级方案（直接落地）**：

```python
# app/agent/graph.py 替换 _build_context 中 memories 部分
async def _retrieve_memory(self, user_id, query, context_tokens):
    query_vec = (await self._embedding.embed([query]))[0]
    raw = await self._evidence_repo.memory_lookup(
        user_id=user_id, query=query, vector=query_vec, limit=10
    )
    # 时间衰减 + 相关性加权（MemGPT 思路：recency + relevance）
    now = datetime.utcnow()
    scored = [
        (m, s * 0.7 + self._recency(m.last_used_at, now) * 0.3)
        for m, s in raw
    ]
    scored.sort(key=lambda x: -x[1])
    # Token 预算感知（lost-in-the-middle 防护）
    out, used = [], 0
    for m, s in scored:
        cost = len(m.summary) // 2
        if used + cost > context_tokens: break
        out.append(m); used += cost
    return out
```

**对照**：MemGPT/Letta 的 [archival memory + recall memory 分层](https://docs.letta.com/)（context compaction）；本项目天然分 Context(end=本对话) / Memories(archival) / Experience atoms(External KB) 三层。

**Recency 函数**：指数衰减 `exp(-Δdays / 14)`——14 天半衰期符合"求职场景用户记忆"。

**作品集建议**：展示"time-decayed + relevance-scored retrieval with token budget awareness"——这是 [Anthropic Contextual Retrieval (2024)](https://www.anthropic.com/news/contextual-retrieval) 落地在自己项目的样子。

#### **AG-1：Prompt 工程深度升级**

**现状实证**：
- `app/prompts/career_planning.py` 共 111 行 system prompt
- 0 个 few-shot example，0 个思考模板
- 30 条 Eval case 数据有（`evals/datasets/stage5-v1.jsonl`）

**升级方案（Chain-of-Thought + Few-Shot + 失败感知）**：

```python
SYSTEM_PROMPT_V2 = """你是求职规划引擎。严格按以下步骤推理：

<step_1>用户约束复述</step_1>
- horizon: {N 周}
- time_budget: {X 分钟/日}
- goal_type: {Y}
- 已完成事实: ...

<step_2>列出 3 个候选任务（不要输出 JSON，只思考）</step_2>

<step_3>从候选中选 1~3 个适合"今天"的任务（思考过程）</step_3>

<step_4>输出 JSON</step_4>

参考样例（few-shot）：
{successful_case_from_eval_pool}

上次你失败的规则：{failed_check_codes}（请在生成时主动规避）
"""
```

**对照**：
- [Wei et al. "Chain-of-Thought", 2022](https://arxiv.org/abs/2201.11903)：两步推理比直出 JSON 显著提升结构化输出准确率
- [Self-Consistency (Wang et al. 2022)](https://arxiv.org/abs/2203.11171)：多次采样取多数；本项目可用 `temperature=0.4` × 3 投票
- [Anthropic Prompt Engineering Guide](https://docs.anthropic.com/)：`<step>` XML 标签引导对 Claude/GLM/Sonnet 类模型有效

**实现成本**：1 小时。优先选 3 条热评测集案例（1 happy + 1 复杂 + 1 边界），动态注入 `successful_case_from_eval_pool`。

#### **AG-2：Validator Boolean → Soft Scoring**

**现状**：13 条硬规则全 boolean，超 1 分钟和超 30 分钟都是 same fail → 触发同一 repair prompt。

**升级方案**：

```python
@dataclass
class ValidationScore:
    code: str
    severity: float   # 0.0 = 完全合规, 1.0 = 严重违反
    delta: float      # 偏差量

def score_time_budget(candidate, ctx) -> ValidationScore:
    overage = sum(t.estimated_minutes for t in candidate.tasks) - ctx.time_budget_minutes
    return ValidationScore(
        code="TIME_BUDGET",
        severity=clamp(overage / 30, 0, 1),  # 超 30 分钟才视为 1.0
        delta=overage,
    )

def aggregate(scores) -> tuple[bool, str | None]:
    hard_fails = [s for s in scores if s.code in {"HORIZON_MATCH", "SOURCE_INTEGRITY"} and s.severity >= 1.0]
    if hard_fails: return False, hard_fails[0].code
    soft_sum = sum(s.severity for s in scores)
    if soft_sum > THRESHOLD: return False, "soft"
    return True, None
```

**对照**：
- [Constitutional AI (Anthropic 2022)](https://arxiv.org/abs/2212.08073)：用一组带权原则打分而非硬约束
- [Self-Refine (Madaan et al. 2023)](https://arxiv.org/abs/2303.17651)：反馈从"错/对"改为"具体维度的具体分数"能让 refinement 更针对

**实现成本**：2 天。先把 13 条全 → 打分型，再加 threshold + soft-pass 路径（>50% severity 才 fail，否则放走）。

### 4.3 其余算法缺口（按 ROI 排序）

| ID | 优先级 | 缺口 | 现状 | 升级算法 + 对照 | 成本 |
|---|---|---|---|---|---|
| **AG-3** | P1 | `route_intent` 关键词匹配（"查看计划"误判） | `if any(term in message)` | LLM fallback 分类器（规则高置信 → 规则；不确定 → 1 次小模型调用输出 `IntentResult`）。对照 [Anthropic "Routing" workflow pattern](https://www.anthropic.com/research/building-effective-agents)；参考 [BERT-based Slot Tagging 2016] 但用 LLM 更省 | 半天 |
| **AG-4** | P2 | 候选生成是单次 greedy | `temperature=0.1` × 1 | Best-of-N + scoring：仅当首次失败触发 N=3 × temperature=0.7 并发，validator 选最优。对照 [WebGPT (Nakano et al. 2021)](https://arxiv.org/abs/2112.09332) 的 best-of-N with reward model | 1 天 |
| **AG-5** | P2 | repair 是"全量重写"prompt | "请修 TIME_BUDGET" | Self-Reflection：先让 LLM diagnose 错在哪（`<diagnosis>`），再 targeted patch。对照 [Reflexion (Shinn et al. 2023)](https://arxiv.org/abs/2303.11366) 的 Actor/Evaluator/Self-Reflection 三模块；本项目 Validator 已是 Evaluator，补 Self-Reflection 即可 | 半天 |
| **AG-6** | P2 | 无 LLM-as-judge Eval | 12 个 boolean grader | 加 `judge_plan_quality` grader（让 GLM 输出 `{"score": 1-5, "dimensions": {...}}`）；weekly 跑真模型回归。对照 [MT-Bench (Zheng et al. 2023)](https://arxiv.org/abs/2306.05685) LLM-as-judge + [τ-bench (Sierra 2024)](https://arxiv.org/abs/2406.12045) agent eval 范式 | 1 天 |
| **AG-7** | P3 | 反馈循环完全 cold start | 无 distill_evidence | 最小版：review 的 `blockers/adjustment_request` 写入下次 plan context；abandoned task 写 memory_candidate；对照 Reflexion 的 episodic memory buffer | 半天 |
| **AG-8** | P3 | Tool 去重 ABA 隐患 | args_hash 不含 memory 状态 | 去重 key 加入 `memory_version_snapshot` 或 TTL（5 分钟内同 args 才复用） | 2 小时 |

---

## 5. RAG / 检索视角（独立章节）

项目已用 pgvector 但只走到"板凳深度"，离 production RAG 还差三层：

| 层 | 现状 | SOTA 实践 | 论文/工具 |
|---|---|---|---|
| **Query Rewriting** | 直接 embed 用户原文 | HyDE（假设性文档）/ step-back prompting | [HyDE (Gao et al. 2022)](https://arxiv.org/abs/2212.10496) |
| **Retrieval** | 仅 vector cosine | Hybrid: BM25 + vector；re-rank | [Cohere Rerank / bge-reranker](https://github.com/FlagOpen/FlagEmbedding) |
| **Context Placement** | 不感知 lost-in-the-middle | 把 evidence 放开头/结尾，中间放次要 | [Liu et al. 2023, Lost in the Middle](https://arxiv.org/abs/2307.03172) |
| **Chunking** | 整段 context 拼接 | sentence-window + parent-doc retriever | [LlamaIndex chunking strategies](https://docs.llamaindex.ai/) |

**最高 ROI**：AG-0 接通 cosine + 加 lost-in-the-middle 排序（半天完成）。HyDE / Hybrid Search 列为 Stage 6+ 优化。

---

## 6. Eval 视角（严肃版）

### 6.1 当前 Eval 评估：**L1+L2 级，缺 L3-L5**

```python
# 当前 evals/graders/ 全是 boolean
def grader_format_json(...) -> bool
def grader_rule_validation(...) -> bool
# ... 12 个类似
```

成熟 Agent Eval 5 层（参考 [HELM (Liang et al.)] + [SWE-bench (Jimenez et al. 2023)](https://arxiv.org/abs/2310.06770)）：

| 层 | 当前 | 升级 | 对照 |
|---|---|---|---|
| L1 单元 | ✅ 95 pytest | — | — |
| L2 Trace replay | ✅ 30 条 stage5-v1 | 扩到 100+ 条 + 自动入仓 | SWE-bench 流程 |
| **L3 LLM-as-judge** | ❌ | `judge_plan_quality` 输出 1-5 + 维度 | [MT-Bench (Zheng et al. 2023)](https://arxiv.org/abs/2306.05685) |
| **L4 真模型回归** | ❌ | weekly 真模型 CI workflow | Anthropic evals 仓库 |
| **L5 Human eval** | ❌ | 用户标注 plan 合理度 | — |

### 6.2 LLM-as-judge grader 落地

```python
# evals/graders/judge_plan_quality.py
async def judge_plan_quality(plan, context) -> dict:
    prompt = f"""你是求职规划专家。给以下 plan 评分（1-5）：
    {plan.json}
    用户上下文：{context.json}
    
    评估维度：
    - actionability: 任务是否具体可执行（1-5）
    - alignment: 与目标的相关性（1-5）
    - budget_fit: 时间预算合理性（1-5）
    
    返回 {{"score": float, "dimensions": {{...}}, "reasoning": str}}
    """
    return await llm.judge(prompt)
```

### 6.3 周度真模型回归 CI

```yaml
# .github/workflows/weekly-real-llm.yml
name: Weekly Real-LLM Regression
on:
  schedule: [{cron: "0 3 * * 1"}]
  workflow_dispatch: {}
jobs:
  real-llm-eval:
    env:
      LLM_PROVIDER: openai_compatible
      LLM_API_KEY: ${{ secrets.LLM_API_KEY }}
      LLM_MODEL: glm-4.7
    steps:
      - run: python -m scripts.run_eval --persist
      - uses: actions/upload-artifact@v4
        with: {name: eval-report}
```

**作品集建议**：这套 L3+L4+L5 是绝大多数 Agent demo 缺位的，问面试官"你们项目如何做 quality regression"时拿这个回答非常有分量。

---

## 7. CI / 安全 / 运维

| ID | 优先级 | 缺口 | 建议 |
|---|---|---|---|
| CI-0 | P1 | mock-only CI，真模型回归缺位 | weekly-real-llm.yml（成本几毛/周，§6.3） |
| CI-1 | P2 | OpenAPI snapshot 手维护 | CI 加 `--snapshot-diff` |
| CI-2 | P3 | 无 coverage 阈值 | pytest-cov + 子模块 thresholds |
| SEC-0 | P0 | `.env` 含真实 GLM key（已 gitignore） | **轮换 key** |
| SEC-1 | P2 | risk_gate 只识别自杀关键词 | 加 sexual/violence/PII；接 Anthropic / Azure content safety |
| SEC-2 | P2 | SSE token 走 query 参数 | 短期 token（5 分钟）+ refresh |
| OPS-0 | P1 | 无监控（OTel / Prometheus） | OTel SDK + trace/span 导出 |
| OPS-1 | P2 | 无 graceful drain | SIGTERM handler + active run 抢救 |
| OPS-2 | P2 | 无 DB 备份策略 | pg_dump cron 或云 RDS |

---

## 8. 综合判断

### 形态定位

本项目是 [Anthropic Evaluator-Optimizer workflow](https://www.anthropic.com/research/building-effective-agents) 的工程化范例：**LLM 在固定节点生成 → 13 条规则 + repair → 否则降级**。不追求 Agentic 自由度，换取了可解释、可回放、可降级——这是 production 的正确选择。

### 三层定位

| 层 | 评价 |
|---|---|
| 工程 | 顶级 MVP 梯队：分层、类型、契约、测试、降级，打败 90% 开源 Agent demo |
| 产品 | 停留在 demo 阶段，0 真实用户；memory_candidates 永远空是强破坏 |
| 算法 | 骨架对、深度浅：向量检索基础设施齐了没接通，prompt 0 个 few-shot，validator 全 boolean，无 LLM-as-judge，无反馈闭环 |

### 对标样本

| 维度 | 本项目 | 成熟参考 | 差距 |
|---|---|---|---|
| Agent 形态 | workflow + 1 LLM 节点 | LangGraph / Anthropic patterns | ✅ 同赛道 |
| 记忆检索 | pgvector 建好未接 | MemGPT / Letta 三层记忆 | 🟠 接通即可 |
| 自反思 | 1-pass + 1 repair | Reflexion Actor/Evaluator/Self-Reflection | 🔴 缺 reflection |
| Eval | 12 boolean grader | MT-Bench / τ-bench | 🔴 缺 LLM-as-judge |
| 多副本 | 单 Worker 假设 | LangGraph Cloud / OpenAI Assistants | 🔴 需重构 |

---

## 9. 严肃升级路线（按时间窗口）

### Week 1（立竿见影，作品集级）

| # | 改进 | 论文/对照 | 成本 |
|---|---|---|---|
| 1 | **AG-0** 接通 pgvector memory 检索 + 时间衰减 + token budget | MemGPT + Contextual Retrieval | 半天 |
| 2 | **AG-1** prompt 加 CoT + 3 个 few-shot + 失败规则注入 | Wei 2022 + Self-Consistency | 1 小时 |
| 3 | **A-0** 给 `quality_reviewer` / `distill_evidence` spec 标 Stage 6 未交付 | — | 5 分钟 |
| 4 | **CI-0** weekly 真模型回归 workflow | Anthropic evals 实践 | 半天 |
| 5 | **AG-3** route_intent 加 LLM fallback | Anthropic Routing pattern | 半天 |

**Week 1 完成后**：作品集可写"**生产级 Agent with MemGPT-style retrieval + CoT prompting + 真模型回归 CI**"——这是绝大多数贴着 LangChain 教程做的项目到不了的层次。

### Week 2-4（产品化 + Eval 升级）

| # | 改进 | 论文/对照 |
|---|---|---|
| 6 | P-1 接通 EvidenceService / distill_evidence，候选不再空 | Reflexion episodic memory |
| 7 | AG-2 validator 改 soft scoring + soft pass | Constitutional AI / Self-Refine |
| 8 | AG-5 repair 改 Self-Reflection（diagnose + targeted patch）| Reflexion 三模块 |
| 9 | AG-6 加 LLM-as-judge grader + 周度真模型回归 | MT-Bench, τ-bench |
| 10 | P-0 + E-3 真正 landing page + 删 HomePage dead code | — |

### Month 2-3（品质化 / 多副本）

| # | 改进 | 论文/对照 |
|---|---|---|
| 11 | AG-4 Best-of-N decoding（仅 first-attempt 失败触发）| WebGPT reward model |
| 12 | A-1 多副本：Redis pub/sub 取代 SSE 轮询 + 分布式 Recover Lock | LangGraph Cloud architecture |
| 13 | RAG 升级：HyDE + Hybrid Search (BM25+vector) + Reranker | HyDE (Gao 2022), bge-reranker |
| 14 | 监控：OpenTelemetry trace 导出 + Grafana panel | OTel practice |

---

## 10. 引用 / 参考

### 论文
1. [Wei et al. "Chain-of-Thought Prompting" (2022)](https://arxiv.org/abs/2201.11903) — 两步推理提升结构化输出
2. [Wang et al. "Self-Consistency" (2022)](https://arxiv.org/abs/2203.11171) — 多次采样投票
3. [Madaan et al. "Self-Refine" (2023)](https://arxiv.org/abs/2303.17651) — 维度化反馈驱动 refinement
4. [Shinn et al. "Reflexion" (2023)](https://arxiv.org/abs/2303.11366) — Actor/Evaluator/Self-Reflection + episodic memory buffer；HumanEval 91% pass@1 vs GPT-4 80%
5. [Nakano et al. "WebGPT" (2021)](https://arxiv.org/abs/2112.09332) — Best-of-N with reward model
6. [Bai et al. "Constitutional AI" (Anthropic 2022)](https://arxiv.org/abs/2212.08073) — 原则带权打分
7. [Gao et al. "HyDE" (2022)](https://arxiv.org/abs/2212.10496) — Hypothetical Document Embeddings
8. [Liu et al. "Lost in the Middle" (2023)](https://arxiv.org/abs/2307.03172) — context 位置影响利用率
9. [Zheng et al. "MT-Bench" (2023)](https://arxiv.org/abs/2306.05685) — LLM-as-judge 范式
10. [Sierra et al. "τ-bench" (2024)](https://arxiv.org/abs/2406.12045) — agent tool-use eval
11. [Jimenez et al. "SWE-bench" (2023)](https://arxiv.org/abs/2310.06770) — 真实代码任务 eval
12. [Liang et al. "HELM" (2022)](https://arxiv.org/abs/2211.09110) — holistic LLM eval

### 工程/平台参考
13. [Anthropic. "Building Effective Agents" (2024)](https://www.anthropic.com/research/building-effective-agents) — 五种 workflow pattern + workflow vs agent
14. [Anthropic. "Contextual Retrieval" (2024)](https://www.anthropic.com/news/contextual-retrieval) — 给 chunk 加上下文再 embed
15. [LangGraph 文档](https://docs.langchain.com/) — checkpoint / store / state machine 模式
16. [Letta (MemGPT) 文档](https://docs.letta.com/) — 三层记忆：main context / archival / recall
17. [Berkeley Function Calling Leaderboard (2024)](https://gorilla.cs.berkeley.edu/leaderboard.html) — tool-use 准确率榜单

### 其它（用于制定本路线的背景资料）
- DeepSeek-V3 / GLM-4.7 / Qwen3 technical reports — 国产 reasoning model 行为特征
- pgvector HNSW 参数调优（ef_search / m）— 本项目 Stage 6+ 可挖

---

## 11. 一句话总结

> **这是工程上的 A、产品上的 C+、算法上的 B- 项目。骨架（受控 Agent + 事件溯源 + 不可变快照）是生产级姿势；算法面（记忆检索未接通、prompt 0 few-shot、validator 全 boolean、无 LLM-as-judge）离 production-grade Agent 还有 2-4 周密集迭代的距离。**
>
> **可执行的最佳下一步是 Week 1 的 5 件事**——做完即从"工程自洽"跳到"算法面合格"，并且每一项都能在简历/作品集上单独成条展示。
