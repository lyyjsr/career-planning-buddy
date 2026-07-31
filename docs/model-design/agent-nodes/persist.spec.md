# persist — 受控持久化

## 定位

Graph 的适配节点，本身不直接操作 ORM，而是调用 `PlanPersistenceService.persist_validated_plan()`。

## Input

run_id、user_id、validated PlanCandidate、companion candidate、source ids、source_plan_id。

## 单事务动作

1. 锁定当前用户活动计划；
2. 创建新 Plan(generated)；
3. 批量创建 Tasks；
4. 创建 CompanionMessage；
5. 关联 SearchSource；
6. replan 成功时归档旧计划；
7. 更新 agent_runs.final_plan_id/status；
8. 写 plan.ready 和 run.completed/run.degraded 事件。

任何一步失败全部回滚，Run 在外层收敛为 failed。Memory candidate 不与计划主事务强绑，可在计划成功后单独幂等写入。
