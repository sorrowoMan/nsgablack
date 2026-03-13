# 信号驱动偏置（Signal-driven Bias）

这份文档描述一种**偏置的工程类别**：它本质上是“策略层（policy）”，需要上游能力层提供统计信号，因此通常应与 Plugin/Wiring 配套使用。

## 1. 什么是信号驱动偏置

在 NSGABlack 中，`AlgorithmicBias` 并不要求“单独启用就有意义”。

有一类偏置的职责是：**消费某种统计信号 → 产生选择/评分倾向**。信号本身不由偏置生成，而由能力层注入到 `context.metrics`。

典型例子：

- `RobustnessBias`：消费 `mc_std`（来自 Monte Carlo 重复评估）来惩罚不稳定候选解
- 未来可扩展：消费 `surrogate_std` / `surrogate_uncertainty`（来自代理模型）进行风险规避或探索引导

## 2. 这类偏置的特点

- **依赖外部信号**：没有信号时必须安全退化（返回 `0.0`），而不是抛异常
- **策略可复用**：同一“鲁棒性策略”可以由不同信号提供方驱动（MC / surrogate / bootstrap / 重复评估缓存）
- **解耦但需要配方**：为了避免“用户只开偏置却没有信号 → 看起来没效果”，需要提供权威组合（wiring）

## 3. 工程规范（必须遵守）

### 3.1 偏置侧（Bias）

信号驱动偏置必须：

- 声明 `requires_metrics: set[str]`
- 声明 `recommended_plugins: list[str]`（或者提供 wiring）
- 在缺信号时返回 `0.0`（可选择 `RuntimeWarning` 提示一次，warn-once）

示例（节选）：

```python
class RobustnessBias(AlgorithmicBias):
    requires_metrics = {"mc_std"}
    recommended_plugins = ["MonteCarloEvaluationPlugin"]

    def compute(self, x, context):
        if "mc_std" not in context.metrics:
            return 0.0
        ...
```

### 3.2 能力层（Plugin/Adapter/外部评估器）

信号提供方应把统计写入 `context["metrics"]`（再由 `BiasModule` 透传到 `OptimizationContext.metrics`）。

建议同时声明：

- `provides_metrics: set[str]`

示例（节选）：

```python
class MonteCarloEvaluationPlugin(Plugin):
    provides_metrics = {"mc_mean", "mc_std", "mc_samples"}
```

## 4. Wiring：把“必须组合”变成权威入口

当一个能力必须“成套使用”才有意义时，推荐提供 `utils/wiring/*` 的权威组合函数：

- 它不改变底座，只负责装配（挂插件、启用偏置、设置默认值）
- 它是“事实标准”：后续测试/示例/新功能对齐它即可

目前已有（直接装配）：

- `plugins/evaluation/monte_carlo_evaluation.py`（提供 `mc_std`）
- `bias/algorithmic/signal_driven/robustness.py`（消费 `mc_std`）

用法：

```python
from nsgablack.plugins import MonteCarloEvaluationPlugin, MonteCarloEvaluationConfig
from nsgablack.bias import BiasModule, RobustnessBias

solver.add_plugin(
    MonteCarloEvaluationPlugin(
        config=MonteCarloEvaluationConfig(mc_samples=64)
    )
)
bias = BiasModule()
bias.add(RobustnessBias(weight=0.2))
solver.set_bias_module(bias, enable=True)
```

## 5. 推荐落地路径（解构算法时）

当你在解构一个“需要统计信号”的算法思想时：

1. 先把“如何得到信号”做成 Plugin（或由 Adapter 主动调用 ParallelEvaluator / 评估短路插槽）
2. 再把“如何消费信号产生倾向”做成 Bias（信号驱动偏置）
3. 最后用 Wiring 固化“权威组合”与默认值（避免示例/参数发散）
