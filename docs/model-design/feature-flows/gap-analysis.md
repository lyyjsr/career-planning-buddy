# 功能模块对齐性审查报告（gap-analysis）

| 项目 | 内容 |
|---|---|
| 文档版本 | v0.2 |
| 日期 | 2026-07-26（初稿）/ 2026-07-26（A 类冲突收敛） |
| 状态 | **A 类（架构层 vs 施工层契约漂移）的核心冲突已在 §1 决策点 1/2/3/4/5/6 落地**：架构层 [api-and-data-contracts.md](../../architecture/api-and-data-contracts.md) 已修订到新版本（§4.1 路径前缀规则 / §5.2-5.5 加 view 声明 / §6.2 PlanStatus 5 值 / §6.3 memory 敏感入 candidates / §7.2 SSE 命名收敛 / §12 端到端示例修正）。**B 类（功能点→API 承接缺口）尚未处理**——见 §2-7 各模块修复建议 |
| 范围 | career-planning-buddy/docs 下与"功能点设计完善度 + API/状态机/表对齐"相关的全部 spec |
| 方法 | 4 个交叉对齐矩阵：①功能点×节点 ②API Request×业务动作 ③API Response×表字段 ④状态机转移×触发动作 |
| 引用约定 | `<file>:<line>` 形式直接定位证据 |

> **A 类冲突的收敛决策**（ prat 的 6 条 P0 决策点已采纳，详见 §9 决策清单"已落地"列）：
> - **§1.1 路径前缀**：所有"当前用户资源"路径不带 `/me/`，身份校验统一靠 JWT claim 推断（aigov 风格）。仅 `GET /api/v1/me` 作为聚合端点保留（"次日续上"摘要）。
> - **§1.2 agent-runs Request**：`message + goal_type_override(可选) + hint_intent(可选)`。`intent` 字段由 LLM intent_router 判别后写入 agent_runs，不信任前端直传。
> - **§1.3 plan 状态机**：5 值 `pending / active / adopted / completed / archived`。废弃旧 6 值（draft/generated/in_progress/abandoned）。
> - **§1.4/§1.5 plan/task 实体建模**：架构层 PlanDetail/PlanTask 改为**响应视图 view schema**（明确标 "service 由 plans + tasks + search_sources + companion_messages 拼装"），存储模型以 [data-models/](../data-models/) 为准。
> - **§1.6 memory 类型枚举**：`memories.type` 4 值，敏感只入 `memory_candidates` 表。架构层 §5.5 已对齐。
> - **§1.7 SSE 事件命名**：架构层 §7.2 表为单一事实源（11 个事件）；`companions.message` 拼写已修正为 `companion.message`；最小订阅集 = `progress + plan.ready + degraded + run.failed + run.completed`（+首次建档 `clarification.requested`）。

---

## 0. 总体结论

当前 spec 体系**总量非常完整**（PRD + ADR + TDD + API 契约 + 11 节点 + 10 表 + 4 状态机），但在"功能点→API→表→状态机"的垂直对齐上存在**两类系统性问题**：

- **A 类：架构层 vs 施工层契约漂移**。`architecture/api-and-data-contracts.md`（v1.0，2026-07-11，615 行）与 `model-design/api-spec/*.md` 在**路径、字段名、字段语义**上大面积不一致。架构层的契约更接近 PRD/TDD 的全口径，而 api-spec 是后来重写的"施工版"，二者未做同步收敛。
- **B 类：功能点→API 的承接缺口**。PRD §6 部分 P0 子功能在 api-spec 中找不到独立端点（或字段不齐），节点 spec 描述了行为但 api-spec 没有公开出口。

A、B 两类问题如不先收敛，阶段二写的"功能模块文档"会同时引用两套冲突的契约，**任何流程图和 CRUD 矩阵都会自相矛盾**。因此本报告的修复建议**先收敛 A 类（架构层与 api-spec 二选一）**，再补 B 类。

下文按 6 个功能模块逐一列出。**所有标 ⚠️ 的条目都需要你拍板**——多数涉及"以哪一份为准"的方向选择题。

---

## 1. 命名/字段层面的全局性冲突（A 类，影响每个模块）

### 1.1 端点路径前缀冲突

