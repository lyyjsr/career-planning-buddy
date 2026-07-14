# Dazi 项目 Spec 编写规范

| 项目 | 内容 |
|---|---|
| 文档版本 | v1.0 |
| 日期 | 2026-07-11 |
| 关联文档 | [PRD_v1.0](../design-input/02_产品需求文档PRD_v1.0.md)、[ADR](../design-input/03_架构决策记录ADR.md)、[开发流程指南](../design-input/04_开发流程指南.md) |
| 文档目的 | 定义本项目"给 AI 工具 + 人读的 spec"的编写规范。所有 LLD 分册、Agent 节点设计、API 契约文档必须遵循本规范 |

---

## 0. 一句话原则

> **Spec 描述"是什么"和"约束是什么"，不描述"怎么实现"。一旦你写了 `for` 循环伪代码，spec 就变成了低质量代码。**

Spec 是给 Claude Code / Cursor 的**机器可执行契约**，不是给人评审的小说。AI 工具拿到字段化、约束化、负面边界化的 spec 能直接生成正确代码；拿到 narrative 化的描述只能照抄伪劣实现。

---

## 1. 为什么需要这份规范

### 1.1 Spec 在本项目中的双重读者

| 读者 | 它从 spec 中提取什么 |
|---|---|
| **AI 代码生成工具** | 字段类型、不变量、状态机、错误边界 → 直接生成代码 |
| **人（开发者/面试官）** | 决策依据、约束理由、模块边界 → 理解架构与审查代码 |

**核心矛盾**：人喜欢读故事，AI 喜欢读结构。本规范以 AI 友好为主，人在 ADR 和架构图里讲故事。

### 1.2 不写 spec 会发生什么

| 症状 | 根因 |
|---|---|
| AI 生成的 Python Agent 少了降级路径 | spec 只写了 happy path |
| AI 把"任务状态变更"逻辑散到 5 个 Service 方法 | spec 没写不变量"状态变更必须经 Aggregate Root" |
| 两个开发者对同一接口的理解不一致 | spec 字段用"差不多"、"适当"等模糊词 |
| AI 把诊断节点的搜索逻辑也实现了 | spec 没写负面边界"诊断 Agent 不调用搜索 API" |

---

## 2. Spec 的核心要素（七要素模型）

**每一份功能 spec 必须包含以下七个部分，缺一不可。**

> v1.1 升级：在 v1.0 六要素基础上**新增第 7 要素 Trace 字段**（参 Anthropic ACI 精心设计原则 + [model-design/agent-nodes/](../model-design/agent-nodes/) 范例）。

### 2.1 输入 Schema

定义该模块/节点/API 的**所有入参**，含字段名、类型、必填、约束。

- 用语言无关的类型表达：`string`、`int`、`float`、`bool`、`list<T>`、`struct{...}`、`enum{...}`
- 复杂对象给出字段表
- 必须标注哪些字段是必填、哪些是可选、默认值

**反例**：`message: 用户消息`（无类型、无长度约束）
**正例**：`message: string, max_length=2000, 必填`

### 2.2 输出 Schema（含 Structured Output）

定义该模块/节点/API 的**所有返回值结构**。对于 Agent 节点，这一段就是给 LLM 的 structured output schema。

- 字段表 + 枚举值
- 约束（如 `rewrite_count: int, le=2`、`today_tasks: list<Task>, min_length=1, max_length=3`）

**反例**：`返回规划结果`（无法据此生成代码）
**正例**：
```
{
  intent: enum{plan, follow_up_question, high_risk},
  goal_type: string,
  open_questions: list<string>, max_length=3,
  search_need: bool
}
```

### 2.3 不变量（Invariants）

**这是 spec 的灵魂，AI 无法自己推断，人最容易漏。**

不变量是该模块**永远不能违反的规则**，无论代码怎么实现。AI 生成代码后，这些不变量也会成为单元测试的断言。

