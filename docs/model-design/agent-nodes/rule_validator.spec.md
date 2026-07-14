# rule_validator.spec.md — 5 维规则校验节点

状态：本轮实现。

## 0. 节点定位

| 维度 | 内容 |
|---|---|
| 中文名 | 规则校验节点（5 维质量评分的程序部分） |
| 类型 | 程序节点（不调 LLM） |
| 工作流位置 | 第 7 步（career_planning_agent 候选输出后） |
| 字段引用 | [PRD §7 五维质量评分（核心质量约束）](../../overview/product-overview.md) |
| 写权限 | ❌ 不直接写 |

> 5 维里维度 1/2/3/5 由本节点跑；维度 4（连续性）由 `quality_reviewer` LLM Judge 跑。

## 1. 输入 Schema

`app.schemas.validation.ValidateRequest`

| 字段 | 类型 | 必填 |
|---|---|---|
| `candidate` | `PlanCandidate` | ✅ |
| `user_context` | `PlanningContext` | ✅（取 time_budget / history） |
| `history_today_tasks` | `list[str]` | ❌（连续性检查的输入，但实际判定在 quality_reviewer） |

## 2. 输出 Schema

`app.schemas.validation.ValidationReport`

| 字段 | 类型 | 必填 |
|---|---|---|
| `dimension_1_startable` | `Literal["pass","fail"]` | ✅ |
| `dimension_2_time_match` | `Literal["pass","fail"]` | ✅ |
| `dimension_3_cognitive_load` | `Literal["pass","fail"]` | ✅ |
| `dimension_5_deliverable` | `Literal["pass","fail"]` | ✅ |
| `fail_reasons` | `list[str]` | ✅ 详细每个 fail 的原因 |
| `rewrite_suggestion` | `str \| null` | ❌ |

## 3. 4 维的机器判定规则（程序化）

### 维度 1：可启动性（starter_action 显式性）
**Pass 条件**：每个 task 的 `starter_action` 命中动词白名单：
`[打开, 新建, 写下, 提交, 安装, 运行, 复制粘贴, 发送]` + 后接具体对象（如 `打开 XX`）

**Fail 信号词**：`[准备, 了解, 研究熟悉, 学习, 思考]`

### 维度 2：时段匹配
**Pass 条件**：`sum(task.estimated_minutes) <= user_context.time_budget_minutes`

### 维度 3：认知负荷
**Pass 条件**：每个 task 的动词 ∈`[写, 改, 提交, 完成, 跑通, 并发]`（高产出动词）
**Fail 信号词**：`[理解, 熟悉, 掌握, 看, 弄懂]`

### 维度 5：完成可验证
**Pass 条件**：每个 task `deliverable` 字段含可观测产物（关键词 `[diff, 文件, commit, log, 文档, 答案, URL]`），且不包含抽象词 `[提升, 打好, 加强, 夯实]`

## 4. 不变量

| ID | 不变量 |
|---|---|
| INV-1 | 4 维任一 fail → `fail_reasons` 非空 |
| INV-2 | 4 维全 pass → `fail_reasons == []` |
| INV-3 | 维度判定结果与 fail_reasons 一一对应 |

## 5. 错误边界

| 错误 | 处理 |
|---|---|
| 动词白名单配置缺失 | fail-hard（配置错误） |
| candidate.today_tasks 为空 | 视为全维 fail：`fail_reasons=["no_candidate"]` |

## 6. 状态机

无状态机。程序节点。

## 7. 依赖与副作用

| 依赖 | 用途 |
|---|---|
| 配置 | `core/validator/verb_whitelist.py`（高产出/可启动动词） |
| 配置 | `core/validator/fail_signals.py`（抽象词词表） |
| 读 | `user_context` |
| 写 Trace | 节点一行 |

## 8. Trace 字段

| 字段 | 示例 |
|---|---|
| `node_name` | `"rule_validator"` |
| `dim_1` | `"pass"` |
| `dim_2` | `"fail"` |
| `dim_3` | `"pass"` |
| `dim_5` | `"pass"` |
| `fail_reasons` | `["dim_2: tasks total 5h > budget 30min"]` |

## 9. 参考实现顺序

1. `schemas/validation.py` ValidationReport
2. `core/validator/verb_whitelist.py` + `fail_signals.py`
3. `agent/nodes/rule_validator.py`
4. `tests/agent/test_rule_validator.py` ≥4 case（每维 fail 一个 + 全 pass）

## 10. 引用

- [PRD §7](../../overview/product-overview.md) 5 维质量评分（业务判定）
- [TDD §8](../../architecture/tdd.md) 实现机制
