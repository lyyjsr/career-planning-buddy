# 功能与契约对齐结论

原 v0.2 审查中记录的主要冲突已在 v3.0 设计包收敛。当前事实：

| 问题 | 收敛结果 |
|---|---|
| 是否基于 ClawAgent | 否，独立项目 |
| 编码助手与运行时模型混淆 | 已分离；Codex 负责开发，运行时由 Provider 配置 |
| DeepSeek V4 项目代号 | 从权威文档移除 |
| 五类空壳 Provider | 收敛为 LLM/Search/Embedding 三类 |
| Plan 状态含义混乱 | generated/active/completed/archived；adopted_at 为时间字段 |
| Profile stage 三套枚举 | exploring/preparing/applying/interviewing |
| Review 重复传任务事实 | 删除 task id 列表，由 Service 从数据库计算 |
| SSE 声称重连但无事件表 | 新增 agent_events |
| Last-Event-ID 语义 | sequence 单调递增并持久化 |
| 多 Worker 能力夸大 | 明确 MVP 单 Worker 和重启限制 |
| Guest 登录伪 OAuth token | 改为 /auth/guest + device hash |
| 11/12 节点计数冲突 | 10 核心 + 2 增强 |
| 结构化输出无限修复 | 最多一次修复 |
| 搜索 URL 可由模型生成 | 只能引用已保存 source id |
| 硬编码安全资源 | 改为集中配置并人工审核 |
| 外部 DaZi 代码链接 | 移除，全部以本仓库未来路径描述 |

剩余非阻塞事项：真实模型 smoke、UI 视觉稿、30 条 Eval Case 和实际代码实现。
