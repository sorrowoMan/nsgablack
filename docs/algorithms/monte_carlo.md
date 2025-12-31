# 蒙特卡洛优化模块使用指南

## 概述

蒙特卡洛模块提供了一个**可组合的优化框架**，用于处理包含随机变量的优化问题。核心特点：

- ✅ **嵌套架构**：MC采样 → 调用任意优化器（GA/VNS/...）
- ✅ **三层组合**：代理模型 + MC + 遗传算法
- ✅ **多种模式**：期望优化、鲁棒优化、CVaR优化
- ✅ **高度可复用**：模块化设计，易于扩展

---

## 核心类

### 1. `StochasticProblem` - 随机问题基类

继承自 `BlackBoxProblem`，用于定义包含随机变量的优化问题。

```python
from nsgablack import StochasticProblem, DistributionSpec

class MyStochasticProblem(StochasticProblem):
    def __init__(self):
        super().__init__(
            name="我的随机问题",
            dimension=2,
            bounds={'x0': [0, 10], 'x1': [0, 10]}
        )

    def get_random_distributions(self):
        """定义随机变量的分布"""
        return {
            'noise': DistributionSpec('normal', {'mean': 0, 'std': 0.1}),
            'demand': DistributionSpec('uniform', {'low': 80, 'high': 120})
        }

    def evaluate_stochastic(self, x, random_params):
        """评估目标函数（给定随机参数）"""
        noise = random_params['noise']
        demand = random_params['demand']
        return (x[0] - demand)**2 + noise
```

### 2. `DistributionSpec` - 分布规范

支持的分布类型：
- `'normal'`: 正态分布，参数 `{'mean': μ, 'std': σ}`
- `'uniform'`: 均匀分布，参数 `{'low': a, 'high': b}`
- `'lognormal'`: 对数正态分布，参数 `{'mean': μ, 'sigma': σ}`
- `'triangular'`: 三角分布，参数 `{'left': a, 'mode': c, 'right': b}`

### 3. `MonteCarloOptimizer` - MC优化器

核心优化器，支持三种模式：

```python
from nsgablack import MonteCarloOptimizer, BlackBoxSolverNSGAII

# 定义内层优化器工厂
def optimizer_factory(problem):
    solver = BlackBoxSolverNSGAII(problem)
    solver.enable_progress_log = False
    return solver

# 创建MC优化器
mc_optimizer = MonteCarloOptimizer(
    stochastic_problem=problem,
    inner_optimizer_factory=optimizer_factory,
    mc_samples=100,           # MC采样数
    mode='expectation',       # 'expectation' | 'robust' | 'cvar'
    robust_lambda=0.5,        # 鲁棒优化的方差权重
    cvar_alpha=0.95,          # CVaR的置信水平
    seed=42
)

# 运行优化
result = mc_optimizer.optimize(
    pop_size=50,
    max_generations=100
)
```

**三种优化模式：**

| 模式 | 目标函数 | 适用场景 |
|------|---------|---------|
| `expectation` | min E[f(x, ξ)] | 最小化期望值 |
| `robust` | min E[f] + λ·Std[f] | 平衡期望与波动性 |
| `cvar` | min CVaR_α[f] | 最小化最坏情况 |

### 4. `SurrogateMonteCarloOptimizer` - 代理+MC优化器

三层嵌套架构：代理模型 → MC评估 → 遗传算法

```python
from nsgablack import SurrogateMonteCarloOptimizer

optimizer = SurrogateMonteCarloOptimizer(
    stochastic_problem=problem,
    inner_optimizer_factory=optimizer_factory,
    mc_samples=50,            # 每次MC评估的样本数
    surrogate_type='gp',      # 'gp' | 'rf' | 'rbf'
    initial_samples=20,       # 初始训练样本数
    max_iterations=10,        # 迭代次数
    samples_per_iter=5,       # 每次迭代新增样本数
    mode='expectation'
)

result = optimizer.optimize(pop_size=40, max_generations=30)
```

**优势：**
- 大幅减少昂贵的MC评估次数
- 适合每次MC评估耗时较长的问题
- 自动平衡探索与利用

---

## 使用示例

### 示例1：随机库存优化

