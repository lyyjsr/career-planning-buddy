# 新增用例开发 Checklist

状态：本轮实现。

English summary: Use this checklist when adding a new use case (API / node / feature) so layers, schemas, tools, providers, security, and tests are handled consistently.

> **规则覆盖**：每节末尾的 `[Enforced-by ...]` 标注映射到 [AGENTS.md](../../AGENTS.md) 的 Non-Negotiable Rules（`R-*` 规则 ID）与对应机器门禁（import-linter / ruff / mypy / scripts/check-*.sh）或 `manual review`。

---

## 0. 开发前确认

- [ ] 已确认所属逻辑模块（建档/规划/任务/复盘/记忆/来源/Agent Runtime）。
- [ ] 已确认用例类型：命令（写）、查询（读）、Agent 节点、Tool、Provider、组合流程。
- [ ] 已读 [development-workflow](./development-workflow.md)、[python-coding-standards](../standards/python-coding-standards.md)、[security-and-compliance](../standards/security-and-compliance.md)、[testing-and-tdd](../standards/testing-and-tdd.md)。
- [ ] 涉及节点设计时，已确认 [spec-writing-guide](../standards/spec-writing-guide.md)。

[Enforced-by: 文档读取 = manual review]

---

## 1. 文件落位

- [ ] Router、错误映射放 `app/api/`。
- [ ] Pydantic schema、枚举、错误码放 `app/schemas/`。
- [ ] Service、状态机、用例编排放 `app/services/`。
- [ ] Repository 接口与实现放 `app/repositories/`，ORM Model 放 `app/models/`。
- [ ] Agent graph、节点、harness 放 `app/agent/`；Tools 放 `app/tools/`。
- [ ] Provider Protocol 与实现放 `app/providers/`。
- [ ] Prompt 模板放 `app/prompts/{goal_type}/`（带版本号）。
- [ ] 配置、Feature Flag 放 `app/core/`。

[Enforced-by: R-Layer1/R-Layer2/R-Layer3（import-linter 禁止越层）]

---

## 2. Schema 契约

- [ ] 所有对外 schema 用 Pydantic，`model_config = ConfigDict(extra="forbid")` 或显式 `extra="allow"`。
- [ ] 必填字段标注 `...`，可选字段有默认值。
- [ ] LLM 结构化输出有对应 Pydantic 模型（structured output）。
- [ ] OpenAPI 自动生成 + snapshot 入 Git（阶段 1 起）。
- [ ] 破坏性变更必须显式更新 snapshot。

[Enforced-by: R-Contract1/R-Contract2 + manual review；CI check-contracts.sh]

---

## 3. Agent 节点

- [ ] 节点有对应的 `model-design/agent-nodes/<node>.spec.md`（六要素齐全）。
- [ ] **真 Agent 只有 1 个**（CareerPlanningAgent）；其余节点不命名成 `<X>Agent`。
- [ ] 节点只调只读 Tool，不直接写业务表。
- [ ] 循环受预算约束（≤2 轮、≤4 次工具调用）。
- [ ] 失败路径显式列出（超时/超预算/schema 不符 → degrade/fail）。

[Enforced-by: R-Agent1/R-Agent2/R-IO1/R-IO2 + manual review]

---

## 4. Tool 与 Provider

- [ ] Tool 用 Protocol 接口，实现注入，不走硬编码 HTTP。
- [ ] Tool 调用走 harness 包装（限流/超时/可观测）。
- [ ] Provider 不向上暴露厂商特有响应对象（.Protocol 返回标准化结构）。
- [ ] Mock 实现必须通过同一 ToolSpec/Provider 契约测试。
- [ ] 日志只记摘要（invocationId/traceId/错误码），不记完整 prompt/密钥。

[Enforced-by: R-Layer2/R-Layer3 + import-linter + manual review]

---

## 5. 安全与审计

- [ ] 涉及 LLM 调用、记忆写入、高风险分流时，设计阶段同时设计审计点。
- [ ] 敏感记忆默认不写入 → candidates 池 → 用户确认。
- [ ] 高风险分流（关键词 + LLM 分类器）→ 固定话术 + 12356。
- [ ] 日志不输出 API Key、完整 prompt、用户敏感原文。
- [ ] Prompt 注入防护：工具结果包 `<evidence>`，不进 System Message。

[Enforced-by: R-Safety1/R-Safety2 + manual review]

---

## 6. 测试要求

- [ ] schemas：Pydantic 校验单测（必填/extra forbid/枚举边界）。
- [ ] services：用例与状态机单测（含非法状态转移）。
- [ ] repositories：testcontainers postgres 测 CRUD。
- [ ] agent：每个节点用 Mock Provider 测 happy/fail/降级。
- [ ] api：FastAPI TestClient 测成功 / 校验失败 / 未认证 / 错误码。
- [ ] providers：Mock 与真实实现共享同一契约测试。
- [ ] eval（阶段 5+）：30 case 自动评测通过率 ≥ 85%。

[Enforced-by: 文档读取 + CI；ruff/mypy 由 check.sh 调度]

---

## 7. 禁止事项

- [ ] 禁止 Router 直接调 Repository、ORM 或外部 HTTP。
- [ ] 禁止 `app/agent/` 依赖 `app/models/`（ORM 越层）。
- [ ] 禁止 Agent / 节点直接写业务表。
- [ ] 禁止把厂商 SDK 对象返回给 schemas/api。
- [ ] 禁止静默吞错。
- [ ] 禁止修改 Prompt 不加版本号。
- [ ] 禁止 MVP 阶段引入 Redis/Celery/K8s（除非触发 ADR-001 演进条件）。
- [ ] 禁止把节点命名成 `<X>Agent`。

[Enforced-by: R-Layer1 + import-linter + R-Agent2 + R-Fail1 + manual review]

---

## 8. 提交前

- [ ] 已运行 `pytest` 对应模块。
- [ ] 已运行 `bash scripts/check.sh`，或说明无法执行的具体原因。
- [ ] 已确认没有敏感信息进入日志、配置、测试数据。
- [ ] 已确认文档同步更新 [docs/README.md](../README.md) 与 [AGENTS.md](../../AGENTS.md)。
- [ ] 已确认未提交 AI 临时测试文件或无关格式化改动。

[Enforced-by: R-Plan1（check-plan.sh）；门禁 = `bash scripts/check.sh`]
