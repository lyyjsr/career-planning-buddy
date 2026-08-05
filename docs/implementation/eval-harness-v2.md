# Eval Harness V2 实施记录

## 范围

V2 按 PR-0 到 PR-8 递进交付。本文记录已冻结和已实现的边界，完整 Replay 引擎、真实
模型评估、统计门禁和线上漂移监控属于后续 PR，不在 PR-0/PR-1 中提前伪实现。

## PR-0：Truth Baseline 与契约冻结

- 移除恒真的 `snapshot_replay` grader；
- 保留兼容 API，但将现有行为命名为 `legacy_trace_clone`；
- API 响应、Trace 和 config snapshot 显式记录 execution kind；
- 以 [`eval-harness-v2-baseline.md`](./eval-harness-v2-baseline.md) 保存改造前事实基线；
- 无数据库迁移，旧 Run 与旧 API 路径保持可读。

## PR-1：Evidence Integrity

- `EvidenceVisibility` 是候选级值对象，冻结逻辑调用 ID、完整目录 hash、可见引用和被截断引用；
- normal、force-final、format repair、business repair 都显式接收证据目录；
- candidate 只按产生它的 Provider 调用可见范围校验，不按 Run 全局目录校验；
- 空引用合法且不会被 Graph 自动补齐；
- 失败 Tool 或被 Tool 压缩器移除的项目不会进入可见目录；
- Trace 只保存 ID、hash、count，不保存证据正文；
- finalizer 保存候选原样引用，并在事务前再次验证可见性。

## 后续顺序

PR-2 数据集契约与 provenance，PR-3 确定性 grader，PR-4 fixture/schema，PR-5 真实 Replay，
PR-6 实验持久化与队列，PR-7 分层评估与 LLM Judge，PR-8 CI/夜间/线上监控。后续 PR
不得把 Mock 规则回归指标描述为真实模型或生产质量结论。