```python
from nsgablack import StochasticProblem, DistributionSpec, optimize_with_monte_carlo

class InventoryProblem(StochasticProblem):
    def __init__(self):
        super().__init__(
            name="库存优化",
            dimension=2,
            bounds={'x0': [50, 200], 'x1': [0, 50]}  # 订货量, 安全库存
        )

    def get_random_distributions(self):
        return {
            'demand': DistributionSpec('normal', {'mean': 100, 'std': 20})
        }

    def evaluate_stochastic(self, x, random_params):
        order_qty, safety_stock = x
        demand = random_params['demand']

        # 成本 = 订货成本 + 持有成本 + 缺货成本
        cost = 10*order_qty + 2*max(0, order_qty+safety_stock-demand) + 50*max(0, demand-order_qty-safety_stock)
        return cost

# 运行优化
problem = InventoryProblem()
result = optimize_with_monte_carlo(
    stochastic_problem=problem,
    inner_optimizer_factory=lambda p: BlackBoxSolverNSGAII(p),
    mc_samples=100,
    mode='expectation',
    pop_size=50,
    max_generations=50
)

print(f"最优订货策略: {result['best_x']}")
print(f"期望成本: {result['best_f']:.2f}")
```

### 示例2：鲁棒投资组合优化

```python
class PortfolioProblem(StochasticProblem):
    def __init__(self, n_assets=3):
        super().__init__(
            name="投资组合",
            dimension=n_assets,
            bounds={f'x{i}': [0, 1] for i in range(n_assets)}
        )
        self.expected_returns = np.array([0.08, 0.12, 0.15])
        self.return_stds = np.array([0.05, 0.10, 0.15])

    def get_random_distributions(self):
        return {
            f'return_{i}': DistributionSpec('normal', {
                'mean': self.expected_returns[i],
                'std': self.return_stds[i]
            })
            for i in range(len(self.expected_returns))
        }

    def evaluate_stochastic(self, x, random_params):
        weights = x / (np.sum(x) + 1e-10)
        returns = np.array([random_params[f'return_{i}'] for i in range(len(x))])
        return -np.dot(weights, returns)  # 最小化负收益

# 鲁棒优化：最小化 E[f] + 0.5*Std[f]
problem = PortfolioProblem()
optimizer = MonteCarloOptimizer(
    stochastic_problem=problem,
    inner_optimizer_factory=lambda p: BlackBoxSolverNSGAII(p),
    mc_samples=100,
    mode='robust',
    robust_lambda=0.5  # 平衡收益与风险
)

result = optimizer.optimize(pop_size=50, max_generations=50)
print(f"最优权重: {result['best_x'] / np.sum(result['best_x'])}")
```

### 示例3：代理+MC+GA三层架构

```python
from nsgablack import optimize_with_surrogate_mc

class ExpensiveStochasticProblem(StochasticProblem):
    """每次MC评估耗时较长的问题"""
    def __init__(self):
        super().__init__(name="昂贵随机问题", dimension=5, bounds={f'x{i}': [0, 10] for i in range(5)})

    def get_random_distributions(self):
        return {f'noise_{i}': DistributionSpec('normal', {'mean': 0, 'std': 0.1}) for i in range(5)}

    def evaluate_stochastic(self, x, random_params):
        noise = np.array([random_params[f'noise_{i}'] for i in range(5)])
        return np.sum((x + noise - 5)**2)

# 使用代理模型加速
problem = ExpensiveStochasticProblem()
result = optimize_with_surrogate_mc(
    stochastic_problem=problem,
    inner_optimizer_factory=lambda p: BlackBoxSolverNSGAII(p),
    mc_samples=30,           # 每次MC评估30个样本
    surrogate_type='gp',     # 高斯过程代理
    initial_samples=15,      # 初始15个训练点
    max_iterations=8,        # 迭代8次
    pop_size=40,
    max_generations=30
)

print(f"最优解: {result['best_x']}")
print(f"真实MC评估次数: {len(result['y_train'])}")  # 远小于直接MC+GA
```

---

## 便捷函数

### `optimize_with_monte_carlo`

快速运行MC优化的便捷函数：

