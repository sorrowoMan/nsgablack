# 增强搜索策略系统 - 使用指南

## 📚 快速开始

### 1. 基础使用

```python
from nsgablack.experimental.multi_agent.strategies.search_strategies import (
    SearchStrategyFactory,
    SearchMethod
)

# 为探索者创建差分进化策略
explorer_strategy = SearchStrategyFactory.create_strategy(
    SearchMethod.DIFFERENTIAL_EVOLUTION,
    config={'F': 0.8, 'CR': 0.9}
)

# 执行搜索
new_solutions = explorer_strategy.search(
    population=current_population,
    bounds=problem_bounds,
    n_solutions=50
)
```

### 2. 为不同角色配置策略

```python
# 探索者：使用差分进化
explorer_config = {
    'search_method': SearchMethod.DIFFERENTIAL_EVOLUTION,
    'search_params': {
        'F': 0.8,      # 差分权重
        'CR': 0.9      # 交叉概率
    }
}

# 开发者：使用模式搜索
exploiter_config = {
    'search_method': SearchMethod.PATTERN_SEARCH,
    'search_params': {
        'pattern_size': 2,
        'step_size': 0.1
    }
}
```

---

## 🔍 搜索方法详解

### Explorer（探索者）推荐方法

#### 1. 差分进化 (Differential Evolution) ⭐⭐⭐⭐⭐

**原理**：
```
v = x_r1 + F * (x_r2 - x_r3)  # 差分变异
u = crossover(v, x_target)      # 交叉
```

**为什么适合探索者**：
- ✅ 利用种群多个个体的差异信息
- ✅ 搜索方向多样，不易陷入局部最优
- ✅ 参数少，鲁棒性强
- ✅ 在连续优化问题上表现优异

**参数建议**：
```python
{
    'F': 0.8,          # 差分权重 [0.5, 1.0]
    'CR': 0.9,         # 交叉概率 [0.8, 1.0]
    'variant': 'rand'  # 使用随机基向量
}
```

**适用场景**：
- 高维连续优化问题
- 多峰问题
- 需要强探索能力的问题

---

#### 2. 进化策略 (Evolutionary Strategy) ⭐⭐⭐⭐

**原理**：
```
从多元正态分布采样: x ~ N(μ, σ²Σ)
其中 μ 是种群均值，Σ 是协方差矩阵
```

**为什么适合探索者**：
- ✅ 自适应变异，根据种群分布调整
- ✅ 能够探索复杂的搜索空间
- ✅ 协方差矩阵捕获变量相关性

**参数建议**：
```python
{
    'sigma': 0.5,         # 初始标准差
    'learning_rate': 0.1  # 学习率
}
```

**适用场景**：
- 变量之间有相关性的问题
- 需要自适应探索的问题
- 复杂的搜索空间

---

#### 3. 模拟退火 (Simulated Annealing) ⭐⭐⭐

**原理**：
```
生成邻域解，以概率接受劣解
概率 = exp(-ΔE/T)，T 随时间降低
```

**为什么适合探索者**：
- ✅ 概率接受机制，能够跳出局部最优
- ✅ 温度调度控制探索强度
- ✅ 理论上有全局收敛保证

**参数建议**：
```python
{
    'initial_temp': 1.0,
    'cooling_rate': 0.95,
    'min_temp': 1e-4
}
```

**适用场景**：
- 强多峰问题
- 需要理论保证的问题
- 作为其他方法的补充

---

### Exploiter（开发者）推荐方法

#### 1. 模式搜索 (Pattern Search) ⭐⭐⭐⭐⭐

**原理**：
```
从当前点出发，沿着坐标方向搜索
x_trial = x_base + Δx_i  (对每个维度i)
```

**为什么适合开发者**：
- ✅ 系统性探索邻域
- ✅ 能够可靠地找到局部最优
- ✅ 不需要梯度信息
- ✅ 收敛速度快

**参数建议**：
```python
{
    'pattern_size': 2,    # 搜索范围
    'step_size': 0.1,     # 初始步长
    'reduction': 0.5      # 步长缩减因子
}
```

**适用场景**：
- 连续可微问题
- 需要精确局部优化
- 低维问题

---

#### 2. 近似梯度 (Approximate Gradient) ⭐⭐⭐⭐

**原理**：
```
使用有限差分近似梯度：
∂f/∂x_i ≈ (f(x+εe_i) - f(x)) / ε

沿负梯度方向搜索：x_new = x - α∇f(x)
```

**为什么适合开发者**：
- ✅ 利用函数的局部结构信息
- ✅ 收敛速度快
- ✅ 适合可微问题

**参数建议**：
```python
{
    'epsilon': 1e-5,      # 有限差分步长
    'learning_rate': 0.1, # 学习率
    'method': 'forward'   # 前向差分
}
```

**适用场景**：
- 可微函数
- 连续优化问题
- 需要快速收敛

**限制**：
- ❌ 需要额外的函数评估（计算梯度）
- ❌ 对噪声敏感

---

#### 3. 文化基因算法 (Memetic Algorithm) ⭐⭐⭐⭐⭐

**原理**：
```
全局搜索（GA/DE） + 局部精炼（Hill Climbing）
大部分解用全局搜索生成
小部分解用局部搜索精炼
```

**为什么适合开发者**：
- ✅ 结合全局和局部搜索优点
- ✅ 全局探索避免陷入局部最优
- ✅ 局部搜索快速收敛
- ✅ 灵活的混合策略

