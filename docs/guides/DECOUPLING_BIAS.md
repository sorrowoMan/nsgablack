# DECOUPLING_BIAS: BiasModule 该负责什么

Bias 不等于“作弊”。Bias 是你把偏好、软约束、搜索倾向写成可组合组件的方式。

这一页讲清楚：哪些东西适合偏置化，哪些不适合，以及为什么偏置化能让你更快响应“新业务约束/新点子”。

## BiasModule 的职责（应该做）

- 领域偏置（domain）：软约束/偏好（惩罚项、优先级、业务规则）
- 算法偏置（algorithmic）：搜索倾向（退火温度、pattern search、tabu 记忆等）
- 信号驱动偏置（signal-driven）：依赖统计信号/metrics 的偏置
  - 必须声明 `requires_metrics`
  - 强烈建议配套一个推荐 `wiring`（避免“只拿到偏置没法用”）

## Bias 不该承担什么

- 硬约束可行化：优先放 `RepresentationPipeline`（init/mutate/repair）
- 工程调度/并行/输出：交给 Plugin/Wiring
- 复杂策略过程：那是 Adapter 的工作（Bias 更像“倾向/打分/软约束”）

## 为什么要偏置化（你一定遇到过）

- 新规则来了：你不想去改算法主循环（容易引入隐性 bug）
- 你要做对比：你希望“只换偏置，不换策略”，把因果说清楚
- 你要复用：同一份业务偏好希望能跨 NSGA2/SA/VNS 等策略复用

## 你应该看哪里

- 偏置系统入口/索引：`docs/indexes/BIAS_INDEX.md`
- 信号驱动偏置规范：`docs/user_guide/signal_driven_bias.md`
- 偏置实现：`bias/`
- 真实用法：`WORKFLOW_END_TO_END.md`