格式：编号 + 陈述句，每条只讲一件事。

```
I-1: rewrite_count 不得超过 2
I-2: rewrite_count 达到 2 仍未通过校验时，必须降级为模板计划
I-3: 高风险触发后，不得进入记忆候选
I-4: 敏感记忆未经用户确认前，不得写入长期记忆
```

### 2.4 错误与边界（含降级）

AI 默认只写 happy path。spec 必须显式列出每个可能的失败路径和处理方式。

格式用表格：

| 触发条件 | 系统行为 | 用户可见 |
|---|---|---|
| 搜索 API 超时 | 使用 cached atoms，标注 `degraded=true` | "本次未完成联网检索" |
| LLM 返回不符合 schema | 重试 1 次，仍失败则节点降级 | 模板计划 |
| rewrite_count 达到 2 | 降级模板计划 | 模板计划 + 说明 |

** sentencing 级别分类**：
- **retry**：自动重试 N 次后继续
- **degrade**：降级到 fallback 路径，继续输出
- **fail**：该节点/任务失败，返回错误

### 2.5 状态机（若适用）

涉及状态流转的模块必须画状态机。状态机是业务核心，必须显式，不能靠叙述。

格式：**状态列表 + 流转规则表**，不必画 Mermaid 图（可选）。

状态列表：
```
任务状态: pending | in_progress | completed | abandoned | expired
```

流转规则表：

| 当前状态 | 允许的下一状态 | 触发条件 | 副作用 |
|---|---|---|---|
| pending | in_progress | 用户点击开始 | 记录 started_at |
| in_progress | completed | 用户点击完成 | 记录 completed_at |
| in_progress | abandoned | 用户点击放弃（必须填原因） | 触发复盘引导 |
| pending | expired | 次日 0 点定时任务 | 无 |

**不变量补充**：`I-X: 不允许从 completed 回退到任意状态`

### 2.6 依赖与副作用

列出该模块**会调用哪些外部服务、会读写哪些数据表、会发出哪些事件/消息**。AI 据此生成正确的 import 和事务边界。

| 类型 | 对象 | 读/写 | 说明 |
|---|---|---|---|
| 外部服务 | DeepSeek LLM API | 调用 | 节点推理 |
| 外部服务 | Tavily Search API | 调用 | 仅搜索蒸馏节点 |
| 数据表 | agent_steps | 写 | 每节点生成一条 |
| 数据表 | plans | 写 | 计划生成后写 |
| 消息 | 无 | — | 本项目暂不使用消息队列 |

### 2.7 Trace 字段（Anthropic ACI 精心设计原则）

> v1.1 新增：本要素保证节点可观测、可 Replay、可 Eval。参 [Harness 五层](../architecture/tdd.md)、[model-design/agent-nodes/intent_router.spec.md §7](../model-design/agent-nodes/intent_router.spec.md) 范例。

列出该节点每次执行**必须写哪一行 Trace**——到 `agent_steps` 表（多对一 run；多行 `tool_calls` 仅真 Agent 节点产生）。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| node_name | `str` | ✅ | 固定值（如 `intent_router`） |
| prompt_version | `str` | LLM 节点 ✅ | R-Prompt1 版本化 |
| model | `str` | LLM 节点 ✅ | 实际调用的模型 ID |
| tokens_in / tokens_out | `int` | LLM 节点 ✅ | 用于成本核算 |
| latency_ms / llm_latency_ms | `int` | ✅ / nullable | 节点总耗时 / LLM 调用耗时 |
| cost_cny | `float` | ✅ | 节点单次成本 |
| fallback_reason | `str \| null` | ✅ | 降级时填代号；正常 null（代号见 [api-spec/errors.md §fallback_reason](../model-design/api-spec/errors.md)） |
| success | `bool` | ✅ | false=未产生有效输出 |
| mock_mode | `str \| null` | 测试时 | "happy"/"invalid"/"timeout" |
| trace_data | `jsonb` | 节点专属 | 如 dim_1/dim_2/matched_keywords 等节点特有字段 |

