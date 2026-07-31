# distill_evidence — 证据整理

Stage 4 增强节点。将 SearchProvider 返回的来源清洗为可检索的经验候选。

## Input

run_id、goal_type、1~10 个 SearchSource。

## Output

最多 5 个 EvidenceAtomCandidate：title、content、evidence、goal_type、reliability。

## 约束

- URL 必须来自输入来源；
- 冲突来源同时保留并标注；
- 不直接写 experience_atoms，交给 EvidenceService 审核/持久化；
- 不在 plan run 主路径中强制等待入库；
- 来源质量不足时返回空列表，不编造。
