# overview/ 目录入口

状态：本轮实现。

English summary: What the project is — business positioning, unified vocabulary, bounded contexts, user journeys.

## 定位

用于理解项目**为什么存在、面向谁、解决什么问题**。回答"是什么"，不改领域模型、API 契约或代码事实。

## 与相邻目录的边界

- `architecture/` 回答"系统怎么设计"；本目录只回答"项目和业务是什么"。
- `model-design/` 回答"某个特性的节点 spec"；本目录给全局背景。
- `design-input/` 是出处资料，不是事实来源；本目录是事实来源。

## 文档

- [产品概览 PRD v2.0](./product-overview.md)
- [需求规格说明书 SRS](./srs.md) — 面向开发/评审，整理用户角色、功能边界、验收指标和需求追踪矩阵
- [用户使用说明书](./user-manual.md) — 面向最终用户/产品演示者，说明首次建档、生成规划、今日任务、每日复盘、重规划、记忆管理与状态变化
- [项目演示脚本](./demo-walkthrough.md) — 面向作品展示/面试演示，串起用户价值、核心链路与工程亮点

## 待补文档（按阶段化交付推进到阶段 1 时补齐）

- 统一术语表（goal_type/starter_action/plan_run/agent_step 等）
- 限界上下文与服务职责（MVP 是单后端，但需明确逻辑边界：建档/规划/任务/复盘/记忆/来源/Agent Runtime）
- 业务用例追踪矩阵（intent → 对应 API → 对应节点 → 测试）