| 资源 | architecture/api-and-data-contracts.md §4.1 | model-design/api-spec/*.md | 现状判定 |
|---|---|---|---|
| profile | `/api/v1/me/profile` | `/api/v1/profile` | ⚠️ **冲突**：架构层走 `/me/`（强调"不信任前端 user_id"），api-spec 砍掉了 `/me/` |
| tasks 列表 | `/api/v1/me/tasks`、`/api/v1/me/tasks/today` | `/api/v1/tasks` | ⚠️ **冲突**：同上；另外"今日任务"专用端点在 api-spec 中**缺失**，靠 `?date=today` 兜底 |
| reviews | `/api/v1/me/reviews` | `/api/v1/reviews` | ⚠️ 同上 |
| memories | `/api/v1/me/memories`、`/api/v1/me/memory-candidates/{id}/confirm` | `/api/v1/memories`、`/api/v1/memory-candidates/{id}/confirm` | ⚠️ 同上 |
| plans | `/api/v1/me/plans/active`、`/api/v1/plans/{plan_id}` | **缺席**（api-spec 没 plans.md） | 🔴 **缺端点级 spec** |
| agent-runs | `/api/v1/agent-runs` + `/api/v1/dev/runs` | `/api/v1/agent-runs`（无 dev 路径） | ⚠️ 开发者路径（trace/replay/eval）在 api-spec 中**完全缺失**，仅 `model-design/harness/` 描述 |

**证据**：
- 架构层：`architecture/api-and-data-contracts.md:120-135` 的端点表
- 施工层：`model-design/api-spec/profile.md:6,26`、`tasks.md:5,28`、`reviews.md:5`、`memories.md:5,20` 等

### 1.2 agent-runs 请求字段冲突（最严重）

| 字段 | architecture/api-and-data-contracts.md §12 + §4 | model-design/api-spec/agent-runs.md |
|---|---|---|
| 消息字段 | `user_request: str` + `intent: "create_plan"/...` | `message: str` + 无 `intent` 字段 |
| 场景覆盖 | `goal_type_override` 不存在，靠 `intent` 区分 create_plan/replan | 有 `goal_type_override` |
| 类名 | `CreateRunRequest` (`schemas.agent_run`) | `CreateRunRequest` (`app.schemas.agent_run`) |

**证据**：
- 架构层：`architecture/api-and-data-contracts.md:439-443`（示例 A Payload `intent` + `user_request`）、`:549`（示例 C 同结构）
- 施工层：`model-design/api-spec/agent-runs.md:16-20`（`message` + `goal_type_override`）

⚠️ **决策点 1**：以 `intent + user_request` 还是 `message + goal_type_override` 为准？
- 选 `intent + user_request`（架构层）：意图显式传，意图路由器（intent_router）无需 LLM 即可分流（但意图路由节点 spec 已声明"用 LLM 单次分类"，前后矛盾）
- 选 `message + goal_type_override`（施工层）：让 LLM 自己判意图（符合 `intent_router.spec.md` 节点定位），但 replan 触发路径只剩"用户主动说"或 server 兜底
- **我的建议**：以施工层为准（保留 `message`），**新增可选字段 `hint_intent`** 让前端可显式提示但仍允许 LLM 改写——并在架构层同步改正。

### 1.3 plan 状态机的双套语义冲突

| 维度 | architecture/api-and-data-contracts.md §6.2 | model-design/state-machines/plan-status.mmd + plans.md |
|---|---|---|
| 枚举值 | `draft / generated / adopted / in_progress / completed / abandoned` | `pending / active / completed / archived` |
| 触发"激活" | `adopted`（用户开始任一任务时） | `active`（persist 节点 commit 时） |
| abandoned | 枚举值之一 | **不存在**（只有 archived） |

**证据**：
- 架构层：`architecture/api-and-data-contracts.md:180,275-278`
- 施工层：`model-design/data-models/plans.md:12`、`model-design/state-machines/plan-status.mmd:3-12`

🔴 **决策点 2**：plan 状态机到底用哪一套？
- 架构层的 `draft→generated→adopted→in_progress→completed/abandoned` 更贴合用户旅程的"生成→采纳→执行→完成"语义，但和 task 状态机的 in_progress（任务级）混淆；
- 施工层的 `pending→active→completed→archived` 更简洁，与 persist 节点 spec 一致，但**丢失了"用户采纳"这个产品动作**（PRD §5.1 happy path 明确"开始任一任务=采纳"）。
- **我的建议**：以施工层 4 值为基础，新增 `adopted`（用户首次开始任务时由 task 状态机副作用触发）；废弃 `draft/generated/in_progress/abandoned` 这套。

### 1.4 plan 实体的字段维度冲突

| 字段 | architecture/api-and-data-contracts.md §5.2 PlanDetail | model-design/data-models/plans.md |
|---|---|---|
| 内容存储 | 多个结构化字段：`horizon / summary / milestones / weekly_focus / today_tasks / companion_message / sources / adjustment_reason` 等扁平字段 | `content_json jsonb` 单一字段（rationale/assumptions/metadata） |
| 任务关联 | plan 自带 `today_tasks: list[PlanTask]` | tasks 独立表，通过 plan_id FK 关联 |
| sources | plan 字段 | 独立 search_sources 表 |

**证据**：
- 架构层：`architecture/api-and-data-contracts.md:166-183`
- 施工层：`model-design/data-models/plans.md:13`、`er-diagram.mmd:35-46`

⚠️ **决策点 3**：plan 实体关系建模以哪份为准？
- 施工层的"plan 顶层 + tasks 独立表 + sources 独立表 + companion_message 由 run/companion 表持有"是更可演进的建模；
- 架构层 PlanDetail Schema 是某个查询/响应组装出来的视图对象（前端读模型），**不是存储模型**。
- **我的建议**：明确 storage = `data-models/plans.md`，response view = `api-and-data-contracts.md §5.2`，在 api-spec `plans.md` 中区分"响应组装"层。这里**需要新建 `api-spec/plans.md`** 端点 spec。

### 1.5 task 字段命名冲突

| 字段 | architecture/api-and-data-contracts.md §5.3 PlanTask | model-design/api-spec/tasks.md + tasks.md |
|---|---|---|
| 任务状态字段名 | `status: TaskStatus` | `state` |
| 顺序字段 | `priority: int 1-3` | `order_index: int 0-2` |
| 放弃原因 | `abandon_reason_code` + `abandon_reason_text` 两段 | `abandoned_reason` 单字段枚举（无 text） |
| 完成可验证字段 | `deliverable` | `deliverable`（一致） |
| 启动动作字段 | `starter_action` | `starter_action`（一致） |

**证据**：
- 架构层：`architecture/api-and-data-contracts.md:185-197`
- 施工层：`model-design/data-models/tasks.md:13,23`、`api-spec/tasks.md:38`

⚠️ **决策点 4**：task 字段以施工层为准（更细），架构层 PlanTask §5.3 改为 view schema。
**特别提示**：`abandoned_reason` 缺少自由文本字段（如"其他原因"用户必须能说人话），施工层应补一个 `abandoned_reason_text` 列——见 §4 下面 review 模块也涉及。

### 1.6 memory 系统双套类型枚举

| 维度 | architecture/api-and-data-contracts.md §5.5 | model-design/data-models/memories.md + memory_candidates.md |
|---|---|---|
| 类型枚举 | 5 值：`profile_fact / stable_preference / execution_pattern / **sensitive** / temporary` | 4 值：`profile_fact / stable_preference / execution_pattern / session_temp`（敏感 type 走 candidates 表） |
| 状态枚举 | `candidate / confirmed / closed / deleted` | memories 无 status，candidates 是 `pending / confirmed / rejected` |
| sensitivity | `normal / sensitive` | `none / sensitive`（memories）；`sensitive / highly_sensitive`（candidates） |

**证据**：
- 架构层：`architecture/api-and-data-contracts.md:211-222`
- 施工层：`model-design/data-models/memories.md:11,13`、`memory_candidates.md:13-16`

🔴 **决策点 5**：以施工层的"敏感不入主表"为准还是以架构层的"敏感也是 memory 一种"为准？
- **我的建议**：以施工层为准（已经在 INV/persist/safe_response 多处落实）；架构层 §5.5 改写为"敏感走 candidates"以保持一致。

### 1.7 SSE 事件名冲突

| 事件 | architecture/api-and-data-contracts.md §7.2 | model-design/api-spec/agent-runs.md |
|---|---|---|
| 命名 | `run.created` `node.started` `node.completed` `tool.called` `tool.returned` `companions.message`(`companions` 拼写也疑似 typo) `run.completed` `run.failed` | `progress` `plan_ready` `degraded` `error` `complete` |

**证据**：
- 架构层：`architecture/api-and-data-contracts.md:307-318`
- 施工层：`model-design/api-spec/agent-runs.md:56-66`

🔴 **决策点 6**：**这是最该先收敛的一处**——前端没法实现两套事件名。两份都各 8 个事件，语义不重合。
- **我的建议**：以架构层为命名主体（更结构化），但 `companions.message` 改为 `companion.message`；并明确架构层 `node.started/completed` 与施工层 `progress` 的对应关系——后者作为聚合事件名保留。

---

## 2. 模块 1：首次建档——审查结果

**PRD §6 出处**：`overview/product-overview.md:236-237` 两行 P0：
- 首次建档：goal_type/stage/available_minutes 采集
- 首次建档：追问补齐

| 检查项 | 现状 | 缺口 |
|---|---|---|
| 字段命名 | `available_minutes` (PRD) vs `time_budget_minutes` (api-spec/tasks.md/skills) vs `available_minutes_per_day` (api-contracts §5.1) | 🔴 三套命名；以 api-spec `time_budget_minutes` 为基准 |
| 字段范围 | PRD 没说；api-contracts §5.1: `int (10-720)`；api-spec/profile.md:14: `int 15-480` | ⚠️ **范围不一致**，需统一 |
| 必填字段 | PRD 三必填 + 可选；api-spec/profile.md PUT "所有字段必填 OR 用 PATCH" | 🔴 **缺 PATCH 端点** spec（仅提一句"OR 用 PATCH"未给定义） |
| "skill_summary" vs "skills: list[SkillItem]" | api-contracts §5.1 用 `skills`；api-spec/profile.md + data-models/user_profiles.md 用 `skill_summary: text` | ⚠️ 决策点 7：结构化 vs 自由文本 |
| "target_companies / deadline / preferences" | api-contracts §5.1 列了；data-models/user_profiles.md **无字段** | ⚠️ 决策点 8：这些列是否要落到表 |
| "首次建档缺失触发的 clarification 端点" | `clarification.spec.md` 是 LLM 之后的节点；但**首次建档阶段**缺前端可用 API：是返回 200+missing_slots 还是 422？ | 🔴 **决策点 9**：clarification 的对前端契约（哪种触发、返回结构）完全没在 api-spec 中定义 |
| `goal_type` 枚举 | PRD §3.3 6 值；schemas/enums.py 已实装 GoalType；api-contracts §5.1 也 6 值 | ✅ 一致 |
| `stage` 枚举 | PRD 用文字"应届大四/研二"；api-spec 用 `early/mid/late/unknown`；api-contracts §5.1 用 string 任意 | ⚠️ 决策点 10：阶段语义映射缺 |
| 登录后自动生成 user 行 | users 表 `brief_login_type='guest'` 默认；auth/login 返回 `user_id` | ⚠️ "首次登录后是否自动 PUT 一份默认 profile"未定义 |
| 用户旅程 "次日续上" | PRD §5.1 列了这一动作；spec 无对应接口（应复用 GET /me 或 PATCH /profile？） | ⚠️ 决策点 11：续接/token 续期机制 |

**修复建议（不修代码，仅修 spec）**：
1. 统一字段名为 `time_budget_minutes`，范围 `[15, 480]`（采纳 api-spec）
2. 补 `api-spec/profile.md` 的 PATCH 端点 spec（用于"可选字段后补"场景，对齐 PRD §5.2 的"3 必填，其余可后补"）
3. 新增 `api-spec/clarification.md`：定义"首次建档阶段触发 clarification 的 API 形态"（建议 POST /agent-runs 内返回 schema 携带 `missing_slots`，前端按 hint_options 给问卷）
4. PRD §3.3 与 api-spec 的 stage/目标公司/截止日期字段做一次清单核对

---

## 3. 模块 2：生成规划（plan_run）——审查结果

**PRD §6 出处**：`overview/product-overview.md:238-240`。
- 生成规划：整体方向 + 本周重点 + 今日任务
- 动态事实联网核查 + 来源标注
- 5 维质量评分 + 校验降级

| 检查项 | 现状 | 缺口 |
|---|---|---|
| 触发入口 | POST /agent-runs | ✅ 存在（字段冲突见 §1.2） |
| 同步 vs 异步 | api-contracts §0: "创建返回 202 + run_id；GET 状态权威" | ✅ api-spec 一致 |
| SSE 端点 | api-spec/agent-runs.md GET /events | 🔴 **事件命名两套**（见 §1.7） |
| `intent=replan` 触发路径 | intent_router.spec.md 输入支持 4 值枚举 `create_plan/replan/query_plan/high_risk` | ⚠️ 决策点 12：replan 是从前端发起（带 plan_id）还是后端从 review 触发（见 reviews.md "副作用 ④"）？前端契约不清 |
| `intent=query_plan` 旁路 | intent-routing-flow.mmd 表显式"services.plan.read 不走 Agent" | 🔴 **缺 GET /me/plans/active 端点级 spec** |
| 通用场景兜底示例（goal_type=other） | api-contracts §12.3 给示例；api-spec 无 spec | ⚠️ 决策点 13：兜底是行为描述还是独立 intent |
| 高风险回落示例（companion_message 不空但 plan=null） | api-contracts §12.4 示例 | ⚠️ RunDetailResponse 是否给 `companion_message`（agent-runs.md:88 给了）；但 `plan=null` 时哪个字段告诉前端"这是风险分流"？缺 `risk_category` 透出 |
| 取消 Run | api-contracts §4.1 `/agent-runs/{id}/cancel` POST | 🔴 **api-spec 完全缺失 cancel 端点** |
| 节点 spec ↔ agent-runs 输入输出 | intent_router 输入需要 `user_id/message/goal_type/session_id/recent_intents`；agent-runs.md Request 仅 `message/goal_type_override` | 🔴 缺 `session_id`、`recent_intents` 来源（应由 server 注入） |
| run 列表（GET /agent-runs） | 架构层 §4.1 没列外部 list；只有 `/dev/runs` | ⚠️ 决策点 14：外部"我的规划历史"端点缺失 |
| 价格/预算 | PRD §9.4：单 run ≤ ¥0.2；agent.spec.md:18 `max_cost_cny=0.15`；trace agent_runs.total_cost_cny | ✅ 一致 |
| node count | PRD §6: "5 维质量评分 + 校验降级"通过 rule_validator+quality_reviewer+revise_or_fallback 实现；spec 端节点 11 个 | ✅ 覆盖 |

**修复建议**：
1. 先解决 §1.2 决策点 1，再统一架构层和 api-spec 的 Request Schema
2. 新增 `api-spec/plans.md`：GET /me/plans/active、GET /plans/{id}、GET /plans/{id}/sources
3. 在 `api-spec/agent-runs.md` 补 cancel 端点 + dev 路径（trace/replay）端点
4. SSE 事件先做 §1.7 决策点 6 收敛

---

## 4. 模块 3：今日任务推进——审查结果

**PRD §6 出处**：`overview/product-overview.md:241` P0：开始/完成/放弃。

| 检查项 | 现状 | 缺口 |
|---|---|---|
| 列表端点 | GET /tasks（带 date/status/plan_id/cursor/limit） | ✅ 完整 |
| 今日任务专用端点 | api-contracts §4.1 `/me/tasks/today` | 🔴 api-spec **缺失专用端点** |
| 状态转移端点 | PATCH /tasks/{id} 带 `state/version` 乐观锁 | ✅ 完整 |
| state 字段 vs status | tasks.md 用 `state`；api-contracts/PlanTask 用 `status` | ⚠️ 见 §1.5 决策点 4 |
| expired 状态 | task-state.mmd 标"后台 cron 每 5 分钟" | 🔴 **缺 cron 配置文档**（cron_config 或 docs/architecture/tdd.md 内引用） |
| abandoned_reason 自由文本 | tasks.md 仅 `abandoned_reason` 单字段枚举；api-spec/tasks.md 也只列枚举 | ⚠️ 决策点 15：PRD §6.2 "用户放弃任务记录原因"——reason_text 字段建议补 |
| "in_progress 进入副作用" | task-state.mmd:21 "started_at 写入" | ✅ 一致 |
| completed 必填字段 | api-spec/tasks.md 要求 `actual_minutes`；tasks.md 字段允许 NULL | ✅ 一致 |
| 任一用户行为触发"陪伴话术" | companion_response.spec.md：完成/放弃是 T2/T3 触发条件 | ⚠️ **缺前端返回话术的接口字段**——PATCH /tasks 响应只返 Task 对象，没 companion_message |

**修复建议**：
1. `tasks.md` 表新增 `abandoned_reason_text varchar(200) NULL`
2. PATCH /tasks 响应扩展为 `{task, companion_message?}`（或新增独立 GET /companion/trigger 端点）
3. task-state.mmd 的 cron 来源 → 在 governance 文档中加 "定时任务登记" 章节

---

## 5. 模块 4：每日复盘 + 复盘-调整闭环——审查结果

**PRD §6 出处**：`overview/product-overview.md:242-243`：复盘提交 + 复盘-调整双层。

| 检查项 | 现状 | 缺口 |
|---|---|---|
| 复盘提交端点 | POST /reviews | ✅ 完整（含 `trigger_replan` 可选） |
| Input 字段 | `plan_id/mood/blockers/completed_task_ids/abandoned_task_ids/free_text` | ✅ 完整（blockers 是 PRD §8 的"阻碍"） |
| 缺字段 | PRD §8.1 复盘 4 项："完成情况/情绪/阻碍/调整请求"——其中"调整请求" `adjustment_request` 在 api-spec 没有显式字段 | ⚠️ 决策点 16：用户主动提"调整"放 free_text 还是独立字段？ |
| Response | `ReviewResult: {review_id, companion_message, suggested_replan, next_plan_id}` | ✅ 合理 |
| 错误码 | STATE_PLAN_NOT_COMPLETED 409 | ⚠️ 决策点 17：这个错语义可疑——PRD 允许"中途复盘"（用户没完成所有 task 也能复盘），409 应改为"未到复盘窗口" |
| 复盘列表 GET /reviews | api-contracts §4.1 列了 `/me/reviews` POST/GET；api-spec 只有 POST | 🔴 **缺 GET 端点**（用户翻历史复盘） |
| replan 触发链路 | reviews.md "副作用 ④：若建议 replan，可选自动触发新的 plan_run（需用户在前端确认）" | 🔴 **缺"用户确认 replan"的端点**——PATCH /reviews/{id}/confirm? POST /reviews/{id}/replan? 完全没定义 |
| 复盘统计写入 reviews.consecutive_abandoned/consecutive_completed | 这是 service 计算的字段（写入表）但 API Request 不传 | ⚠️ 决策点 18：consecutive_* 是 server-side computed 还是 client 传？应 server computed（隐式OK，但 spec 应明示） |
| companion_message 生成路径 | reviews.md "副作用 ② 路由到 companion_response 节点"——但 companion_response 节点 spec 输入要 `trigger_tag/run_id`，reviews 流程没经过 run_id | 🔴 **缺口**：复盘阶段是否新建一个 review_run？还是 companion_response 不通过 LangGraph 跑而走同步 Service？节点 spec 与 API 副作用这里有歧义 |
| PlanStatus 转移 | plan-status.mmd:6 "active → completed: reviews 中 completed_task_ids 覆盖所有 plan task" | ⚠️ 决策点 19："覆盖所有"是写 review 时校验还是后台扫描？时机不明确 |

**修复建议**：
1. `api-spec/reviews.md` 补 GET 端点
2. 补 "用户确认 replan" 的端点（建议 POST /reviews/{id}/replan）
3. 明确复盘阶段 companion_message 的生成路径（建议：新建独立的 review_run 走 companion 节点，复用 trace 表）
4. reviews 表新增 `trigger_tag` 字段或 relations（记录触发了哪条话术）
5. STATE_PLAN_NOT_COMPLETED 语义重新定义

---

## 6. 模块 5：记忆管理 + 敏感记忆候选——审查结果

**PRD §6 出处**：`overview/product-overview.md:245-247`：记忆查看/删除/关闭 + 敏感记忆 candidates 池 → 用户确认后写入。

| 检查项 | 现状 | 缺口 |
|---|---|---|
| GET /memories | ✅ 含 type 过滤、include_sensitive 标记 | ✅ 完整 |
| DELETE /memories/{id} | ✅ 204 + 404/403 错误 | ✅ 完整 |
| PATCH /memories/{id}（关闭/确认） | api-contracts §4.1 列了 PATCH；api-spec **缺** | 🔴 **缺 PATCH 端点** |
| GET /memory-candidates | api-spec 列出但仅说"返回 MemoryCandidateListResponse" | ⚠️ 缺分页、缺 status 过滤 |
| POST /memory-candidates/{id}/confirm | ✅ 返回 Memory | ✅ 完整 |
| POST /memory-candidates/{id}/reject | ✅ 返 `{status:"rejected"}` | ✅ 完整 |
| candidate 过期 cron | memory_candidates.md expires_at 7 天 | 🔴 同 §4 expired，**缺 cron 配置文档** |
| 写入 memories 表的字段：last_used_at | memories.md:18 | ⚠️ memory_lookup 触发更新 last_used_at，但 spec 没说 API 端点（应该是节点行为，不需要外部 API） |
| 关闭（关闭后是否还能恢复？） | memories 无 status 字段，怎么关？ | 🔴 **架构-施工冲突**：架构层 §5.5 说 memory 有 status: candidate/confirmed/closed/deleted；施工层 memories 表无 status——除非以"删除"=DELETE 表达"关闭" |
| sensitivity 字段对外可见性 | memories.md:sensitivity='none'/'sensitive'；API 列表 include_sensitive=true 时展示 | ⚠️ 决策点 20：但 memories.md 表注释说"敏感内容不入此表，走 candidates"——那 memories 表里 sensitivity='sensitive' 的行是谁写进去的？冲突 |

**修复建议**：
1. 补 `api-spec/memories.md` 的 PATCH 端点 spec
2. 决策 6 后处理"关闭"语义：建议 memories 表加 `status varchar(16) DEFAULT 'active' CHECK IN ('active','closed')` 字段，PATCH /memories/{id} 用于切换
3. 6.3 memory_candidate 过期 + 4 task expired 全部进入"定时任务登记表"

---

## 7. 模块 6：安全分流——审查结果

**PRD §6 出处**：`overview/product-overview.md:244`：高风险识别 + 固定话术 + 12356。

| 检查项 | 现状 | 缺口 |
|---|---|---|
| 风险识别触发节点 | risk_gate.spec.md：LangGraph 第 1 步 | ✅ 完整 |
| 关键词词表 + LLM 分类器双重 | risk_gate.spec.md §6 双重 + INV-3 | ✅ 完整 |
| 高风险回落响应 | api-contracts §12.4 给示例（Response 200 + status=fallback + companion_message）；但 api-spec/agent-runs.md RunDetailResponse 无 `risk_category` 字段透出 | 🔴 run detail 缺 risk_category 字段 |
| safe_response 节点输出 → API 响应 | safe_response.spec.md 输出 `SafeResponse{message, hotline, additional_resources[], risk_logged}` | 🔴 RunDetailResponse / Run List 都没有 `hotline`、`additional_resources` 字段 |
| 不写入记忆的合规约束 | safe_response INVs + persist INV-3 | ✅ 完整 |
| Trace 字段 | risk_gate.spec.md §7 + safe_response.spec.md §8 | ✅ 与 trace-tables.md 对齐 |
| 安全事件监控告警 | safe_response.spec.md §6 "后台异步推送告警给运营（TODO，阶段 6）" | ⚠️ 决策点 21：MVP 是否做？ |
| 用户后续"我没事"恢复流程 | PRD/risk_gate 都未定义"safe_response 后用户继续聊"的衔接 | ⚠️ 决策点 22：是浅冲突还是 MVP 不做 |

**修复建议**：
1. `api-spec/agent-runs.md` RunDetailResponse 增 `risk_category` / `hotline` / `additional_resources` 三字段（fallback_reason 已存在）
2. 决策 22 给出"safe_response 后下一轮"的产品策略

---

## 8. 跨模块的横切问题

### 8.1 开发者路径缺失

`/api/v1/dev/*` 端点在架构层有 5 个（runs / runs/{id} / runs/{id}/replay / evals/datasets / evals/experiments），但 `model-design/api-spec/` **完全没有 dev 路径端点 spec**。CPB 独有的 `model-design/harness/` 目录写了 harness 设计但没拆端点 spec。

**修复建议**：新建 `model-design/api-spec/dev-runs.md` + `dev-evals.md` 两份端点 spec。

### 8.2 定时任务（cron）整体未建档

至少 3 处依赖后台任务但无 spec：
- task expired 自动标记（task-state.mmd:25）
- memory_candidate 7 天过期清理（memory_candidates.md:19）
- plan 90 天归档（plan-status.mmd:8 + plans.md:archived_at）

**修复建议**：新建 `architecture/cron-and-workers.md` 或在 `tdd.md` 内增加章节。

### 8.3 节点 spec ↔ API 端点的输入字段不对接

intent_router 节点需要 `session_id / recent_intents`，但 `/agent-runs` Request 不传——这些应由 server 注入。在 `_internal_schemas vs _api_schemas` 上没有显式说明。

**修复建议**：在每个 api-spec 端点末尾的"Service / Repository 调用"章节明示哪些字段是 server 注入的。

### 8.4 companion_message 的归属表

- plan 创建时（companion_response 节点输出）→ 应存到哪？plans.md/content_json？agent_runs？无字段
- 复盘时 companion_message → reviews 表无字段
- 任务 PATCH 后 companion_message → tasks 表无字段

**修复建议**：在 `data-models` 增加 `companion_messages` 表（或挂在 plans/reviews/tasks 上各自加 `companion_message text NULL` 字段）。当前 api-contracts §5.2 PlanDetail 给了 `companion_message` 字段，意味着 PlanDetail view 是按需拼接还是从某字段取——需要决定。

---

## 9. 决策清单（请逐条确认）

下面是需要你拍板的全部决策点（按 ID 汇总）。**前 6 条是 A 类核心冲突（§1），已于 2026-07-26 收敛落地，详见 §0 状态说明。** 后续 B 类（7-26）尚未处理。

| # | 决策点 | 我的建议 | 影响范围 | 状态 |
|---|---|---|---|---|
| 1 | agent-runs Request 字段：`intent+user_request` vs `message+goal_type_override` | 后者 + 增加可选 `hint_intent` | api-contracts §4,§12 + agent-runs.md + intent_router.spec.md | ✅ 已落地 |
| 2 | plan 状态机枚举 | 施工层 4 值 + 新增 `adopted` | api-contracts §6.2 + plan-status.mmd + plans.md | ✅ 已落地 |
| 3 | plan 实体建模 vs PlanDetail view | storage=施工层、view=架构层 PlanDetail | api-contracts §5.2 + plans.md + 新建 api-spec/plans.md | ✅ 已落地（架构层 §5.2 加 view 声明） |
| 4 | task 字段名 status vs state；priority vs order_index；reason_text 是否新增 | state + order_index + 新增 reason_text；架构层 §5.3 改 view | api-contracts §5.3 + tasks.md + api-spec/tasks.md | ✅ 已落地（架构层 §5.3 加 view 声明） |
| 5 | memory 类型枚举 | 施工层为准（敏感走 candidates） | api-contracts §5.5 + memories.md | ✅ 已落地 |
| 6 | SSE 事件命名 | 架构层命名主体 + `companions.message`→`companion.message` + 保留 progress 聚合 | api-contracts §7.2 + agent-runs.md | ✅ 已落地 |
| 7 | profile.skills: list[SkillItem] vs skill_summary: text | skill_summary text（简洁可演进） | api-contracts §5.1 + user_profiles.md | ✅ 已落地（架构层 §5.1 决策 7） |
| 8 | target_companies/deadline/preferences 是否落表 | deadline 入表（计划计算需要），其余纳入 content_json 或新增 profile_preferences 表 | api-contracts §5.1 + user_profiles.md | ✅ 已落地（架构层 §5.1 决策 8） |
| 9 | clarification 在首次建档阶段的 API 形态 | /agent-runs 200 返 missing_slots + hint_options（同节点 spec），不另起端点 | api-spec/agent-runs.md + 新增 clarification.md | 🔴 待处理（B 类） |
| 10 | stage 语义映射 | 在 PRD §3.3 增术语表条目 | overview/product-overview.md | ✅ 已落地（架构层 §5.1 决策 10 术语映射已登记 early/mid/late/unknown） |
| 11 | "次日续上"端点 | GET /me（含 active_plan + 今日 tasks + 昨日 review 摘要） | api-spec 新增端点 | 🔴 待处理（B 类） |
| 12 | replan 触发：前端发起还是 review 副作用 | 双路径：POST /agent-runs 带 hint_intent=replan（前端发起）+ reviews 副作用可触发（向后端推荐） | agent-runs.md + reviews.md | 🔴 待处理（B 类） |
| 13 | goal_type=other 兜底是否独立 intent | 不独立，intent_router 路由仍按 message 判 | intent-router-flow.mmd + intent_router.spec.md | 🔴 待处理（B 类） |
| 14 | "我的规划历史"端点 | 新增 GET /me/plans（cursor 分页） | api-spec 新增 plans.md | 🔴 待处理（B 类，路径已定 GET /api/v1/plans） |
| 15 | abandoned_reason_text 字段 | 新增 | tasks.md + api-spec/tasks.md | 🔴 待处理（B 类） |
| 16 | 调整请求字段 | 显式 adjustment_request 字段 | reviews.md + api-spec/reviews.md | 🔴 待处理（B 类） |
| 17 | STATE_PLAN_NOT_COMPLETED 语义 | 改为"未到复盘窗口"或删除该约束 | api-spec/reviews.md | 🔴 待处理（B 类） |
| 18 | consecutive_* 计算位置 | service computed（写入 reviews 表）| reviews.md 已隐含，spec 明示 | 🔴 待处理（B 类） |
| 19 | PlanStatus active→completed 的判定时机 | 同步：review 提交时 service 校验"task 全完成"则转移 | plan-status.mmd + reviews.md | ✅ 已落地（plan-status.mmd 同步事务约束已写） |
| 20 | memories 表 sensitivity='sensitive' 行来源 | 统一删除该取值（敏感只入 candidates） | memories.md + api-contracts §5.5 | ✅ 已落地 |
| 21 | 安全监控告警 MVP 范围 | 写 trace 不接告警通道，MVP 不做推送 | safe_response.spec.md | 🔴 待处理（B 类，范围决策） |
| 22 | safe_response 后用户继续聊的衔接 | MVP 不做（一进入 safe_response 即结束 run，下一轮新开 run） | safe_response.spec.md + run-status.mmd | 🔴 待处理（B 类，范围决策） |
| 23 | companion_message 数据归属 | 增 companion_messages 表（id,user_id,plan_id,trigger_tag,message,...） | data-models 新增 | 🔴 待处理（B 类） |
| 24 | cron 任务整体建档 | 新建 architecture/cron-and-workers.md | 新建文档 | 🔴 待处理（B 类） |
| 25 | dev 路径 API spec 是否补 | 补（dev-runs.md + dev-evals.md） | api-spec 新增 2 份 | 🔴 待处理（B 类） |
| 26 | canceled vs cancelled 拼写 | task-state.mmd 用 abandoned；plan-status.mmd 缺 abandoned；run-status.mmd 用 cancelled | 全文统一 | 🔴 待处理（拼写细节） |

---

## 10. 阶段一产出后的下一步

**A 类（§1 决策点 1-6）已收敛**——架构层与施工层契约已对齐，可以安全推进阶段二功能模块流程文档（不会出现"两套契约自相矛盾"的情况）。

**B 类（§9 决策点 9/11/12/13/14/15/16/17/18/21/22/23/24/25/26 共 15 条）尚未处理**——这些是"缺端点 / 缺字段 / 缺范围声明"的承接缺口，**不阻塞 contract 收敛但阻塞功能实现完整度**。

按资深架构师视角的推进顺序建议（**只列出关键路径，不要求全做**）：

| 优先级 | 决策点 | 理由 |
|---|---|---|
| P0（必做才能开工） | 9, 11, 14, 25 | 4 个缺失的端点 spec（clarification.md / me.md / plans.md / dev-runs.md, dev-evals.md）—— 没这些前端无接口可调 |
| P1（实现时一起做） | 12, 15, 16, 17, 18, 23 | 字段补齐 + 表结构调整——做对应 feature 时一并修，不是单独任务 |
| P2（可决定不做） | 13, 19, 21, 22, 24, 26 | 设计权衡，多数可"MVP 不做"——记入 stage-delivery-definition 的"重新评估时间点"即可 |

如果你只想推进到"能开工"，做完 P0 即可。如果某些决策你想分次给、或想我提供更细的对比表后再决定，请直接说，我会在那一条停下并展开更多上下文。

---

## 附录 A：可信度说明

本报告的所有结论建立在**直接读取了**以下文件的基础上（非 AI 脑补）：
- `overview/product-overview.md`（PRD v2.0）
- `architecture/api-and-data-contracts.md` v1.0
- `model-design/api-spec/` 全部 7 份
- `model-design/agent-nodes/` 全部 12 份 spec
- `model-design/data-models/` 全部 11 份（含 ER）
- `model-design/state-machines/` 全部 4 份 mmd + README
- `backend/app/providers/protocols.py`（DaZi 真实代码，CPB 同名文件为空）
- `backend/app/schemas/enums.py`（DaZi 真实代码）

没有读取/未交叉验证的：
- `architecture/tdd.md` 和 `adr.md`（仅扫了前若干行）
- `model-design/harness/*`（CPB 独有 4 份）
- `model-design/ui-spec/developer-trace.md`
- 各 standards/* 文档
如果你需要我把这些也纳入审查（如 tdd.md 是否和 api-contracts 在 API/状态机表述上一致），告诉我，单开一轮。
