# distill_evidence.spec.md — 证据蒸馏节点

状态：本轮实现。

## 0. 节点定位

| 维度 | 内容 |
|---|---|
| 中文名 | 证据蒸馏节点 |
| 类型 | 程序节点（背景调 LLM 二次整理，非 Agent 循环） |
| 工作流位置 | 第 6 步（在 career_planning_agent 之后或被异步触发） |
| 模型 | DeepSeek V4（蒸馏质量优先） |
| 写权限 | ⚠️ 写 `experience_atoms` 表（**例外**：经 Service 事务写入，不经 persist 节点） |

## 1. 输入 Schema

`app.schemas.evidence.DistillRequest`

| 字段 | 类型 | 必填 | 约束 |
|---|---|---|---|
| `run_id` | `str` | ✅ | —— |
| `documents` | `list[SearchSource]` | ✅ | `min_length=1, max_length=10` |
| `goal_type` | `GoalType` | ✅ | 用于 atom.goal_type 索引 |

## 2. 输出 Schema

`app.schemas.evidence.DistillResult`

| 字段 | 类型 | 必填 |
|---|---|---|
| `atoms` | `list[EvidenceAtom]` | ✅，`max_length=5` |
| `conflicts` | `list[str]` | 文档间冲突 |
| `sources_used` | `list[str]` | 实际引用的 URL |

**EvidenceAtom 子 Schema**：
| 字段 | 约束 |
|---|---|
| `title` | `max_length=100` |
| `body` | `max_length=2000` |
| `source_url` | http(s) URL |
| `reliability` | `Field(ge=0, le=1)` |
| `goal_type` | GoalType |

## 3. 不变量

| ID | 不变量 |
|---|---|
| INV-1 | `atoms` 必须有 `source_url`，且 `source_url ∈ documents[].url` |
| INV-2 | `atoms` 不得包含文档外的信息（防 hallucination） |
| INV-3 | 涉及敏感内容的 atom → 标 `sensitivity="sensitive"`，不直接入库 |

## 4. 错误边界

| 错误 | 处理 |
|---|---|
| LLM 返回 atom 数 = 0 | 返回空，trace `fallback_reason="no_evidence"` |
| 文档间严重冲突 | 入 `conflicts`，trace WARNING |
| LLM 超时 (>15s) | 跳过本节点，不阻塞 plan_run 主流程 |

## 5. 状态机

无内部状态机。背景任务，可并行于 career_planning_agent。

## 6. 依赖与副作用

| 依赖 | 用途 |
|---|---|
| LLM Provider (`DeepSeekV4Provider`) | 整理 + 结构化 |
| Prompt `prompts/distill/v1.py` | 蒸馏指导 |
| 写 DB | `services.evidence.save_atoms(atoms)`（经 Service，事务原子化） |
| Tool | ❌ 不调 Tool |

## 7. Trace 字段

| 字段 | 示例 |
|---|---|
| `node_name` | `"distill_evidence"` |
| `input_doc_count` | `5` |
| `output_atom_count` | `3` |
| `conflict_count` | `1` |
| `latency_ms` | `4320` |
| `cost_cny` | `0.0118` |

## 8. 参考实现顺序

1. `schemas/evidence.py`
2. `services/evidence.py` save_atoms 事务
3. `prompts/distill/v1.py`
4. `agent/nodes/distill_evidence.py`
5. `tests/agent/test_distill_evidence.py` 3 case

## 9. 引用

- [TDD §4.3 节点 6](../../architecture/tdd.md)
- [PRD §3.3 知识库](../../overview/product-overview.md) 经验原子沉淀
