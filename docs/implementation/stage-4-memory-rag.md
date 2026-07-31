# Stage 4：记忆、搜索与 RAG

## 目标

让规划使用用户长期信息和可追踪证据，而不是只靠单轮 Prompt。

## 实现范围

- memories、memory_candidates；
- search_sources、experience_atoms；
- SearchProvider、EmbeddingProvider；
- Tool：memory_lookup、web_search、rag_retrieve；
- context_builder 组合画像、近期任务、复盘、记忆和证据；
- 来源在计划详情中展示；
- 敏感记忆必须进入候选池，用户确认后才能激活。

## 约束

- Embedding 维度由 `EMBEDDING_DIM` 与迁移共同锁定；
- 不把整段网页直接塞给主模型，先清洗、截断和结构化；
- 搜索结果必须保存 URL、标题、摘要、检索时间和可信度；
- 高风险输入不写长期记忆；
- Tool 每次调用都有超时、参数 hash 和结果 hash。

## 验收

- 记忆的查看、关闭、恢复、删除可用；
- 敏感候选确认/拒绝可用；
- RAG 检索能按 user_id、goal_type 过滤；
- 计划详情展示来源；
- Search 或 Embedding 失败时仍能用本地经验库或模板完成基础规划。