> ⚠️ **不得**入 Trace：完整 prompt 文本、API Key、用户敏感原文。完整 prompt 文本到独立加密的 `trace_artifacts` 表（可选）。

---

## 3. Spec 的写作禁止清单

以下写法在 spec 中**一律禁止**，出现即视为不合格 spec。

| 禁止项 | 为什么 | 修改方向 |
|---|---|---|
| **写实现伪代码**（for 循环、if-else 逻辑流） | spec 退化为低质量代码，AI 只会照抄 | 改为不变量 + 状态机描述 |
| **模糊量词**：差不多、适当、几个、高质量、友好、简单 | AI 无法据此生成、面试官无法据此验收 | 改成精确量：`3-5 个任务`、`≤ 30 字` |
| **把 PRD 原文照搬** | PRD 写"用户希望轻松启动"，AI 不知道生成什么 | 落到 `starter_action: string, max_length=30` |
| **跨模块耦合写进单模块 spec** | AI 会把两个模块的代码搅在一起 | spec 以接口契约为边界，跨模块交互单独一份 |
| **只写 happy path** | AI 生成的代码默认就没有降级和错误处理 | 每个失败路径显式列出 |
| **不写"不做的事"** | AI 会自由发挥，做了你不需要的东西 | 负面边界比正面描述更有价值 |
| **单份 spec 超过 2 屏 / 200 行** | AI 上下文成本高，重点分散 | 拆分模块 |

---

## 4. Spec 的填空模板（标准骨架）

**每个 Agent 节点 / 功能模块的 spec 都按此模板填空。** 不要自由发挥结构。

```markdown
# Spec: <模块名 / 节点名>

## 0. 元信息
- 类型: Agent 节点 | REST API | 业务模块 | 基础设施
- 所属上下文: 建档 / 规划 / 任务 / 复盘 / 记忆 / 安全
- 优先级: P0 | P1
- 上游: <依赖谁>
- 下游: <被谁依赖>

## 1. 职责（一句话）
<这一行话讲清楚该模块存在的唯一理由>

## 2. 输入 Schema
| 字段 | 类型 | 必填 | 约束 | 说明 |
|---|---|---|---|---|
| ... | ... | ... | ... | ... |

## 3. 输出 Schema（Structured Output）
| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| ... | ... | ... | ... |

### Structured Output JSON 示例
```json
{ ... }
```

## 4. 不变量（Invariants）
- I-1: <陈述句，每条一件事>
- I-2: ...

## 5. 状态机（若适用）
状态列表: ...
| 当前状态 | 下一状态 | 触发条件 | 副作用 |
|---|---|---|---|

## 6. 错误与降级
| 触发条件 | 级别 | 系统行为 | 用户可见 |
|---|---|---|---|

## 7. 依赖与副作用
| 类型 | 对象 | 读/写 | 说明 |
|---|---|---|---|

## 8. Prompt 策略（仅 Agent 节点）
- 模型: <具体模型名>
- system prompt 核心指令（≤ 5 行摘要）
- few-shot 数量: <数字>
- few-shot 选取规则: <规则>

## 9. 工具调用白名单（仅 Agent 节点）
允许调用: [工具A, 工具B]
禁止调用: [工具C]

## 10. 不做的事（负面边界）
- 不调用 <X>
- 不直接写 <表>
- 不返回 <字段>
```

---

## 5. 完整范例：诊断 Agent 节点 Spec

下面是一份**符合本规范的完整范例**，所有后续 spec 都参照此范例的颗粒度和结构。

---

### Spec: 诊断 Agent 节点（DiagnosisNode）

#### 0. 元信息

