# prompts/ 规范子目录

状态：设计基线。

English summary: Prompt-as-code standards — versioning, format, and review checklist. Agent 项目独有规范（普通 Web 项目没有）。

## 定位

Agent 项目里 Prompt 是版本化 first-class 工件（[AGENTS.md R-Prompt1/2](../../../AGENTS.md)）。本目录统一规范。

## 文件清单

| # | 文件 | 覆盖 |
|---|---|---|
| 1 | [prompt-format-standard.md](./prompt-format-standard.md) | 消息数组结构、System/Task/User 分层、few-shot 写法 |
| 2 | [prompt-versioning-standard.md](./prompt-versioning-standard.md) | 文件命名、版本机制、Replay 对比的依赖 |
| 3 | [prompt-review-checklist.md](./prompt-review-checklist.md) | Prompt PR 评审检查表 |

## 引用

- AGENTS.md R-Prompt1/2/3
- 节点 spec §6 Prompt 引用：[model-design/agent-nodes/](../../model-design/agent-nodes/)
- 代码位置：`backend/app/prompts/{goal_type}/<purpose>_v<n>.py`