```python
from nsgablack import optimize_with_monte_carlo

result = optimize_with_monte_carlo(
    stochastic_problem=problem,
    inner_optimizer_factory=optimizer_factory,
    mc_samples=100,
    mode='expectation',
    # 以下参数传递给内层优化器
    pop_size=50,
    max_generations=100
)
```

### `optimize_with_surrogate_mc`

快速运行代理+MC优化的便捷函数：

```python
from nsgablack import optimize_with_surrogate_mc

result = optimize_with_surrogate_mc(
    stochastic_problem=problem,
    inner_optimizer_factory=optimizer_factory,
    mc_samples=50,
    surrogate_type='gp',
    initial_samples=20,
    max_iterations=10,
    # 以下参数传递给内层优化器
    pop_size=40,
    max_generations=30
)
```

---

## 返回结果

所有优化函数返回一个字典，包含：

```python
{
    'best_x': np.ndarray,        # 最优解
    'best_f': float,             # 最优目标值
    'solver': Solver,            # 内层求解器实例
    'statistics': {              # 最优解的统计信息
        'mean': float,           # 期望值
        'std': float,            # 标准差
        'min': float,            # 最小值
        'max': float,            # 最大值
        'q25': float,            # 25%分位数
        'q50': float,            # 中位数
        'q75': float,            # 75%分位数
        'samples': np.ndarray    # 所有MC样本
    }
}
```

---

## 与其他模块的组合

### 1. 与Bias模块结合

```python
from nsgablack import create_standard_bias

def optimizer_factory(problem):
    solver = BlackBoxSolverNSGAII(problem)
    solver.enable_bias = True
    solver.bias_module = create_standard_bias(problem)
    return solver

result = optimize_with_monte_carlo(
    stochastic_problem=problem,
    inner_optimizer_factory=optimizer_factory,
    mc_samples=100
)
```

### 2. 与VNS结合

```python
from nsgablack import BlackBoxSolverVNS

def vns_factory(problem):
    solver = BlackBoxSolverVNS(problem)
    solver.max_iterations = 200
    solver.k_max = 5
    return solver

result = optimize_with_monte_carlo(
    stochastic_problem=problem,
    inner_optimizer_factory=vns_factory,
    mc_samples=100
)
```

### 3. 与多样性初始化结合

```python
def optimizer_factory(problem):
    solver = BlackBoxSolverNSGAII(problem)
    solver.enable_diversity_init = True
    solver.use_history = True
    return solver

result = optimize_with_monte_carlo(
    stochastic_problem=problem,
    inner_optimizer_factory=optimizer_factory,
    mc_samples=100
)
```

---

## 运行完整示例

```bash
# 运行所有示例
python -m nsgablack.monte_carlo_example

# 快速测试
python test_monte_carlo.py
```

---

## 设计理念

蒙特卡洛模块的设计遵循以下原则：

1. **可组合性**：MC优化器接受任意优化器工厂，可以嵌套调用GA/VNS/其他算法
2. **模块化**：清晰分离随机问题定义、MC评估、优化求解三个层次
3. **可扩展性**：易于添加新的分布类型、优化模式、代理模型
4. **统一接口**：与现有的BlackBoxProblem体系无缝集成

这种设计使得你可以灵活组合不同的优化策略，构建复杂的嵌套优化流程。

---

## 常见问题

**Q: 如何选择MC采样数？**

A:
- 简单问题：50-100个样本
- 复杂问题：100-500个样本
- 使用代理模型时：可以减少到30-50个样本

**Q: 何时使用代理+MC？**

A: 当单次MC评估耗时较长（>1秒）时，使用代理模型可以显著加速。

**Q: 如何选择优化模式？**

A:
- `expectation`: 只关心平均性能
- `robust`: 需要平衡性能与稳定性
- `cvar`: 需要避免最坏情况

**Q: 可以用于多目标优化吗？**

A: 可以！内层优化器可以是NSGA-II，会自动处理多目标Pareto前沿。

---

## 总结

蒙特卡洛模块为你的优化框架增加了处理不确定性的能力，通过可组合的设计，你可以：

- ✅ 嵌套调用任意优化器
- ✅ 组合代理模型加速
- ✅ 灵活选择优化模式
- ✅ 与现有模块无缝集成

这使得你的代码能够优雅地处理实际工程中常见的随机优化问题！
