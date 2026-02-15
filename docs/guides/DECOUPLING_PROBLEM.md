# DECOUPLING_PROBLEM: Problem 该负责什么

你写 `problem.evaluate(x)` 的那一刻，其实就决定了后面所有算法是否“好用”。

这一页的目标：让你清楚什么应该放进 Problem，什么不应该放进去，以及为什么这样拆能让你更快落地新点子/新约束/新实验口径。

## Problem 的职责（应该做）

- 定义决策变量空间：`bounds`、维度、变量含义
- 定义目标：单目标/多目标的 `objectives`
- 定义硬约束（可选）：返回约束违规度（推荐 `g(x) <= 0` 为可行）
- 保持评估口径稳定：同一个 `x` 在同一环境下评估结果可预期

你可以把 Problem 理解为：“给定一个候选解 x，现实世界给你一个反馈 f(x)”。

## Problem 的非职责（不建议做）

这些事情“能做”，但会让你后期更难并行、更难复用、更难对比：

- 在 `evaluate()` 里写文件/画图/打印大量日志
- 在 `evaluate()` 里维护全局状态（计数器/缓存/随机数源）并影响返回值
- 在 `evaluate()` 里做并行/调度（能力层应该交给 Plugin）
- 在 `evaluate()` 里做可行性修复（硬约束优先放到 `RepresentationPipeline`）

## 为什么要这样拆（你一定会遇到的场景）

- 你想换算法/做融合：Problem 不动，才能复用同一问题口径
- 你想并行评估：`evaluate()` 越纯，越不容易被多进程搞炸
- 你想做对比实验：输出口径/统计口径应该交给 Plugin，而不是混进评估里

## 你应该从哪里开始

- 端到端流程：`WORKFLOW_END_TO_END.md`
- 统一口径输出（建议默认挂）：`plugins/ops/benchmark_harness.py` + `suite.benchmark_harness`
- Context keys（避免你自创 key 造成不一致）：`utils/context/context_keys.py`
