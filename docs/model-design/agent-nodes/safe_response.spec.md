# safe_response.spec.md — 安全响应节点

状态：本轮实现。

## 0. 节点定位

| 维度 | 内容 |
|---|---|
| 中文名 | 安全响应节点 |
| 类型 | 程序节点（不调 LLM，纯固定话术） |
| 工作流位置 | risk_gate 触发 high 风险时直接路由到此 → END |
| 责任 | 输出固定话术 + 12356 援助信息；不入长期记忆 |

## 1. 输入 Schema

`app.schemas.risk.SafeResponseInput`

| 字段 | 类型 | 必填 |
|---|---|---|
| `user_id` | `str` | ✅ |
| `run_id` | `str` | ✅ |
| `risk_level` | `Literal["high"]` | ✅ |
| `risk_category` | `Literal["mental_health","legal","financial","self_harm","other"]` | ✅ |

## 2. 输出 Schema

`app.schemas.risk.SafeResponse`

固定结构：

| 字段 | 类型 | 说明 |
|---|---|---|
| `message` | `str` | 固定话术（按 risk_category 选） |
| `hotline` | `str` | `"12356 全国心理援助热线"` |
| `additional_resources` | `list[str]` | 1-2 个权威 URL |
| `risk_logged` | `bool` | True（监控标记） |

## 3. 固定话术模板（每风险类别一条）

文件：`core/safe_responses.py`

| risk_category | 话术示例（节选） |
|---|---|
| mental_health | "我注意到你可能正在经历困难时刻。你的感受是真实的，不孤单..." |
| self_harm | "如果你有伤害自己的念头，**请立即拨打 12356 或 110**。" |
| legal/financial | "我无法在法律/财务上给出准确建议，请咨询专业机构。" |
| other | "你的情况可能需要专业帮助..." |

## 4. 不变量

| ID | 不变量 |
|---|---|
| INV-1 | `risk_logged == True`（必须监控标记） |
| INV-2 | 不写入长期记忆（强制不写 memories 表） |
| INV-3 | 必须包含 `12356` 字符串 |
| INV-4 | 话术不经 LLM 生成（避免意外的"安抚式忽略"） |

## 5. 错误边界

无错误降级（最末节点）。任何异常 → 仍返固定兜底话术 + 监控标记。

## 6. 状态机

无；路由到此即终止 workflow。

## 7. 依赖

| 依赖 | 用途 |
|---|---|
| 配置 | `core/safe_responses.py`（5 类话术） |
| 写 Trace | 1 行（带 `risk_category`） |
| 监控服务 | 后台异步推送告警给运营（TODO，阶段 6） |

## 8. Trace 字段

| 字段 | 示例 |
|---|---|
| `node_name` | `"safe_response"` |
| `risk_category` | `"mental_health"` |
| `hotline_provided` | `"12356"` |

## 9. 实现顺序

1. `schemas/risk.py` 加 SafeResponseInput + SafeResponse
2. `core/safe_responses.py` 5 模板
3. `agent/nodes/safe_response.py`
4. `tests/agent/test_safe_response.py` 5 case（每类一个 + INV-* 验证）

## 10. 引用

- [ADR-006 记忆不写入](../../architecture/adr.md)
- [PRD §风险场景](../../overview/product-overview.md)
- [security-and-compliance.md §1 高风险分流](../../standards/security-and-compliance.md)
