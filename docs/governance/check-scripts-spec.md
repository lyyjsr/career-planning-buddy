# 门禁脚本规范

| 版本 | v1.1 |
|---|---|
| 日期 | 2026-07-24 |
| 状态 | 定稿 |
| 目的 | 定义 `scripts/check*.sh` 的职责，让 AI 协作开发时"无法绕过流程" |
| v1.0 → v1.1 | §3 check-doc-status.sh 修死规则——`docs/0[1-9]_*.md` 是不存在的路径，改为遍历所有 `docs/**/*.md`（排除 design-input 与 scratch）+ 新增 §3.1 例外、§3.2 状态字段阈值 |

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

**职责**：每份正式 spec 文档（非 `design-input/` 归档、非 `requirements/*/scratch/` 实验）含状态字段，让 AI 开发知道哪些是权威可直接施工。

**实现要点**（脚本本身落 `scripts/check-doc-status.sh`，Stage 0 才创建；下面是规则源）：

```bash
#!/bin/bash
# 推荐用 bash（macOS/Linux 通用）。若必须用 POSIX sh：
#   把 `done < <(find ...)` 改成 `find ... | while IFS= read -r f; do ... done`
set -e

# 扫描范围：docs/** 下所有 .md，但排除归档区与实验区
# - design-input/ 已显式标记为"非权威"——跳过
# - requirements/*/scratch/ 是探索区——跳过
# - 各 README.md（入口索引）也须带状态字段

exclude_pattern="docs/design-input/|.*/scratch/"

fail=0

# 注意管道写法：while 在子 shell 里，不能跨管道保留 fail 变量；
# 用临时文件或 grep -L 兜底
find docs -name "*.md" \
    -not -path "$exclude_pattern" \
    | grep -vE "$exclude_pattern" \
    | while IFS= read -r f; do
  # 任一行命中以下任一即视为合规：
  #   | 状态          （spec 表格头部）
  #   | Status        （英文版表格）
  #   | 文档版本       （PRD / ADR 老格式）
  #   状态：          （clarify.md / plan.md / tasks.md SDD 模板格式，含中文冒号）
  #   状态:           （英文冒号兼容）
  if ! grep -qE "^[| ]+(状态|Status|文档版本)|^状态[：:]" "$f" 2>/dev/null; then
    echo "❌ $f 缺少状态字段（应为 | 状态 / | Status / | 文档版本 / 状态：）"
    fail=1
  fi
  # 在子 shell 里 fail 不会传出来——要靠下面 grep -L 兜底
done

# 兜底：grep -L "无匹配" 反向列出缺状态字段的文件
missing=$(find docs -name "*.md" \
              -not -path "docs/design-input/*" \
              -not -path "*/scratch/*" \
              -exec grep -LE "^[| ]+(状态|Status|文档版本)|^状态[：:]" {} \;)
if [ -n "$missing" ]; then
  echo "$missing" | sed 's/^/❌ /;s/$/ 缺少状态字段/'
  exit 1
fi

exit 0
```

**守护规则**：文档必须显式标 `状态：定稿/草稿/废弃/本轮实现/规划中/已实现`（任一形态任一语言均可），让 AI 开发得以判断 "这是可直接施工的真理源" 还是 "半成品/实验产物"。

### 3.1 例外与豁免

- **`design-input/` 全部豁免**：归档位置，已由 [`design-input/README.md`](../design-input/README.md) 显式声明"非事实来源"。本目录所有 spec 状态无意义。
- **`requirements/<feature>/scratch/` 豁免**：实验产物，不并入主干。
- **`.mmd` 图表文件豁免**：mermaid 文件无表头需求。

### 3.2 阈值约定（与 [`spec-driven-workflow.md`](./spec-driven-workflow.md) §状态字段流转对齐）

| 值 | 何时标 |
|---|---|
| `规划中` | spec/plan 在写但未到可施工状态 |
| `草稿` / `本轮实现` | 施工中（典型 SDD 推进态） |
| `定稿` | 真理源稳定，AI 可照抄写代码 |
| `废弃`（或 `_status=deprecated`）| 已被取代，仅作历史档案（通常应迁 `design-input/`）|

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
