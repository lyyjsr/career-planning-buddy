# AGENTS.md — AI 协作宪章（释义版）

| 版本 | v1.0 |
| 状态 | 定稿 |
| 定位 | **释义文档**——根 [AGENTS.md](../../AGENTS.md) / [AGENTS.zh-CN.md](../../AGENTS.zh-CN.md) 是 AI 入口的权威单一事实来源；本文件补充中文释义、项目身份边界、Spec-Driven 五段式与禁止行为的完整说明 |
| 优先级 | 与根 AGENTS.md 同等；冲突时以根 AGENTS.md 为准 |

---

## 1. 项目身份

这是一个 **AI 求职规划搭子** 项目——面向计算机学生的求职规划 Agent。单核心 Agent（CareerPlanningAgent）+ 受控节点工作流 + 六层 Harness。

**项目不是什么**：
- 不是多 Agent 系统（所有"Agent"实际是节点，只有 1 个真 Agent）
- 不是 Java 业务系统（FastAPI 单后端）
- 不是聊天机器人（有任务状态闭环）
- 不是 demo（是完整工程项目）

---

## 2. 必读路径

权威的按场景路由表见根 [AGENTS.md §Required Reading Paths](../../AGENTS.md)。本节给精简中文版：

| 顺序 | 文档 | 作用 |
|---|---|---|
| ① | [PRD v2.0](../overview/product-overview.md) | 做什么、为什么、验收标准 |
| ② | [ADR v2.0](../architecture/adr.md) | 8 条核心技术决策 |
| ③ | [TDD v1.0](../architecture/tdd.md) | 系统怎么分层、Agent 怎么跑 |
| ④ | [API v1.0](../architecture/api-and-data-contracts.md) | 接口契约、Schema、状态机 |
| ⑤ | [技术点决策矩阵](../architecture/technology-decision-matrix.md) | 每个技术点现在做/延后/不做 |
| ⑥ | [阶段化交付](./stage-delivery-definition.md) | 当前在哪个阶段、退出条件 |
| ⑦ | [Spec-Driven 工作流](./spec-driven-workflow.md) | 改动前的澄清→计划→任务流程 |
| ⑧ | [Spec 编写规范](../standards/spec-writing-guide.md) | 节点/API spec 怎么写 |

---

## 3. 不可协商规则

权威清单（含 RFC 2119 关键字与 Enforced-by 标注）见根 [AGENTS.md §Non-Negotiable Rules](../../AGENTS.md)：R-Layer1/2/3、R-Contract1/2、R-Agent1/2、R-Data1/2、R-IO1/2、R-Fail1、R-Prompt1/2、R-Safety1/2、R-Plan1/2。中文镜像见 [AGENTS.zh-CN.md](../../AGENTS.zh-CN.md)。本节不重复。

---

## 4. Spec-Driven 五段式

每次改动必须走：

```
改动到来
  ↓
① Clarify   边界/假设不明确 → 登记 clarify.md
② Plan      跨模块/触状态机/新增 API/新增表 → 写 plan.md + mermaid
③ Tasks     跨服务/新增 API/新增表 → 写 tasks.md + [P] 并行标记
④ Implement 按 schemas → services → runtime → api 顺序
⑤ Verify    pytest + import-linter + ruff + eval + 自愈回灌
```

完整 lavor 流程图、持久化判定矩阵、`clarify.md` / `plan.md` / `tasks.md` 三个模板见 [spec-driven-workflow.md](./spec-driven-workflow.md)；条款级别的约束见根 [AGENTS.md](../../AGENTS.md) R-Plan1 / R-Plan2。

---

## 5. 代码风格

权威清单见根 [AGENTS.md §Code Style](../../AGENTS.md)；编码细节规则在 [standards/python-coding-standards.md](../standards/python-coding-standards.md)。本节不重复。

---

## 6. 禁止行为

权威禁止清单见根 [AGENTS.md §Forbidden Behaviors](../../AGENTS.md)（中文镜像 [AGENTS.zh-CN.md](../../AGENTS.zh-CN.md)）。本节不重复。

---

## 7. 当前阶段

**📍 阶段 0：工程基线**

下一步：搭骨架 + import-linter + docs 目录 + Docker Compose 模板。

退出条件：见 [阶段化交付定义](./stage-delivery-definition.md)。

---

## 8. 如何提问题

发现 spec 有歧义 / 冲突 / 缺失时：
1. 不要擅自决定
2. 在 `docs/clarify/{date}-{topic}.md` 登记问题
3. 等待决策后更新对应 spec 文档
