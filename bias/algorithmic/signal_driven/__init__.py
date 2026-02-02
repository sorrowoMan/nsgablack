"""
Signal-driven algorithmic biases.

这类偏置不“自产”关键评估信号，而是**消费**上游能力层注入到 `context.metrics` 的统计量，
例如 Monte Carlo 评估的 `mc_std`、代理模型的不确定性 `surrogate_std` 等。

工程约定：
- 信号驱动偏置必须声明 `requires_metrics`（它依赖哪些 metrics key）
- 同时必须给出 `recommended_plugins` 或提供一个 `utils/suites/*` 的权威组合入口
- 当信号缺失时必须安全退化（返回 0.0），不得抛异常破坏主流程
"""

from .robustness import RobustnessBias
from .uncertainty_exploration import UncertaintyExplorationBias

__all__ = [
    "RobustnessBias",
    "UncertaintyExplorationBias",
]