| 项 | 值 |
|---|---|
| 类型 | Agent 节点 |
| 所属上下文 | 规划（Planning Context） |
| 优先级 | P0 |
| 上游 | Java 业务层（传入 user_message + user_profile） |
| 下游 | 搜索蒸馏 Agent（接收 intent/goal_type/open_questions/search_need） |

#### 1. 职责（一句话）

识别用户意图、目标类型、所处阶段、缺失信息；决定是否需要追问、是否触发联网搜索；不生成任何计划内容。

#### 2. 输入 Schema

| 字段 | 类型 | 必填 | 约束 | 说明 |
|---|---|---|---|---|
| user_message | string | 是 | max_length=2000 | 当前用户消息 |
| user_profile | struct | 是 | — | 用户画像 |
| user_profile.goal_type | string | 否 | enum{cs_job_seeking, civil_service, ai_intern, general} | 目标类型，可为空（首次建档） |
| user_profile.stage | string | 否 | max_length=50 | 当前阶段描述 |
| user_profile.available_time | string | 否 | max_length=50 | 可投入时间 |
| recent_reviews | list<Review> | 否 | max_length=3 | 最近 3 次复盘，用于上下文 |
| history_stats.recent_completion_rate | float | 否 | range=[0.0, 1.0] | 近期完成率 |

#### 3. 输出 Schema（Structured Output）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| intent | enum | {plan, follow_up_question, high_risk} | 意图分类 |
| scene_tag | string | — | 场景标识（cs_job_seeking 等），未支持场景填 general |
| goal_type | string | — | 识别出的目标类型 |
| stage | string | max_length=50 | 识别出的阶段 |
| anxiety_points | list<string> | max_length=3 | 识别出的焦虑点，用于计划生成参考 |
| open_questions | list<string> | max_length=3 | 需要追问的问题；为空表示信息足够 |
| search_need | bool | — | 是否需要联网搜索 |
| search_keywords | list<string> | max_length=5；search_need=false 时必须为空 | 搜索关键词 |
| is_supported_scene | bool | — | 是否是已支持首发场景 |

**Structured Output JSON 示例**：

```json
{
  "intent": "plan",
  "scene_tag": "cs_job_seeking",
  "goal_type": "计算机央国企求职",
  "stage": "应届大四",
  "anxiety_points": ["不知道先做项目还是刷题", "担心没有实习经历"],
  "open_questions": [],
  "search_need": true,
  "search_keywords": ["2026 央国企 计算机 招聘", "央国企 技术岗 笔试内容"],
  "is_supported_scene": true
}
```

#### 4. 不变量（Invariants）

- I-1: `intent=high_risk` 时，`open_questions` 必须为空（不追问，直接分流到安全节点）
- I-2: `search_need=false` 时，`search_keywords` 必须为空列表
- I-3: `open_questions` 长度超过 3 时，截断为前 3 条（不在 prompt 里要求"最多 3 个"再做硬截断）
- I-4: 诊断节点**不生成**任何 plan、task、starter_action 字段
- I-5: `is_supported_scene=false` 时，`scene_tag` 必须为 `general`
- I-6: 诊断节点执行时间 ≤ 3 秒（用作 SLA 与超时判断依据）

#### 5. 状态机

诊断节点**不涉及业务对象状态流转**。本节不适用。

#### 6. 错误与降级

| 触发条件 | 级别 | 系统行为 | 用户可见 |
|---|---|---|---|
| LLM 调用超时（> 3s） | degrade | 使用小模型 fast retry 1 次（1s 超时）；仍失败则跳过诊断，直接走 general 兜底 | 无感知，转入通用规划 |
| LLM 返回不符合 schema | retry | tenacity 重试，指数退避，最多 3 次；仍失败则同上 degrade | 无感知 |
| `intent=high_risk` | fail（本节点终止） | 直接跳转安全分流节点，不进入后续 workflow | 高风险固定话术 |
| `user_message` 为空或纯空白 | fail（前置校验） | 由 Java 业务层拦截，不进入 Python agent | 系统提示"请输入你的问题" |
| `open_questions` 非空 | exit（正常分支） | 节点成功返回，workflow 提前结束，回到追问流程 | 返回追问消息 |

