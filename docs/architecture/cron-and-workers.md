# 单 Worker 与定时任务设计

## 1. Agent Run 执行器

MVP 只允许单 Uvicorn Worker。`AgentRunExecutor` 维护进程内 `dict[run_id, asyncio.Task]`。

创建流程：

1. Service 在数据库写 `agent_runs(pending)`；
2. 提交事务；
3. Executor 创建 asyncio Task；
4. Task 用独立 Session 执行 Graph；
5. 结束时删除 Registry 项。

取消流程：

1. 校验 Run 属于当前用户且非终态；
2. 找到本进程 Task 并 `cancel()`；
3. 即使 Task 不存在，也把数据库状态收敛为 cancelled；
4. 写 `run.cancelled` 事件。

## 2. 启动恢复

应用启动时：

- 查询超过 `AGENT_DEADLINE_SECONDS + 30` 的 pending/running Run；
- 标记 failed；
- fallback_reason=`process_interrupted`；
- 写 `run.failed` 事件。

MVP 不自动重新执行，避免重复副作用。

## 3. 定时任务

单进程 APScheduler 或应用内 scheduler 只做轻量清理：

| Job | 周期 | 行为 |
|---|---|---|
| expire_tasks | 每小时 | scheduled_date 早于今天且仍 pending → expired |
| expire_memory_candidates | 每天 | 过期 pending candidate → rejected/expired |
| archive_old_plans | 每天 | completed 超过 90 天 → archived |
| cleanup_guest_users | 每天 | 无业务数据且超过保留期的 guest 用户清理 |
| detect_stale_runs | 每分钟 | 超截止时间的 run → failed |

所有 Job 必须幂等，并使用数据库条件更新避免重复处理。

## 4. 升级到多 Worker 的前置条件

引入 Celery/Redis、Redis Streams 或数据库抢占队列前，必须先解决：

- worker lease / heartbeat；
- ACK 与重试；
- 幂等执行；
- 死信；
- 事件顺序；
- 取消传播；
- 部署滚动升级。
