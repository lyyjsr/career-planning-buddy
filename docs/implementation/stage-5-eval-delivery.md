# Stage 5：Trace、Eval 与工程交付

## 目标

把项目做成可演示、可评测、可复现的秋招作品。

## 实现范围

1. 开发者 Run 列表与详情；
2. Trace 树：节点、模型、Tool、Token、耗时、错误；
3. 30 条 JSONL 固定 Eval Case；
4. 规则 Grader：意图、任务数量、时间预算、可启动性、可验证性、来源；
5. Bad Case 回流；
6. Docker Compose 一键启动；
7. CI：lint、type check、test、migration、eval smoke；
8. README 截图、Demo、真实测试结果。

## Replay 范围

MVP Replay 只支持：

- 复制原始输入；
- 指定新的 prompt_version 或 model；
- Tool 使用保存的 fixture；
- 对比输出和指标。

不承诺对真实网络搜索的完全确定性重放。

## 验收

- 30 case 可一条命令运行；
- 报告包含通过率、失败原因、平均耗时、平均成本；
- 核心场景通过率达到项目设定阈值；
- Docker Compose 从空环境可启动；
- 3~5 分钟 Demo 可完整走通建档、规划、任务、复盘和重规划。
