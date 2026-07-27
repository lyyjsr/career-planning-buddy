# ui-spec/ — 前端 UI 交互 spec 目录入口

| 版本 | v1.0 |
|---|---|
| 日期 | 2026-07-26 |
| 状态 | 本轮实现——目录入口已建；5 份用户页面 spec 待补 |

---

## 1. 定位

把 [PRD §9.1](../../overview/product-overview.md#9-非功能需求) 声明的 **MVP 5 个用户前端页面 + 1 个开发者页面**逐页展开为前端交互 spec，给前端编码或 AI 拼装 shadcn/ui 提供约束。

本目录**只写交互 spec**——信息架构、关键交互、4 态（空/载/错/成功）、API 关联、组件建议；**不写视觉**（颜色/字体/间距/shadcn 默认 + 前端工程师审美）。

## 2. 与相邻目录的边界

| 邻居 | 边界 |
|---|---|
| [api-spec/](../api-spec/) | 是数据契约（请求/响应 schema）；本目录是页面交互——引用 api-spec，不重写字段 |
| [agent-nodes/](../agent-nodes/) | 是节点行为字段级 spec；本目录只关心"页面如何消费节点的输出" |
| [state-machines/](../state-machines/) | 是状态机合法性表；本目录把"状态变化"翻译为"用户看到的 UI 反馈" |
| `standards/prompts/` | prompt 是后端迭代物；前端不进 spec |

## 3. 全局约定（所有用户页面共享）

### 3.1 技术栈（来自 [ADR-001](../../architecture/adr.md)）

- **React 18 + TypeScript**
- **Vite** 构建
- **shadcn/ui + Tailwind CSS**（组件库，AI 拼装友好的默认审美）
- **TanStack Query** 数据层（缓存 + 失效 + 乐观更新）
- 路由：**React Router v6**

### 3.2 4 态（每页必须实现）

| 态 | 表现 | 数据来源 |
|---|---|---|
| **空态** | `EmptyState` 组件 + 引导文案（不放搞笑插图） | API 返 list 为空 |
| **加载态** | `Skeleton` 占位（首次）/ `Spinner` 角标（刷新） | `isLoading` from TanStack Query |
| **错误态** | `ErrorState` + 重试按钮 + 不兜底 | API 4xx/5xx |
| **成功态** | 数据展示 | API 返正常 |

### 3.3 全局组件

- `<Header>` 含 logo + 路由切换
- `<CompanionToast>` 全局陪伴话术浮层（订阅 SSE `companion.message` 事件）
- `<RiskGateModal>` 高风险分流弹层（响应 `risk_category` 字段，固定话术 + 12356）

### 3.4 不做的事

- ❌ 无 PWA、无 mobile app（[ADR-001](../../architecture/adr.md) MVP 只 Web）
- ❌ 无 SSR（单页应用）
- ❌ 无多语言（中文单语）
- ❌ 无主题切换（shadcn light 默认）
- ❌ 无骨架动画（避免 demo 味）

## 4. 待补清单（MVP 范围）

| # | 页面 | 路由 | API spec | UI 组件建议 | spec 状态 |
|---|---|---|---|---|---|
| 0 | **产品导航与页面使用流** | 全局 | [`/api/v1/me`](../api-spec/profile.md) + 各页面 API | PC/移动端导航、主路径、状态映射 | ✅ [product-navigation.md](./product-navigation.md) |
| 1 | **今日任务页** | `/today` | [`/api/v1/tasks/today`](../api-spec/tasks.md) | `TaskCard` ×N + "开始/完成/放弃"操作 + optimism 乐观更新 | ❌ 待写 |
| 2 | **规划对话页** | `/chat` | [`/api/v1/agent-runs`](../api-spec/agent-runs.md) + [`SSE`](../../architecture/api-and-data-contracts.md#7-sse-事件协议) | `ChatInterface` + 消息流 + 工具调用气泡 + `companion.message` 浮层 | ❌ 待写 |
| 3 | **任务列表页** | `/tasks` | [`/api/v1/tasks`](../api-spec/tasks.md) | `DataTable` + 状态/日期筛选 + 详情抽屉 | ❌ 待写 |
| 4 | **每日复盘页** | `/reviews/new` | [`/api/v1/reviews`](../api-spec/reviews.md) + [`/reviews/:id/accept-replan`](../api-spec/reviews.md) | `Form` + Stepper（情绪/阻碍/完成/调整）+ `suggested_replan` 确认 | ❌ 待写 |
| 5 | **记忆管理页** | `/memories` | [`/api/v1/memories`](../api-spec/memories.md) + [`/api/v1/memory-candidates`](../api-spec/memories.md) | `MemoryList` + Active/Closed 切换 + `CandidateList`（敏感候选确认/拒绝） | ❌ 待写 |
| — | 开发者 Trace 页 | `/dev/traces` | [`/api/v1/dev/runs`](../api-spec/dev-runs.md) | 见 [developer-trace.md](./developer-trace.md) | ✅ 已写 |
| — | "次日续上"聚合页 | `/` (首页) | [`/api/v1/me`](../api-spec/profile.md)（active_plan + today_tasks + 昨日 review） | `SummaryCard` + 一键继续 | ❌ 待写（轻量级） |

## 5. 每页 spec 该有的章节（模板）

新建 `<page>.md` 时按此 7 节结构写（参考 [developer-trace.md](./developer-trace.md) 现成范例）：

```markdown
# <页面名>

## 1. 定位
### 1.1 是什么
### 1.2 不是什么
### 1.3 路由

## 2. 信息架构
- 区块图（mermaid 或 ASCII）
- 每区块对应 API 字段

## 3. 关键交互（流程时序）
- mermaid sequenceDiagram
- 用户/前端/API/Backend 的来回

## 4. 4 态（空/载/错/成功）表现
| 态 | 表现 |

## 5. 数据契约引用
- 引用 api-spec/*.md（不重写字段）

## 6. 交互细节
- 表单校验、乐观更新、SSE 处理、轮询、超时...

## 7. 不做（边界声明）
- 列出"看起来该做但本期不做"的项
```

## 6. 编码顺序（与 [stage-delivery-definition.md](../../governance/stage-delivery-definition.md) 对齐）

| 顺序 | 页面 | 阶段 | 理由 |
|---|---|---|---|
| 1 | developer-trace.md（已完成） | Stage 5 | 工程化基础，验证 SSE + trace 表 |
| 2 | today.md | Stage 6 前半 | MVP 核心——用户每天打开第一页 |
| 3 | chat.md | Stage 6 中段 | 紧接 today，是"开始规划"入口 |
| 4 | reviews.md | Stage 6 后段 | 闭环——计划→执行→复盘 |
| 5 | tasks.md | Stage 7 | P1 用户次要页 |
| 6 | memories.md | Stage 7 | P1 用户次要页 |
| 7 | home.md（次日续上） | Stage 7 | 轻量级聚合页 |

## 7. 写 spec 前的"原型"建议

Spec 是文字约束，**不能替代视觉**。建议在写 spec 前先用以下任一方式产出**低保真原型**：

| 方案 | 工时 | 适用 |
|---|---|---|
| **Excalidraw 手绘 wireframe** | 半天/5 页 | 决策"页面有什么/不放什么" |
| **Figma 低保真** | 1 天/5 页 | 同上 + 团队评审 |
| **v0.dev / Lovable AI 直出** | 2 小时 | 拼装 shadcn 默认形态作起点（视觉可改） |

**spec ↔ 原型的分工**：

- 原型回答「这一页**长什么样**」（视觉骨架）
- spec 回答「这一页**怎么交互、连什么 API、4 态怎么表现**」（行为契约）

两者**互补不替代**。建议流程：原型先画 → spec 复用原型的区块命名 → 后端按 spec 实现。

## 8. 与 Codex / Cursor / Figma 工具链的对接

详见 [../../requirements/frontend-tooling-research/README.md](../../requirements/frontend-tooling-research/README.md)（如已建）；否则此节保留为占位——后续会单独调研"Figma → Codex/Cursor → React 代码"工作流是否适配本项目。

---

## 当前状态

| 维度 | 状态 |
|---|---|
| 目录入口（README） | ✅ 本文件 |
| 用户页面 spec | ❌ 0/5 待补 |
| 开发者页面 spec | ✅ 1/1 已完成 |
| 原型图 | ❌ 0 份 |
| 与 Figma 对接调研 | ❌ 待做 |

下一步动作（按优先级）：
1. 决定是否补 5 页 Figma 原型（如走秋招作品 → 必补）
2. 按"编码顺序"逐页写 `<page>.md` spec（每页约 200 行）
3. 在 `requirements/` 落 spec-driven 三件套（如新增页面）

---

*本文档是 ui-spec 目录入口；具体页面 spec 见同目录 `<page>.md` 文件。`ui-spec/` 目录的定位与边界见 [model-design/README.md](../README.md)。*
