# feature-flows/ — 业务功能模块流程文档入口

| 项目 | 内容 |
|---|---|
| 文档版本 | v0.1 |
| 日期 | 2026-07-26 |
| 状态 | 本轮实现；与 [gap-analysis.md](./gap-analysis.md) 配套产出 |
| 范围 | 按 PRD §6 功能清单分 6 个业务纵向模块，每模块固定 5 节（A 概览/B 流程图/C 接口字段/D CRUD 矩阵/E 组件依赖）|

## 定位

每个文件回答"该业务模块的端到端闭环是什么"：从前端动作 → 后端 API → 落表节点 → 调用 Provider 的全链路施工蓝图。与相邻目录的边界：

| 目录 | 角色 | 与本目录的差异 |
|---|---|---|
| `architecture/` | 跨特性契约（ADR / TDD / API 协议级） | 答"为什么这么设计" |
| `model-design/api-spec/` | 单端点字段级 spec | 答"端点 Request/Response 长什么样"|
| `model-design/agent-nodes/` | 节点级 spec | 答"节点输入/输出/不变量"|
| `model-design/state-machines/` | 状态机 + 转移矩阵 | 答"哪些转移合法"|
| **`feature-flows/`（本目录）** | **模块级跨层流程** | **答"该业务从用户点击到 DB 写入的全部步骤如何串起来"**|

## 6 个模块清单（按 PRD §6 P0 功能）

| # | 模块 | PRD §6 出处 | 文件 | 状态 |
|---|---|---|---|---|
| FM-01 | 首次建档（含澄清补齐） | goal_type/stage/time 采集 + 追问补齐 | [01-onboarding-profile.md](./01-onboarding-profile.md) | 本轮实现 |
| FM-02 | 生成规划（plan_run）| 整体方向+本周重点+今日任务，5 维评分+校验降级，来源标注 | [02-plan-run.md](./02-plan-run.md) | 本轮实现 |
| FM-03 | 今日任务推进 | 开始/完成/放弃 | [03-task-execution.md](./03-task-execution.md) | 本轮实现 |
| FM-04 | 每日复盘 + 复盘-调整闭环 | 复盘 4 项 + 双层调整 | [04-review-replan.md](./04-review-replan.md) | 本轮实现 |
| FM-05 | 记忆管理 + 候选确认 | 查看/删除/关闭 + candidates 池 | [05-memory-management.md](./05-memory-management.md) | 本轮实现 |
| FM-06 | 安全分流 | risk_gate → safe_response + 12356 | [06-risk-triage.md](./06-risk-triage.md) | 本轮实现 |

## 阶段产物

| 阶段 | 产出 |
|---|---|
| 阶段一 | [gap-analysis.md](./gap-analysis.md)（含 26 个决策点 + 修复建议）|
| 阶段四修订（提前完成）| A 类契约漂移 + B 类缺口（5 个新文件）已落实 |
| 阶段二 | 本目录 6 篇模块文档 |
| 阶段三 | [images/](./images/) mermaid 渲染图 |

## 全局对齐总览表（功能点 → API → 表 → 节点）

> 这是"功能点能否找到 4 层承接"的全局视图。✅ = 已具备施工级 spec；⚠️ = 有 spec 但需补；🔴 = 缺口。

