# governance/ 目录入口

状态：本轮实现。

English summary: How AI and humans operate in this repo — reading guide, dev workflow, spec-driven workflow, verification, checklists, gates.

## 定位

指导 AI / 开发者 **如何在本仓库行动**：什么时候按什么顺序读哪些规范、如何按 spec-driven 实施、如何运行门禁、如何完成验证评审。

## 与相邻目录的边界

本目录**不承接**业务规则（在 `overview/` / `architecture/`）、代码规则（在 `standards/`）或特性 spec（在 `model-design/`）；它定义流程和约束如何被强制。

## 文档

阅读与流程：

- [AI 渐进式加载指南](./ai-reading-guide.md)
- AGENTS（双语根入口）：[../../AGENTS.md](../../AGENTS.md) · [../../AGENTS.zh-CN.md](../../AGENTS.zh-CN.md)
- [AI 协作宪章（释义版）](./AGENTS.md)
- [开发流程](./development-workflow.md)
- [新增用例开发 Checklist](./use-case-development-checklist.md)
- [验证与评审](./verification-and-review.md)

Spec-Driven：

- [Spec-Driven 工作流（澄清→计划→任务）](./spec-driven-workflow.md)

门禁与阶段：

- [门禁脚本规范](./check-scripts-spec.md)
- [阶段化交付定义](./stage-delivery-definition.md)

## 读取建议

第一次进入本仓库：先读 `AGENTS.md`，再读 `ai-reading-guide.md`，然后按当前任务的路由表加载。