#### 7. 依赖与副作用

| 类型 | 对象 | 读/写 | 说明 |
|---|---|---|---|
| 外部服务 | DeepSeek 小模型 / GLM-4-Flash | 调用 | 诊断用小模型，成本极低 |
| 外部服务 | Tavily Search API | — | **不调用**（负面边界） |
| 数据表 | agent_steps | 写 | 节点完成后写一条记录，含 latency、status、output_hash |
| 数据表 | users / user_profiles | 读 | Java 侧读完后通过 input 传入，Python 不直接读 |
| 消息/事件 | 无 | — | 本节点不发事件 |

#### 8. Prompt 策略

- **模型**：DeepSeek 小模型 或 GLM-4-Flash（成本优先，任务简单）
- **system prompt 核心指令**（≤ 5 行摘要）：
  1. 你是一个规划助理的诊断模块，只做识别，不做建议
  2. 识别 intent、scene_tag、goal_type、stage、anxiety_points、open_questions
  3. 信息足够时返回 `open_questions=[]`；缺失关键信息时返回 1-3 个追问
  4. 涉及心理危机/医疗/法律/金融时返回 `intent=high_risk`
  5. 输出必须严格符合结构化 schema
- **few-shot 数量**：3 个
- **few-shot 选取规则**：
  - 1 个 `intent=plan, is_supported_scene=true` 的正例
  - 1 个 `intent=follow_up_question`（信息不足需追问）的例
  - 1 个 `intent=high_risk` 的例
  - few-shot 固化在 prompt 文件中，不动态选取

#### 9. 工具调用白名单

- 允许调用：无（诊断节点不调用任何工具）
- 禁止调用：Web Search、Memory Service、经验库检索、任何写操作

#### 10. 不做的事（负面边界）

- 不调用搜索 API（搜索由后续搜索蒸馏 Agent 负责）
- 不读 / 写记忆表（记忆由 Memory Service 统一管理，规划主流程之外）
- 不生成任何 plan / task / starter_action 字段
- 不直接写业务表（业务表落库由 Java 侧根据 agent 返回结果统一写入）
- 不做心理危机话术回复（高风险只标记 `intent=high_risk`，话术由安全分流节点负责）

---

## 6. Spec 的持久化判定矩阵

**承接开发流程指南里的 spec-driven 五段式**，明确哪些改动需要写 spec，哪些不需要。避免"任何改动都起一份 spec"的过度文档化。

| 改动类型 | 需要写 spec 吗 | 需要持久化吗 | 默认颗粒度 |
|---|---|---|---|
| 新增 Agent 节点 | ✅ 必写 | ✅ 持久化 | 一份完整 spec（按本规范全 10 节） |
| 新增 REST API | ✅ 必写 | ✅ 持久化 | 第 1-7 节 + 状态机可省 |
| 新增数据表 / 修改 schema | ✅ 必写 | ✅ 持久化 | 只写第 2/3/4/7 节 |
| 修改既有节点 prompt | ❌ 不起 spec | ✅ 记录到 ADR 或 git commit | 仅 prompt diff |
| 修改状态机流转规则 | ✅ 必写 | ✅ 持久化 | 只写第 5 节 + 对应不变量 |
| Bug fix（< 30 行，单模块） | ❌ 不起 spec | ❌ 不持久化 | 注释 + commit message 即可 |
| 跨模块 / 跨服务改动 | ✅ 必写 | ✅ 持久化 | 额外加一份**接口契约 spec** |
| 实验 / 探索性改动 | ❌ 不起 spec | ❌ 不持久化 | 代码里 TODO 标记 |

