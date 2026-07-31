# Stage 3：真实模型与执行反馈闭环

## 目标

接入真实 OpenAI-compatible LLM，完成任务状态、复盘和重规划。

## 实现范围

1. `LLMProvider` 真实实现与 Mock 契约测试；
2. CareerPlanningAgent 结构化输出；
3. Task PATCH 状态机；
4. Review POST / GET；
5. `POST /reviews/{id}/accept-replan`；
6. 新计划生成时归档被替代计划；
7. 计划首次开始任务时 generated → active；
8. 所有任务完成后计划 active → completed；
9. 规则校验不通过时最多修复一次，仍失败走模板降级。

## 复盘规则

Review 请求只提交复盘内容，完成/放弃数量由 Service 从 tasks 计算，避免客户端与数据库事实冲突。

触发重规划建议的基础规则：

- 连续两次放弃；
- 用户时间预算变化；
- 用户明确要求调整；
- 目标方向变化；
- 阻塞持续存在。

重规划必须由用户确认，不允许后台静默替换活跃计划。

## 验收

- 至少 5 个真实场景可生成结构化计划；
- 任务非法状态转移返回 409；
- Review 能给出 suggested_replan；
- 用户确认后创建新 Run；
- 原计划归档，新计划生成；
- 模型 API 超时、格式错、限流都有明确降级。
