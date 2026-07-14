# 门禁脚本规范

| 版本 | v1.0 |
|---|---|
| 日期 | 2026-07-11 |
| 目的 | 定义 `scripts/check*.sh` 的职责，让 AI 协作开发时"无法绕过流程" |

---

## 总入口：`scripts/check.sh`

```bash
#!/bin/bash
set -e
echo "=== 架构测试 ==="
./scripts/check-architecture.sh
echo "=== 契约测试 ==="
./scripts/check-contracts.sh
echo "=== 文档状态 ==="
./scripts/check-doc-status.sh
echo "=== 文档链接 ==="
./scripts/check-doc-links.sh
echo "=== 评测回归 ==="
./scripts/check-eval.sh
echo "=== 全部通过 ==="
```

CI 中 `scripts/check.sh` 必须为硬阻断——**不允许 `allow_failure: true`**。

---

## 1. check-architecture.sh

**职责**：跑 `import-linter`，守护六层依赖方向。

**实现要点**：
```bash
#!/bin/bash
set -e
cd backend
import-linter --config .importlinter.toml
```

`.importlinter.toml` 关键规则：

```toml
[importlinter]
root_package = app

[importlinter:contract:six-layers]
name = 六层依赖
type = layers
layers =
    app.api
    app.services
    app.agent
    app.tools
    app.repositories
    app.schemas
    app.core

[importlinter:contract:providers-isolation]
name = Providers 不向上暴露厂商对象
type = forbidden
source_modules = app.providers
forbidden_modules = app.api, app.services, app.agent
```

**守护规则**：
- api 不依赖 repositories（越层）
- agent 不依赖 models（ORM 越层）
- providers 不暴露 vendor-specific 响应对象给上层

**失败退出码**：非 0，CI 阻断。

---

## 2. check-contracts.sh

**职责**：Pydantic 自动生成的 OpenAPI 与 Git 中的 snapshot 一致。

**实现要点**：
```bash
#!/bin/bash
set -e
cd backend
python -m app.api.openapi_gen > /tmp/current_openapi.json
diff tests/contracts/openapi_snapshot.json /tmp/current_openapi.json
if [ $? -ne 0 ]; then
  echo "OpenAPI snapshot 不一致——请更新 tests/contracts/openapi_snapshot.json"
  exit 1
fi
```

**守护规则**：
- 任何破坏性变更必须显式更新 snapshot
- 兼容性变更（新增字段）允许通过

---

## 3. check-doc-status.sh

**职责**：每份正式文档（非 design-input）含状态字段。

**实现要点**：
```bash
#!/bin/bash
set -e
for f in docs/0[1-9]_*.md docs/governance/0[1-9]_*.md; do
  if ! grep -q "^| 状态" "$f" 2>/dev/null && ! grep -q "^| 文档版本" "$f" 2>/dev/null; then
    echo "$f 缺少状态字段"
    exit 1
  fi
done
```

**守护规则**：文档必须显式标 `状态：定稿/草稿/废弃`，让 AI 开发知道哪些是权威。

---

## 4. check-doc-links.sh

**职责**：文档内的相对链接（`./xxx.md` / `../xxx.md`）指向真实存在的文件。

**实现要点**：
```bash
#!/bin/bash
set -e
cd docs
# 用 markdown-link-check 或自写脚本
find . -name '*.md' -exec markdown-link-check --quiet --config .linkcheck.json {} +
```

**守护规则**：重命名/移动文件时必须同步更新链接，防止 AI 看到断链乱猜。

---

## 5. check-eval.sh

**职责**：固定评测集回归——确保 Prompt/工作流改动不破坏质量。

**实现要点**：
```bash
#!/bin/bash
set -e
cd backend
pytest tests/eval/ -v --eval-dataset=defaults
```

**守护规则**：
- 评测通过率 <85% 时阻断
- 评测报告含每个 case 的 5 维质量评分
- 失败 case 列入 Bad Case 看板

---

## 6. 其他脚本（非阻断）

| 脚本 | 职责 | 使用时机 |
|---|---|---|
| `scripts/seed-experience-atoms.py` | 把整理的经验原子导入 DB | 阶段 4 |
| `scripts/seed-eval-dataset.py` | 导入评测集 | 阶段 5 |
| `scripts/show-trace.sh <run_id>` | 查看指定 run 的完整 Trace | 开发调试 |
| `scripts/replay.sh <run_id>` | 重放指定 run（同 Prompt 版本） | Prompt 迭代 |
| `scripts/gen-openapi-snapshot.sh` | 重新生成 OpenAPI snapshot | 故意变更契约时 |

---

## Git Hooks（可选）

`.git/hooks/pre-push`：

```bash
#!/bin/bash
./scripts/check.sh
```

每次 push 前自动跑全部门禁——AI 和人都无法绕过。

---

## 失败处理

| 场景 | 处理 |
|---|---|
| 架构测试失败 | 必须修复跨层依赖，不允许调整 import-linter 规则放宽 |
| 契约不一致 | 必须审视是破坏性变更还是 bug；破坏性变更更新 snapshot |
| 评测回归 | 必须修复或显式登记为"已知回归 + 修复计划" |
| 文档状态缺失 | 补上状态字段 |

**严禁操作**：
- 把 check.sh 在 CI 里设 `allow_failure: true`（AIGOV P-02 教训）
- 把 import-linter 规则注释掉绕过
- 把 eval 通过率阈值降低到 85% 以下
