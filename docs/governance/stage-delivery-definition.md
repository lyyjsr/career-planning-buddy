# 阶段化交付定义

| 版本 | v1.0 |
| 状态 | 定稿 |
|---|---|
| 日期 | 2026-07-11 |
| 目的 | 替代时间表——按"完成定义"驱动开发，不按"做到第 X 周" |

---

## 核心原则

- **不绑时间**：每阶段的退出条件达标才进下一阶段；预估时长仅供参考
- **退出条件可验证**：每个退出条件是具体的、可运行/可检查的产物
- **不达条件不进下一阶段**：宁可慢，不要把债务带进下阶段
- **例外**：发现 spec 错了可以先改 spec 再前进，但必须显式记录

---

## 8 个阶段

### 阶段 0：工程基线

**目的**：在写业务代码前，把规则/骨架/门禁铺好。

**退出条件**：
- [ ] 仓库初始化（frontend/backend/docs/scripts/infra 目录）
- [ ] FastAPI 空骨架可启动（`/health` 返回 200）
- [ ] React 空骨架可启动（首屏显示标题）
- [ ] PostgreSQL 容器可起 + Alembic 初始化
- [ ] import-linter 配置就位 + 架构测试绿色
- [ ] `scripts/check.sh` 总入口可运行
- [ ] `docs/` 目录结构就位（含 design-input 归档）
- [ ] `.env.example` + `.gitignore` 完成
- [ ] `README.md` 含启动方式

**预估**：1-2 天

---

### 阶段 1：契约冻结

**目的**：把 PRD/TDD/API 转化为可执行的契约（OpenAPI + Pydantic + DB Schema + 状态机）。

**退出条件**：
- [ ] 所有 Pydantic Schema 落地（UserProfile/Plan/Task/Memory/Agent Run/Step 等）
- [ ] OpenAPI 自动生成 + snapshot 入 Git
- [ ] 所有Alembic 迁移就位（对应 TDD 第 11 章）
- [ ] 状态机用 Python 枚举 + 校验函数实现
- [ ] 所有 Provider Protocol 定义（LLM/Search/Embedding/Cache/Storage）
- [ ] 契约测试通过（Mock Provider 通过同一测试集合）

**预估**：2-3 天

---

### 阶段 2：纵切骨架（Mock）

**目的**：跑通端到端 1 次 plan_run，全链路用 Mock。

**退出条件**：
- [ ] LangGraph 工作流图就位（全部节点串通）
- [ ] 每个节点用 Mock 实现（MockLLMProvider 返回预定义响应）
- [ ] FastAPI 路由：POST `/api/v1/agent-runs` 返回 202
- [ ] SSE 推送事件流（`run.created` → `run.completed`）
- [ ] 前端 5 页面骨架 + 对话页发消息 + 展示规划结果（用 Mock 数据）
- [ ] PostgreSQL 落库：agent_runs/agent_steps/plans/tasks 写入正常
- [ ] Trace 开发者页面可查看 Mock run 的 step 详情

**预估**：3-5 天

**关键纪律**：Mock 链路没跑通，绝对不接真实模型。

---

### 阶段 3：真实模型注入

**目的**：用真实 LLM 替换 Mock，验证 Agent 质量。

**退出条件**：
- [ ] DeepSeek V4 Provider 接入
- [ ] CareerPlanningAgent 可自主调 web_search / rag_retrieve（Mock 版本即可）
- [ ] intent_router 真实分类，置信度阈值生效
- [ ] 5 维质量评分（rule_validator + quality_reviewer）跑通
- [ ] 重写 ≤2 / 降级模板路径全部验证
- [ ] 1 个垂直场景（AI/后端/Agent 求职）3 个 case 跑通，Trace 完整
- [ ] 单 run 成本统计可查（Token + cost_cny）

**预估**：3-5 天

---

### 阶段 4：证据增强

**目的**：接入真实 Web Search + RAG，经验原子上线。