**参数建议**：
```python
{
    'global_method': 'differential_evolution',
    'local_method': 'pattern_search',
    'local_search_prob': 0.3  # 30%的解使用局部搜索
}
```

**适用场景**：
- 复杂的多峰问题
- 需要平衡探索和开发
- 计算资源充足

---

## 📊 性能对比

### 对比表格

| 方法 | 探索能力 | 开发能力 | 收敛速度 | 鲁棒性 | 计算成本 |
|------|---------|---------|---------|--------|---------|
| **随机** | ⭐ | ⭐ | ⭐ | ⭐⭐ | ⭐ |
| **遗传(均匀)** | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| **遗传(算术)** | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| **差分进化** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **进化策略** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **模式搜索** | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ |
| **近似梯度** | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ |
| **模拟退火** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| **文化基因** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |

---

## 🎯 选择建议

### 根据问题特征选择

#### 1. 问题维度
- **低维（< 10）**：模式搜索、近似梯度
- **中维（10-50）**：差分进化、文化基因
- **高维（> 50）**：差分进化、进化策略

#### 2. 问题特性
- **单峰**：近似梯度、模式搜索
- **多峰**：差分进化、模拟退火
- **可分**：遗传算法、差分进化
- **不可分**：进化策略、文化基因

#### 3. 计算预算
- **评估次数少（< 1000）**：模式搜索、模拟退火
- **评估次数中等（1000-10000）**：差分进化、遗传算法
- **评估次数多（> 10000）**：文化基因、进化策略

---

## 💡 组合策略

### 示例1：自适应策略切换

```python
class AdaptiveSearchStrategy:
    """自适应搜索策略"""

    def __init__(self):
        # 早期：强探索
        self.early_methods = [
            SearchMethod.DIFFERENTIAL_EVOLUTION,
            SearchMethod.SIMULATED_ANNEALING
        ]
        # 中期：平衡
        self.mid_methods = [
            SearchMethod.EVOLUTIONARY_STRATEGY,
            SearchMethod.MEMETIC
        ]
        # 后期：强开发
        self.late_methods = [
            SearchMethod.PATTERN_SEARCH,
            SearchMethod.GRADIENT_APPROXIMATION
        ]

    def get_method(self, generation, max_generations):
        progress = generation / max_generations

        if progress < 0.3:
            return np.random.choice(self.early_methods)
        elif progress < 0.7:
            return np.random.choice(self.mid_methods)
        else:
            return np.random.choice(self.late_methods)
```

### 示例2：混合种群策略

```python
# 探索者种群：50% DE + 30% ES + 20% SA
explorer_methods = [
    (SearchMethod.DIFFERENTIAL_EVOLUTION, 0.5),
    (SearchMethod.EVOLUTIONARY_STRATEGY, 0.3),
    (SearchMethod.SIMULATED_ANNEALING, 0.2)
]

# 开发者种群：40% 模式搜索 + 30% 近似梯度 + 30% 文化基因
exploiter_methods = [
    (SearchMethod.PATTERN_SEARCH, 0.4),
    (SearchMethod.GRADIENT_APPROXIMATION, 0.3),
    (SearchMethod.MEMETIC, 0.3)
]
```

---

## 🚀 与当前代码集成

### 推荐：用 Core 的多策略主协调 Adapter 接入（不需要 experimental 目录）

思路：把“搜索策略”实现为 Adapter（或 RoleAdapter 包装），由主协调器下发任务/预算与共享事实。

```python
from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.core.adapters import RoleSpec, MultiStrategyConfig, MultiStrategyControllerAdapter
from nsgablack.utils.suites import attach_multi_strategy_coop

# 每个“角色/策略”都是一个 adapter（可以有多个 unit 并行）
roles = [
    RoleSpec(name="explorer", adapter=lambda uid: ExplorerAdapter(...), n_units=20, weight=1.0),
    RoleSpec(name="exploiter", adapter=lambda uid: ExploiterAdapter(...), n_units=10, weight=1.0),
]

cfg = MultiStrategyConfig(
    total_batch_size=200,
    phase_schedule=(("explore", 20), ("exploit", -1)),
    phase_roles={"explore": ["explorer"], "exploit": ["exploiter"]},
    enable_regions=True,
    n_regions=20,
    seeds_per_task=2,
)

solver = ComposableSolver(problem=problem, representation_pipeline=pipeline)
attach_multi_strategy_coop(solver, roles=roles, config=cfg, attach_pareto_archive=True)
solver.run()
```

---

## 📖 总结

### 当前方法 vs 增强方法对比

| 特性 | 当前方法 | 增强方法 |
|------|---------|---------|
| **Explorer** | 随机选择+均匀交叉+高斯变异 | 差分进化、进化策略、模拟退火 |
| **Exploiter** | 适应度选择+算术交叉+小变异 | 模式搜索、近似梯度、文化基因 |
| **探索能力** | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| **开发效率** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **自适应性** | ❌ | ✅ |
| **问题感知** | ❌ | ✅ |
| **可扩展性** | ⭐⭐ | ⭐⭐⭐⭐⭐ |

### 建议

1. **立即可用**：为探索者配置差分进化，为开发者配置模式搜索
2. **渐进增强**：保留现有方法，逐步添加新策略
3. **自动选择**：根据问题特征自动推荐策略
4. **性能测试**：在标准测试集上对比不同方法的性能

---

**创建日期**: 2025-12-31
**版本**: 1.0
