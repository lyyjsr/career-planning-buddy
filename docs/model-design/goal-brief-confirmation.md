# Goal Brief 目标澄清与确认设计

## 目的

用户提出“设计一个面向岗位的项目”等开放目标时，系统不应立即执行计划生成。系统先形成可检查的 `GoalBrief`，信息不足则追问，信息足够则展示摘要和系统假设；只有用户明确确认后才创建 `AgentRun`。

## 职责边界

- `GoalBrief` 负责目标字段、信息充分性、追问、版本冲突和确认状态。
- Goal Understanding Provider 负责结构化抽取。配置真实 LLM 时使用 LLM；未配置时使用确定性规则；真实 Provider 失败时降级为规则。
- 充分性策略由应用服务确定，LLM 无权把草案标记为已确认。
- `AgentRun` 只接收已经确认的规范化目标并负责可靠执行。
- `Plan` 仍采用 1–8 周总体周期，并固定展开从当天开始滚动未来 7 天任务；当前产品没有 3/5/7 天执行窗口选择。

## 最小充分性

必须明确目标岗位和项目目标。周期、能力重点、技术栈、交付物与成功标准可以使用清晰展示的系统建议，用户可在确认前修改。画像中的岗位方向可以补足目标岗位，但不会被当成用户对本次草案的确认。

## 状态与可靠性

状态机见 [goal-brief-confirmation-flow.mmd](./state-machines/goal-brief-confirmation-flow.mmd)。写接口携带版本号；创建接口使用 `Idempotency-Key`；每位用户最多存在一个未结束草案。确认时在同一数据库事务中更新 `GoalBrief` 并创建带唯一 `goal_brief_id` 的 `AgentRun`，事务提交后再唤醒持久执行器。

## API

- `POST /api/v1/goal-briefs`：创建并分析目标草案。
- `GET /api/v1/goal-briefs/{id}`：恢复草案。
- `POST /api/v1/goal-briefs/{id}/refine`：补充或修改草案。
- `POST /api/v1/goal-briefs/{id}/confirm`：用户确认并创建 Agent Run。
- `POST /api/v1/goal-briefs/{id}/cancel`：取消草案。
- `GET /api/v1/me`：通过 `active_goal_brief` 恢复刷新前状态。
