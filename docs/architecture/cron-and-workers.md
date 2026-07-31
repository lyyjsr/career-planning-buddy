# 单 Worker 与定时任务设计

## 1. Agent Run 执行器

MVP 只允许单 Uvicorn Worker。`AgentRunExecutor` 维护进程内 `dict[run_id, asyncio.Task]`，数据库保存权威状态、Snapshot 和事件。

创建流程：

1. Service 校验幂等和活动 Run；
2. 写 `agent_runs(pending + config snapshot)`；
3. 提交事务；
4. Executor 创建 asyncio Task；
5. Task 使用独立 Session、CancellationToken 和 Deadline 执行 Graph；
6. 正常计划由 Finalizer.finalize_plan 事务收敛；异常/取消由同一 Finalizer 收敛；
7. finally 删除 Registry 项。

取消流程：

1. 校验 Run 属于当前用户且非终态；
2. 条件更新 `cancel_requested_at`；
3. 找到本进程 Task 时调用 `cancel()`；
4. Task 在取消检查点停止，不进入下一节点；
5. Finalizer 条件写 cancelled 和唯一 `run.cancelled`；
6. Task 不存在时由 Service/Finalizer 根据数据库状态收敛，不能重复写 terminal event。

## 2. 启动恢复

应用启动时：

- 查询超过 `deadline_at` 的 pending/running Run；
- 条件标记 failed；
- fallback_reason/error_code=`PROCESS_INTERRUPTED`；
- 写唯一 `run.failed`；
- 不自动重新执行，避免重复 Provider 调用和业务写入。

## 3. 定时任务

单进程 APScheduler 或应用内 scheduler 只做轻量清理：

| Job | 周期 | 行为 |
|---|---|---|
| expire_tasks | 每小时 | scheduled_date 早于今天且仍 pending → expired |
| expire_memory_candidates | 每天 | 过期 pending candidate → expired/rejected |
| archive_old_plans | 每天 | 按产品保留策略归档长期 completed 计划 |
| cleanup_guest_users | 每天 | 无业务数据且超过保留期的 guest 用户清理 |
| detect_stale_runs | 每分钟 | 超 deadline 的 pending/running → failed |

所有 Job 必须幂等，使用数据库条件更新和唯一约束，不能与在线请求产生非法双终态。

## 4. 升级到多 Worker 的前置条件

引入 Celery/Redis、Redis Streams 或数据库抢占队列前，必须解决：

- worker lease / heartbeat；
- ACK、重试和死信；
- 幂等执行；
- 分布式 terminal event 唯一性；
- 事件顺序；
- 取消传播；
- 任务接管和滚动升级。