**退出条件**：
- [ ] Tavily SearchProvider 接入
- [ ] pgvector 索引就位 + RAG Retriever 可用
- [ ] 经验原子库 30-50 条上线（手工录入，覆盖 AI/后端/Agent 三方向）
- [ ] search_sources 表写入完整来源 + summary
- [ ] distill_evidence 节点把来源整理为 experience_atoms
- [ ] 前端来源标注展示（URL + 可靠度 + 来源类型）
- [ ] 通用场景（goal_type=other）跑通兜底路径（坦诚告知 + 通用建议）

**预估**：3-5 天

---

### 阶段 5：Harness 完成

**目的**：完成 Trace/Replay/Eval 三大工程能力。

**退出条件**：
- [ ] Trace 字段完整（含 prompt_version / model_name / tool_calls / token / cost）
- [ ] Replay 页面可用（选 run → 同输入重跑 → 展示差异）
- [ ] Eval 系统可用（30 case 固定数据集 + 自动 grader + 报告）
- [ ] Bad Case 修复闭环（失败 run 一键加入评测集）
- [ ] 故障注入测试通过（LLM/Search/DB 失败均能降级）
- [ ] 1 个垂直场景评测通过率 ≥ 85%

**预估**：3-5 天

---

### 阶段 6：产品完整度

**目的**：覆盖产品 PRD 的全部产品功能。

**退出条件**：
- [ ] 5 维质量评分全维度生效
- [ ] 复盘-调整双层规则（规则驱动 + Agent 驱动）全部触发路径验证
- [ ] 陪伴 6 触发时刻全部实现（companion_response 节点）
- [ ] 安全分流（高风险关键词 + LLM 分类器 + 固定话术 + 12356）
- [ ] 记忆管理全部功能（查看/删除/关闭/敏感确认候选池）
- [ ] 次日续上（基于昨日完成情况自动调整今日任务）
- [ ] 流失路径产品策略全部实现（次日续接卡片 / 回归欢迎语）
- [ ] 端到端 4 个示例 Payload（来自 API 文档第 12 章）跑通

**预估**：4-6 天

---

### 阶段 7：工程交付

**目的**：达到"可发布作品"标准。

**退出条件**：
- [ ] Docker Compose 一键起（fastapi + postgres + caddy）
- [ ] CI 全绿（pytest + import-linter + 契约测试 + eval 回归）
- [ ] `README.md` 含项目介绍/架构图/启动方式/Demo 链接
- [ ] API 文档自动生成且可访问（`/docs`）
- [ ] 结构化日志上线（structlog JSON 输出）
- [ ] 错误码完整（AUTH/VALIDATION/STATE/AGENT/FALLBACK）
- [ ] 5 个核心页面 UI 完整（不是骨架）
- [ ] `.env.example` 完整 + 密钥无硬编码

**预估**：3-5 天

---

## 阶段 8（可选）：作品包装

**目的**：秋招作品化。

**退出条件**：
- [ ] 简历素材整理（每个亮点配数据/截图）
- [ ] Demo 视频录制（3-5 分钟）
- [ ] 1 篇技术博客大纲
- [ ] 面试讲故事脚本（"为什么单 Agent"、"为什么 FastAPI"、"5 维评分怎么设计的"）

---

## 进度追踪

| 阶段 | 状态 | 备注 |
|---|---|---|
| 0 工程基线 | ⬜ 未开始 | 📍 下一步 |
| 1 契约冻结 | ⬜ | |
| 2 纵切骨架 | ⬜ | |
| 3 真实模型 | ⬜ | |
| 4 证据增强 | ⬜ | |
| 5 Harness | ⬜ | |
| 6 产品完整 | ⬜ | |
| 7 工程交付 | ⬜ | |
| 8 作品包装 | ⬜ | |

---

## 重要纪律

1. **Mock 链路不过不接真实模型**（防止错误叠加难调试）
2. **评测不过不上线新 Prompt**（防止回归）
3. **退出条件不达标不进下一阶段**（宁可慢不要债）
4. **发现 spec 错了先改 spec**（不要在代码里绕过 spec）
