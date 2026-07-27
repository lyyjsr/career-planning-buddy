# cron-and-workers.md — 定时任务与后台 Worker

| 项目 | 内容 |
|---|---|
| 文档版本 | v0.1 |
| 日期 | 2026-07-26 |
| 状态 | 本轮实现 |
| 来源 | 解决 [gap-analysis §8.2](../model-design/feature-flows/gap-analysis.md)：项目的多处"由 cron 触发"此前分散在各 spec，无统一登记 |

## 1. 范围

MVP 所有"非用户请求触发"的定时 / 异步任务集中登记。无 Celery/Redis（PRD §10.2），仅基于 PostgreSQL 表 + Python `apscheduler` 或简易 cron worker。

## 2. 任务登记表

| ID | 任务 | 触发频率 | 操作表 | 操作类型 | 详细 spec | 失败行为 |
|---|---|---|---|---|---|---|
| CRON-1 | 任务过期标记 | 每 5 分钟 | `tasks` | UPDATE pending/in_progress + expired_at 到期 → state='expired' | [state-machines/task-state.mmd](../model-design/state-machines/task-state.mmd) `pending/in_progress → expired` | 单条失败不阻塞，写 trace warning |
| CRON-2 | 敏感记忆候选清理 | 每小时 | `memory_candidates` | DELETE WHERE status='pending' AND expires_at<now() | [memory_candidates.md §生命周期](../model-design/data-models/memory_candidates.md) | 同上 |
| CRON-3 | 短期记忆过期 | 每天 03:00 | `memories` | DELETE WHERE type='session_temp' AND expires_at<now() | [memories.md](../model-design/data-models/memories.md) | 同上 |
| CRON-4 | plan 90 天归档 | 每天 04:00 | `plans` | UPDATE status='archived', archived_at=now() WHERE status IN ('active','adopted','completed') AND created_at < now() - interval '90 days' | [plan-status.mmd](../model-design/state-machines/plan-status.mmd) | 同上 |
| CRON-5 | search_sources 归档 | 每周 | `search_sources` | DELETE WHERE expires_at < now() | [search_sources.md](../model-design/data-models/search_sources.md) | 同上 |
| CRON-6 | experience_atoms 归档 | 每周 | `experience_atoms` | SET inactive WHERE expires_at < now()（保留行供 Trace） | [experience_atoms.md](../model-design/data-models/experience_atoms.md) | 同上 |
| WORKER-1 | Run 调度 | 持续轮询 | `agent_runs` | SELECT WHERE status='pending' ORDER BY created_at → invoke LangGraph → UPDATE status='running' | [run-status.mmd pending→running](../model-design/state-machines/run-status.mmd)、[agent-runs.md](../model-design/api-spec/agent-runs.md) | 失败 UPDATE status='failed' + fallback_reason |
| WORKER-2 | 安全事件监控（阶段 6） | 推送给 ops | （无表写入；读 agent_steps WHERE node_name='safe_response'） | —— | [safe_response.spec.md §6](../model-design/agent-nodes/safe_response.spec.md) | 不影响业务，仅监控通道降级 |

## 3. 实现要点

### 3.1 Worker 实现

`app/workers/scheduler.py`（建议路径）：

```python
# 伪代码示意，非真实代码
from apscheduler.schedulers.asyncio import AsyncIOScheduler

def build_scheduler(session_factory):
    sched = AsyncIOScheduler()
    sched.add_job(cron_task_expire, "interval", minutes=5, id="CRON-1")
    sched.add_job(cron_memory_candidate_cleanup, "cron", minute=0, id="CRON-2")
    # ...
    sched.add_job(run_dispatcher, "interval", seconds=2, id="WORKER-1")
    return sched
```

### 3.2 幂等与并发

- 所有 cron 都是幂等的（重复执行无副作用）：基于 `WHERE status='pending'` 等条件判定，自然避免重复 UPDATE
- 同一 record 多次执行用 `version` 字段做乐观锁
- `WORKER-1` 用 `SELECT FOR UPDATE SKIP LOCKED` 防多 worker 抢同一 run

### 3.3 关停与恢复

- `SIGTERM` 时优雅停止：等待当前 run 完成
- Run 在 LangGraph checkpointer 中持久化（ADR-009），重启后可恢复中断的 run

## 4. 监控

每个 cron 执行写一行到 `cron_runs`（建议新建表，与 `agent_steps` 同结构）或集成到 `core/logging.py`。失败阈值告警由 `governance/verification-and-review.md` 后续定义。

## 5. 与 PRD 阶段对齐

| 阶段 | 落地任务 |
|---|---|
| 阶段 2（纵切骨架 mock） | WORKER-1（run dispatcher） |
| 阶段 5（Harness 完成） | CRON-1（task expire）+ CRON-2（candidate 清理） |
| 阶段 6（产品完整度） | 其余 cron + WORKER-2（安全监控） |

## 6. 引用

- PRD §10.2 MVP 不做 Celery/Redis/K8s
- 各状态机：[plan-status.mmd](../model-design/state-machines/plan-status.mmd) / [task-state.mmd](../model-design/state-machines/task-state.mmd) / [run-status.mmd](../model-design/state-machines/run-status.mmd)
- ADR-006：记忆系统分层（含候选池过期）
- ADR-009：LangGraph checkpointer
