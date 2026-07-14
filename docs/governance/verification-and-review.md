# 验证与评审

状态：本轮实现。

English summary: Verify build, static checks, architecture, tests, docs, and layer boundaries before merge.

---

## 验证原则

本项目的统一验证入口是：

```bash
bash scripts/check.sh
```

提交前至少完成：

- 查看 diff。
- 检查规范读取路径或代码边界是否受影响。
- 运行 `bash scripts/check.sh`，或说明无法执行的具体原因。

---

## FastAPI 推荐验证项

`bash scripts/check.sh` 覆盖（详见 [check-scripts-spec.md](./check-scripts-spec.md)）：

- 架构测试：`import-linter`（六层依赖边界）。
- 单元测试：`pytest`。
- 契约测试：OpenAPI snapshot 一致性。
- Eval：固定评测集回归（阶段 5 起，通过率阈值 85%）。
- Lint：`ruff` + `mypy --strict`（schemas/services 层）。
- 文档：状态字段、相对链接。

---

## 安全检查

- 是否在日志输出敏感数据（API Key、Token、DFS 密码、完整 prompt、用户敏感记忆）。
- 是否把原始异常栈直接返回给前端。
- 是否存在 SQL 字符串拼接（必须用 SQLAlchemy 参数化）。
- 是否把外部 LLM/Search 结果未脱敏写入长期记忆。
- 是否存在 CORS 通配符。

---

## 代码评审清单

优先检查：

- 是否违反六层依赖边界（api→repository？runtime→ORM model？）。
- 是否把业务规则写在 Router 而非 Service。
- 是否让 Agent / 节点直接写业务表（R-IO2）。
- 是否把节点命名成 `<X>Agent`（R-Agent2）。
- 是否静默吞错（R-Fail1）。
- 是否缺少降级 `fallback_reason`。
- 是否缺少结构化输出校验（Pydantic）。
- 是否修改了 Prompt 但没加版本号（R-Prompt2）。
- 是否把厂商 SDK 对象暴露给上层（R-Layer3）。
- 是否缺少审计点（涉及 LLM 调用 / 高风险分流 / 记忆写入时）。
- 是否缺少领域/节点单测。

---

## 文档评审清单

- 根入口规范读取路径是否指向真实文件。
- docs 文件是否放入正确的 `overview/` / `architecture/` / `model-design/` / `standards/` / `governance/` / `requirements/` / `design-input/` / `third-party-integration/` 一级目录。
- 文档迁移后是否更新 [docs/README.md](../README.md)、[AGENTS.md](../../AGENTS.md)、[ai-reading-guide](./ai-reading-guide.md) 和全部引用路径。
- 是否出现大段重复内容。

---

## 验证报告模板

```text
验证报告
Architecture (import-linter): 通过 / 失败
Tests (pytest): 通过 / 失败
Contracts (OpenAPI snapshot): 通过 / 失败
Lint (ruff + mypy): 通过 / 失败
Eval (阶段 5+): 通过 / 失败 / 跳过
Docs links: 通过 / 失败
Diff review: 通过 / 失败
Overall: Ready / Not ready
```

---

## CI 与合入

- CI 对所有 PR 运行 `bash scripts/check.sh`；`check.sh` 在 CI 中为**硬阻断**（不允许 `allow_failure: true`）。
- AI 生成代码不得绕过 CI；合入标准以 CI 和 review 为准。