| 功能点（PRD §6）| 所属模块 | 主要 API | 主要表 | 主要节点 | 状态 |
|---|---|---|---|---|---|
| 首次建档 3 必填采集 | FM-01 | PUT /profile | user_profiles | （非 Agent）| ✅ |
| 追问补齐 | FM-01 | clarification.requested SSE | agent_steps | clarification | ✅ |
| 生成规划（today 拆解）| FM-02 | POST /agent-runs + GET /plans/active | plans + tasks | 11 节点全链路 | ✅ |
| 来源标注 + 联网核查 | FM-02 | GET /plans/{id}/sources | search_sources | web_search tool | ✅ |
| 5 维评分 + 校验降级 | FM-02 | （内部，不暴露端点）| agent_steps (trace) | rule_validator + quality_reviewer + revise_or_fallback | ✅ |
| 今日任务 开始/完成/放弃 | FM-03 | PATCH /tasks/{id} | tasks + plans (副作用) + companion_messages | companion_response | ✅ |
| 每日复盘 4 项 | FM-04 | POST /reviews | reviews | companion_response | ✅ |
| 双层调整规则 | FM-04 | POST /reviews/{id}/accept-replan | reviews + agent_runs | （规则+Agent 兜底）| ✅ |
| 安全分流 + 12356 | FM-06 | POST /agent-runs (degraded) | agent_steps (trace) | risk_gate + safe_response | ✅ |
| 记忆 查看/删除/关闭 | FM-05 | GET/DELETE/PATCH /memories | memories | （非 Agent）| ✅ |
| 敏感记忆确认 | FM-05 | POST /memory-candidates/{id}/confirm /reject | memory_candidates + memories | persist（写入源）| ✅ |
| 次日续上 | FM-01 / 全局 | GET /me | plans + tasks + reviews | （非 Agent）| ✅ |
| 6 触发时刻陪伴话术 | FM-02/03/04 | （响应字段 companion_message）| companion_messages | companion_response | ✅ |
| 通用场景兜底（goal=other）| FM-02 | POST /agent-runs + companion_message 显式告知 | 同上 | intent_router + career_planning_agent | ✅ |
| 后台 Trace | （Harness） | GET /dev/runs/{id} | agent_runs + agent_steps + tool_calls | （@with_harness 装饰器）| ✅ |
| Replay 重跑 | （Harness P1）| POST /dev/runs/{id}/replay | 同上 | —— | ⚠️ agent_runs.replay_of_run_id 字段需补 |
| Eval | （Harness P1）| POST /dev/evals/experiments | eval_* 4 表 | —— | 🔴 eval_* 表 schema 未写 |

## 仍然开放的 TODO（阶段五/后续工作清单）

| # | TODO | 影响 | 优先级 |
|---|---|---|---|
| 1 | `agent_runs.replay_of_run_id` 字段添加到 [trace-tables.md](../data-models/trace-tables.md) | dev-runs replay | 阶段 5 |
| 2 | `eval_datasets / eval_cases / eval_experiments / eval_case_results` 4 表 schema | dev-evals 端点 | 阶段 5 |
| 3 | PRD §3.3 增加 stage 术语映射（决策 10）| FM-01 一致性 | 阶段 5 |
| 4 | `STATE_REVIEW_ALREADY_ACCEPTED` 错误码补入 [errors.md](../api-spec/errors.md) | FM-04 | 阶段 5 |
| 5 | memory_candidates 候选去重哈希 `content_hash` 字段 | FM-05 | 阶段 5 |
| 6 | cron_runs 监控表 schema（如启用）| 全模块 | 阶段 6 |
| 7 | safe_response 5 模板措辞评审 | FM-06 合规 | 阶段 6 |
| 8 | stage 调整规则脚本（PRD §8 调整红线具体阈值）| FM-04 | 阶段 6 |
| 9 | 阶段五跑 [DaZi/scripts/check-doc-links.sh](../../../../DaZi/scripts/check-doc-links.sh)（如 CPB 无）| 文档链接校验 | 阶段 5 |

## 阅读建议（按场景）

| 场景 | 必读顺序 |
|---|---|
| 第一次接手本仓 | gap-analysis.md → 本 README 总览表 → 模块 02（plan_run）|
| 实现"今天任务完成"接口 | FM-03 → api-spec/tasks.md → state-machines/task-state.mmd → companion_response.spec.md |
| 实现"复盘触发 replan"全链路 | FM-04 → api-spec/reviews.md → state-machines/plan-status.mmd |
| 评估设计完善度 | gap-analysis.md → 总览表 → 任一模块的 D 节 CRUD 矩阵 |