**判定口诀**：
> 跨上下文、新增 API、新增表、新增节点、改状态机 → 起 spec 并持久化。
> 单模块内的 prompt 调整、bug 修复、参数微调 → 不起 spec，commit 说清楚即可。

---

## 7. Spec 文件的存放与命名

### 7.1 存放位置

```
docs/
├── standards/
│   └── spec-writing-guide.md          ← 本文档
├── model-design/
│   ├── planning/
│   │   ├── 00_业务流程.md              ← 1 张总时序图，不写分册
│   │   ├── 01_API设计.md               ← 双服务契约，按 spec 规范
│   │   ├── 02_状态机.md                ← 全部状态机收口在此
│   │   ├── 03_数据库表.md             ← 表结构 spec
│   │   └── agent-nodes/
│   │       ├── diagnosis.spec.md      ← Agent 节点 spec（按本规范）
│   │       ├── distill.spec.md
│   │       ├── planning.spec.md
│   │       └── validation.spec.md
│   ├── profile/                        ← 其他 5 个上下文同构
│   ├── task/
│   ├── review/
│   ├── memory/
│   └── safety/
└── ...
```

### 7.2 命名规则

| 文档类型 | 命名 | 例子 |
|---|---|---|
| 模块总览 | `NN_中文名.md`（NN=01-13 编号） | `01_API设计.md` |
| Agent 节点 spec | `<node_name>.spec.md` | `diagnosis.spec.md` |
| API 契约 spec | `<resource>.api.spec.md` | `plan.api.spec.md` |

### 7.3 文档状态生命周期

承接开发流程指南的定义：

```
规划中 → 本轮实现 → 已实现
```

Spec 文件首部加一行状态标记：

```markdown
> 状态: 规划中 | 本轮实现 | 已实现
```

---

## 8. Spec 与其他文档的边界

避免重复，每份文档只做一件事。

| 文档类型 | 写什么 | 不写什么 |
|---|---|---|
| **PRD** | 用户故事、业务价值、指标、范围 | API schema、state、表结构 |
| **ADR** | 架构决策的"为什么"、备选方案对比 | 字段表、状态机 |
| **Spec（本规范管辖）** | 字段、不变量、状态机、错误边界 | 决策理由、用户故事 |
| **代码注释** | 实现意图、与非显然约束的提醒 | spec 已写的字段定义（不重复） |
| **Git commit** | 改了什么、为什么改 | 不写架构（架构在 ADR） |

**冲突解决原则**：当 PRD、ADR、Spec 之间出现不一致时，以 **Spec 为代码实现的唯一依据**，PRD 和 ADR 的更新落后于 spec 时，spec 优先；spec 有变更时反向同步更新 PRD/ADR。

---

## 9. 面试讲法（仅供参考，不写进文档正文）

这份规范本身是 senior 信号。面试时可以这样讲：

> "我为项目写了 spec 编写规范，因为代码主要由 AI 工具生成，spec 是 AI 的输入契约。规范核心是六要素模型：输入 schema、输出 schema、不变量、错误边界、状态机、依赖副作用。我特别强调负面边界——'诊断 Agent 不调用搜索 API' 比'诊断 Agent 主要做意图识别'更有用。我对每个 Agent 节点按固定模板填空，AI 生成质量明显比 narrative 式描述高。"

---

## 10. 本规范的版本演进

| 版本 | 日期 | 变更 |
|---|---|---|
| v1.0 | 2026-07-11 | 初版，定义六要素 + 模板 + 范例 + 持久化判定 |

**未来可能的方向**（不在 v1.0 范围）：
- 加入 spec 自动校验脚本（字段类型与 Pydantic/Java DTO 一致性检查）
- 加入 spec → OpenAPI 的自动生成
- 加入 prompt diff 自动归档机制

---

*本规范适用于 dazi 项目所有功能模块、Agent 节点、API 接口的 spec 编写。当本规范与既有 PRD 章节 6 冲突时，以本规范为准。*
