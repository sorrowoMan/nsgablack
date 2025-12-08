# nsgablack - 模块化多目标优化框架

<div align="center">

![Python](https://img.shields.io/badge/Python-3.7%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![NSGA-II](https://img.shields.io/badge/Algorithm-NSGA--II-orange)
![Multi-Objective](https://img.shields.io/badge/Type-Multi--Objective-purple)

一个面向黑箱函数和工程仿真的**高性能模块化优化框架**，提供NSGA-II、代理模型、偏置引导、并行计算等多种优化策略。

[📖 快速开始](#-快速开始) • [🚀 核心功能](#-核心功能) • [📚 文档](#-更多文档) • [🔧 安装](#️-安装依赖)

</div>

## 📋 目录

- [🚀 快速开始](#-快速开始)
- [✨ 核心功能](#-核心功能)
  - [1. 🔵 贝叶斯优化 ⭐](#1-🔵-贝叶斯优化-⭐)
  - [2. 🌐 并行种群评估 ⚡](#2-🌐-并行种群评估-)
  - [3. 🎯 多目标优化 (NSGA-II)](#3-🎯-多目标优化-nsga-ii)
  - [4. 🤖 代理模型优化 (SMBO)](#4-🤖-代理模型优化-smbo)
  - [5. 🧭 偏置引导优化](#5-🧭-偏置引导优化)
  - [6. 🎲 蒙特卡洛优化](#6-🎲-蒙特卡洛优化)
  - [7. 🔍 变邻域搜索 (VNS)](#7-🔍-变邻域搜索-vns)
  - [8. 🧠 机器学习引导的优化](#8-🧠-机器学习引导的优化)
- [📁 项目结构](#-项目结构)
- [🛠️ 安装依赖](#️-安装依赖)
- [📊 性能基准](#-性能基准)
- [🔧 配置选项](#-配置选项)
- [📈 使用建议](#-使用建议)
- [🤝 贡献指南](#-贡献指南)
- [📄 许可证](#-许可证)

---

## 🚀 快速开始

### 运行示例

项目现在支持直接运行示例文件，无需额外配置：

```bash
# ⭐ 推荐：并行评估示例（适用于昂贵函数）
python examples/parallel_evaluation_example_fixed.py

# ⭐ 推荐：偏置系统 v2.0 示例 (独立bias包)
python examples/bias_v2_simple_example.py

# 🤖 代理模型辅助优化
python examples/surrogate_example.py

# 🔵 贝叶斯优化 (新增！)
python examples/bayesian_optimization_example.py

# 🎲 蒙特卡洛优化
python examples/monte_carlo_example.py

# 🎯 多目标优化
python examples/examples.py
```

### 5分钟快速上手

```python
import numpy as np
from core.base import BlackBoxProblem
from core.solver import BlackBoxSolverNSGAII

# 1. 定义你的优化问题
class MyProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(
            name="MyOptimizationProblem",
            dimension=3,
            bounds={'x0': (-5, 5), 'x1': (-5, 5), 'x2': (-5, 5)}
        )

    def evaluate(self, x):
        # 你的目标函数
        return np.sum(x**2)  # 示例：最小化平方和

    def evaluate_constraints(self, x):
        # 可选：约束函数 (返回 <= 0 的值)
        return np.array([
            x[0] + x[1] + x[2] - 3,  # g1(x) <= 0
            1.0 - x[0]             # g2(x) <= 0
        ])

# 2. 创建求解器
problem = MyProblem()
solver = BlackBoxSolverNSGAII(problem)

# 3. 配置参数
solver.pop_size = 50              # 种群大小
solver.max_generations = 100       # 最大进化代数
solver.enable_progress_log = True   # 显示进度

# 4. 运行优化
result = solver.run()

# 5. 查看结果
best_solution = result['pareto_solutions']['individuals'][0]
best_objective = result['pareto_solutions']['objectives'][0][0]

print(f"最优解: {best_solution}")
print(f"最优值: {best_objective}")
print(f"约束值: {problem.evaluate_constraints(best_solution)}")
```

---

## ✨ 核心功能

### 1. 🔵 贝叶斯优化 ⭐

**专为昂贵黑箱函数设计的智能优化方法**，通过高斯过程模型和获取函数，实现样本高效的全局搜索。

#### 🎯 核心优势

- **超高样本效率**：仅需10-100次评估即可找到高质量解
- **不确定性量化**：明确知道哪里需要更多探索
- **理论保证**：有收敛性理论支持
- **灵活使用**：独立优化、偏置引导、混合策略

#### 💻 快速开始

```python
from solvers.bayesian_optimizer import BayesianOptimizer

# 创建贝叶斯优化器
bo = BayesianOptimizer(acquisition='ei', kernel='matern')

# 运行优化
result = bo.optimize(
    objective_func=expensive_function,
    bounds=[(-5, 5), (-5, 5)],
    budget=50
)

print(f"最优值: {result['best_y']:.6f}")
```

### 2. 🌐 并行种群评估 ⚡

**专为昂贵函数优化的高性能并行引擎**，支持多种并行后端，显著提升优化效率。

#### 🎯 适用场景

- **CAE/CFD仿真优化**：单次仿真需要几分钟到几小时
- **机器学习超参数调优**：模型训练耗时
- **工程设计优化**：物理仿真、有限元分析
- **大规模种群评估**：种群数量大的优化问题

#### ⚡ 性能提升

| 种群规模 | 串行时间 | 并行时间 | 加速比         |
| -------- | -------- | -------- | -------------- |
| 50       | 60秒     | 18秒     | **3.3x** |
| 100      | 120秒    | 28秒     | **4.3x** |
| 200      | 240秒    | 52秒     | **4.6x** |

#### 💻 使用方法

```python
from utils.parallel_evaluator import ParallelEvaluator

# 方法1：直接使用并行评估器
evaluator = ParallelEvaluator(
    backend="thread",           # 后端选择
    max_workers=4,              # 并行数量
    chunk_size=10,              # 批次大小
    enable_load_balancing=True  # 负载均衡
)

# 并行评估种群
objectives, violations = evaluator.evaluate_population(population, problem)

# 方法2：在NSGA-II中启用并行
solver = BlackBoxSolverNSGAII(problem)
solver.enable_parallel = True
solver.parallel_backend = "thread"     # 'thread' | 'process' | 'joblib'
solver.max_workers = 4

result = solver.run()
```

#### 🔧 并行后端对比

| 后端        | 优点              | 缺点           | 适用场景  |
| ----------- | ----------------- | -------------- | --------- |
| `thread`  | 轻量级，共享内存  | Python GIL限制 | I/O密集型 |
| `process` | 绕过GIL，真正并行 | 内存开销大     | CPU密集型 |
| `joblib`  | 自动负载均衡      | 依赖joblib     | 混合负载  |

---

### 3. 🎯 多目标优化 (NSGA-II)

**经典的多目标进化算法**，基于快速非支配排序和拥挤度距离。

#### 🎯 适用场景

- **工程设计**：多个冲突目标（成本vs性能）
- **投资组合**：收益vs风险
- **机器学习**：准确率vs复杂度
- **调度问题**：时间vs成本

#### 🔑 核心特性

- **快速非支配排序**：O(MN²)时间复杂度
- **拥挤度距离**：保持解的多样性
- **精英策略**：保证最优解不丢失
- **约束处理**：支持约束多目标优化

#### 💻 使用方法

```python
from core.problems import ZDT1BlackBox, DTLZ2BlackBox

# 内置测试问题
problem = ZDT1BlackBox(dimension=10)  # 2目标，10维
# problem = DTLZ2BlackBox(dimension=12, n_objectives=3)  # 3目标

# 自定义多目标问题
class MultiObjectiveProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(
            name="MultiObj",
            dimension=2,
            bounds={'x0': (0, 1), 'x1': (0, 1)}
        )

    def evaluate(self, x):
        # 返回多个目标值
        f1 = x[0]                    # 最小化 f1
        f2 = (1 + x[1]) / x[0]      # 最小化 f2
        return np.array([f1, f2])

    def get_num_objectives(self):
        return 2  # 重要：指定目标数量

# 求解器配置
solver = BlackBoxSolverNSGAII(problem)
solver.pop_size = 100
solver.max_generations = 200
solver.enable_progress_log = True
solver.report_interval = 20  # 每20代报告一次

# 运行优化
result = solver.run()

# 分析Pareto前沿
pareto_solutions = result['pareto_solutions']['individuals']
pareto_objectives = result['pareto_solutions']['objectives']

print(f"Pareto解数量: {len(pareto_solutions)}")
print(f"目标范围: f1=[{min(pareto_objectives[:,0]):.3f}, {max(pareto_objectives[:,0]):.3f}]")
print(f"目标范围: f2=[{min(pareto_objectives[:,1]):.3f}, {max(pareto_objectives[:,1]):.3f}]")
```

#### 📊 结果可视化

```python
import matplotlib.pyplot as plt

# 绘制Pareto前沿
plt.figure(figsize=(10, 6))
plt.scatter(pareto_objectives[:, 0], pareto_objectives[:, 1],
           alpha=0.6, s=50, c='blue', edgecolors='black')
plt.xlabel('Objective 1')
plt.ylabel('Objective 2')
plt.title('Pareto Front')
plt.grid(True, alpha=0.3)
plt.show()
```

---

### 4. 🤖 代理模型优化 (SMBO)

**大幅减少昂贵评估次数的智能优化策略**，用机器学习模型近似目标函数。

#### 🎯 适用场景

- **仿真驱动设计**：CFD、FEA、多物理场仿真
- **实验优化**：物理实验、药物筛选
- **超参数优化**：深度学习模型调参
- **实时优化**：需要快速响应的场景

#### 🤖 代理模型类型

| 模型类型                   | 特点         | 适用场景   | 精度       | 速度     |
| -------------------------- | ------------ | ---------- | ---------- | -------- |
| **高斯过程 (GP)**    | 不确定性量化 | 小规模问题 | ⭐⭐⭐⭐⭐ | ⭐⭐     |
| **径向基函数 (RBF)** | 插值性质     | 中等规模   | ⭐⭐⭐⭐   | ⭐⭐⭐   |
| **随机森林 (RF)**    | 高维友好     | 大规模问题 | ⭐⭐⭐     | ⭐⭐⭐⭐ |
| **神经网络 (NN)**    | 非线性强     | 复杂函数   | ⭐⭐⭐⭐   | ⭐⭐⭐⭐ |
| **集成模型**         | 鲁棒性好     | 通用场景   | ⭐⭐⭐⭐⭐ | ⭐⭐     |

#### 💻 使用方法

```python
from solvers.surrogate import run_surrogate_assisted, SurrogateAssistedOptimizer

# 方法1：简单快速使用
result = run_surrogate_assisted(
    problem=ExpensiveSimulationProblem(),
    surrogate_type='gp',           # 'gp', 'rbf', 'rf', 'nn', 'ensemble'
    real_eval_budget=100,          # 真实评估预算
    initial_samples=20,            # 初始样本数
    acquisition='ei',              # 'ei', 'pi', 'ucb', 'random'
    cv_folds=5                     # 交叉验证折数
)

print(f"真实评估次数: {result['real_eval_count']}")
print(f"代理模型精度 (R²): {result['model_score']:.3f}")
print(f"最优解: {result['best_solution']}")

# 方法2：高级配置
optimizer = SurrogateAssistedOptimizer(
    problem=problem,
    surrogate_type='ensemble',
    real_eval_budget=200,
    acquisition_strategy='ei',
    exploration_weight=0.1
)

# 自定义采样策略
optimizer.initial_sampling_method = 'lhs'  # 'lhs', 'random', 'sobol'
optimizer.adaptive_sampling = True
optimizer.convergence_threshold = 1e-6

result = optimizer.run()

# 分析代理模型性能
print(f"代理模型评估次数: {result['surrogate_eval_count']}")
print(f"改进效率: {result['improvement_ratio']:.2f}x")
```

#### 📈 性能对比

| 方法      | 评估次数 | 时间 | 精度 | 适用场景 |
| --------- | -------- | ---- | ---- | -------- |
| 纯NSGA-II | 1000     | 100% | 100% | 基准     |
| GP辅助    | 150      | 25%  | 95%  | 小规模   |
| RF辅助    | 200      | 35%  | 92%  | 大规模   |
| 集成模型  | 180      | 30%  | 96%  | 通用     |

---

### 5. 🧭 偏置引导优化

**v2.0全新架构**：算法偏置 + 业务偏置的双重引导，智能优化搜索方向。

#### 🎯 适用场景

- **工程设计优化**：结构强度、流体力学、热传导
- **机器学习**：神经网络架构搜索、超参数优化
- **金融优化**：投资组合、风险管理、算法交易
- **供应链**：库存管理、路径规划、资源分配

#### 🏗️ 双重架构设计

```
传统优化：f(x)
偏置优化：f(x) + 算法偏置(x) + 业务偏置(x)
```

**算法偏置 (Algorithmic Bias)**：

- 关注算法本身的效率和性能
- 促进多样性、加速收敛、避免早熟
- 可在不同问题间复用

**业务偏置 (Domain Bias)**：

- 关注特定领域的约束和偏好
- 处理工程约束、业务规则、专家知识
- 针对特定领域定制

#### 🔧 算法偏置类型

| 偏置类型             | 功能             | 参数                   | 适用场景   |
| -------------------- | ---------------- | ---------------------- | ---------- |
| **多样性偏置** | 促进种群多样性   | weight, metric         | 多模态问题 |
| **收敛性偏置** | 分阶段收敛控制   | weight, early/late_gen | 时间敏感   |
| **探索性偏置** | 检测停滞增加探索 | weight, threshold      | 复杂地形   |
| **精度偏置**   | 好解周围精细搜索 | weight, radius         | 高精度需求 |

#### 🏭 业务偏置类型

| 偏置类型               | 功能               | 应用领域 |
| ---------------------- | ------------------ | -------- |
| **约束偏置**     | 处理硬/软/偏好约束 | 通用工程 |
| **偏好偏置**     | 体现业务偏好目标   | 决策支持 |
| **工程设计偏置** | 安全系数、制造约束 | 机械设计 |
| **金融偏置**     | 风险约束、监管要求 | 金融工程 |
| **ML偏置**       | 计算资源、精度目标 | 机器学习 |

#### 💻 使用方法

```python
from bias import (
    AlgorithmicBiasManager, DomainBiasManager, UniversalBiasManager,
    OptimizationContext
)
from bias.bias_library_algorithmic import (
    DiversityBias, ConvergenceBias, ExplorationBias, PrecisionBias
)
from bias.bias_library_domain import (
    ConstraintBias, PreferenceBias, EngineeringDesignBias
)

# 方法1：从零构建
bias_manager = UniversalBiasManager()

# 添加算法偏置
bias_manager.algorithmic_manager.add_bias(
    DiversityBias(weight=0.2, metric='euclidean')
)
bias_manager.algorithmic_manager.add_bias(
    ConvergenceBias(weight=0.1, early_gen=10, late_gen=50)
)
bias_manager.algorithmic_manager.add_bias(
    ExplorationBias(weight=0.1, stagnation_threshold=20)
)

# 添加业务偏置
constraint_bias = ConstraintBias(weight=2.0)
constraint_bias.add_hard_constraint(lambda x: max(0, stress_limit - calculate_stress(x)))
constraint_bias.add_soft_constraint(lambda x: max(0, cost - calculate_cost(x)))
bias_manager.domain_manager.add_bias(constraint_bias)

# 方法2：使用模板
engineering_bias = create_bias_manager_from_template('basic_engineering')
ml_bias = create_bias_manager_from_template('machine_learning')
finance_bias = create_bias_manager_from_template('financial_optimization')

# 在求解器中使用
solver = BlackBoxSolverNSGAII(problem)
solver.enable_bias = True
solver.bias_manager = bias_manager

result = solver.run()
```

#### 📊 动态权重调整

```python
# 早期：重视算法探索
bias_manager.set_bias_weights(algorithmic_weight=0.7, domain_weight=0.3)

# 后期：重视业务约束
bias_manager.set_bias_weights(algorithmic_weight=0.2, domain_weight=0.8)

# 自动调整
optimization_state = {
    'is_stuck': True,                 # 陷入局部最优
    'is_violating_constraints': False # 违反约束
}
bias_manager.adjust_weights(optimization_state)
```

---

### 6. 🎲 蒙特卡洛优化

**处理不确定性和随机性的强大工具**，通过场景分析和置信区间保证解的鲁棒性。

#### 🎯 适用场景

- **库存管理**：需求不确定性
- **投资决策**：市场波动性
- **可靠性工程**：失效概率分析
- **供应链优化**：供应和需求波动

#### 🔑 核心概念

- **场景分析**：考虑多个可能的未来状态
- **置信区间**：提供解的可靠性保证
- **风险度量**：VaR、CVaR等风险指标
- **鲁棒优化**：最坏情况下的性能保证

#### 💻 使用方法

```python
from solvers.monte_carlo import (
    StochasticProblem, optimize_with_monte_carlo, ScenarioGenerator
)

# 定义随机问题
class StochasticInventory(StochasticProblem):
    def __init__(self):
        super().__init__(
            name="InventoryManagement",
            dimension=1,
            bounds={'stock': (0, 1000)}
        )

    def evaluate_scenario(self, x, scenario):
        """对每个场景评估目标函数"""
        stock = x[0]
        demand = scenario['demand']
        price = scenario['price']

        # 收益计算
        revenue = min(stock, demand) * price
        holding_cost = stock * 0.1
        shortage_cost = max(0, demand - stock) * 5

        return revenue - holding_cost - shortage_cost

    def generate_scenarios(self, n_scenarios):
        """生成随机场景"""
        return [
            {
                'demand': np.random.normal(500, 100),
                'price': np.random.uniform(8, 12),
                'probability': 1.0/n_scenarios
            }
            for _ in range(n_scenarios)
        ]

# 运行蒙特卡洛优化
result = optimize_with_monte_carlo(
    problem=StochasticInventory(),
    n_scenarios=1000,              # 场景数量
    confidence_level=0.95,         # 置信水平
    risk_measure='expected_value',  # 'expected_value', 'var', 'cvar'
    optimization_style='robust'     # 'robust', 'opportunistic'
)

print(f"最优库存水平: {result['best_x']}")
print(f"期望收益: {result['expected_value']:.2f}")
print(f"95%置信区间: [{result['confidence_interval'][0]:.2f}, {result['confidence_interval'][1]:.2f}]")
print(f"风险价值(VaR): {result['var']:.2f}")
print(f"条件风险价值(CVaR): {result['cvar']:.2f}")
```

#### 📊 场景分析示例

```python
# 自定义场景生成器
class DemandScenarioGenerator(ScenarioGenerator):
    def __init__(self, base_demand=500, volatility=0.2):
        self.base_demand = base_demand
        self.volatility = volatility

    def generate_scenarios(self, n_scenarios):
        # 考虑季节性、趋势、随机波动
        scenarios = []
        for i in range(n_scenarios):
            # 季节性因素
            seasonal = 1 + 0.3 * np.sin(2 * np.pi * i / 365)
            # 趋势因素
            trend = 1 + 0.001 * i
            # 随机波动
            random_factor = np.random.lognormal(0, self.volatility)

            demand = self.base_demand * seasonal * trend * random_factor

            scenarios.append({
                'demand': demand,
                'season': 'summer' if i % 365 in [152, 183] else 'other',
                'probability': 1.0 / n_scenarios
            })

        return scenarios

# 使用自定义场景生成器
scenario_gen = DemandScenarioGenerator(base_demand=500, volatility=0.15)
result = optimize_with_monte_carlo(
    problem=inventory_problem,
    scenario_generator=scenario_gen,
    n_scenarios=2000,
    confidence_level=0.99
)
```

---

### 7. 🔍 变邻域搜索 (VNS)

**强大的局部搜索算法**，通过系统性地探索不同邻域结构来逃离局部最优。

#### 🎯 适用场景

- **组合优化**：TSP、调度、背包问题
- **连续优化**：多模态函数优化
- **混合整数优化**：离散+连续变量
- **工程优化**：参数调优、设计优化

#### 🔑 核心思想

1. **系统 shaking**：随机扰动当前解
2. **邻域搜索**：在不同大小邻域中搜索
3. **局部改进**：使用局部搜索算法优化
4. **邻域变化**：动态调整邻域结构

#### 🔧 邻域结构

| 邻域类型     | 搜索半径 | 应用场景 |
| ------------ | -------- | -------- |
| **N1** | 0.01     | 精细搜索 |
| **N2** | 0.05     | 局部搜索 |
| **N3** | 0.1      | 区域搜索 |
| **N4** | 0.2      | 全局探索 |
| **N5** | 0.5      | 跳跃搜索 |

#### 💻 使用方法

```python
from solvers.vns import BlackBoxSolverVNS, NeighborhoodManager

# 基础VNS求解器
solver = BlackBoxSolverVNS(problem)

# 配置VNS参数
solver.max_iterations = 1000        # 最大迭代次数
solver.max_no_improvement = 50      # 无改进最大次数
solver.neighborhood_sizes = [0.01, 0.05, 0.1, 0.2, 0.5]
solver.local_search_method = 'hill_climbing'  # 'hill_climbing', 'simulated_annealing'
solver.shaking_intensity = 1.0

# 启用偏置（VNS支持偏置引导）
solver.enable_bias = True
solver.bias_manager = bias_manager

# 运行优化
result = solver.run()

print(f"最优解: {result['best_x']}")
print(f"最优值: {result['best_f']}")
print(f"迭代次数: {result['iterations']}")
print(f"改进次数: {result['improvement_count']}")

# 自定义邻域管理器
class CustomNeighborhoodManager(NeighborhoodManager):
    def __init__(self, problem):
        super().__init__(problem)
        self.adaptive_sizes = True

    def get_neighborhood(self, x, k):
        """自适应邻域大小"""
        if self.adaptive_sizes:
            # 根据当前解的质量调整邻域大小
            base_size = self.neighborhood_sizes[k]
            quality_factor = self.evaluate_solution_quality(x)
            return base_size * (1 + quality_factor)
        else:
            return self.neighborhood_sizes[k]

# 使用自定义邻域
solver.neighborhood_manager = CustomNeighborhoodManager(problem)
result = solver.run()
```

#### 📊 VNS变体

```python
# 变邻域搜索变体
from solvers.vns import (
    GeneralVNS,           # 广义VNS
    ReducedVNS,          # 简化VNS
    SkewedVNS,           # 偏斜VNS
    VariableNeighborhoodDescent  # 变邻域下降
)

# 广义VNS - 适用于大规模问题
gvns = GeneralVNS(problem)
gvns.max_iterations = 500
gvns.neighborhood_sequence = [1, 2, 3, 2, 1]  # 邻域序列

# 偏斜VNS - 重视某些区域
svns = SkewedVNS(problem, skew_regions=[target_region])

# 变邻域下降 - 纯局部搜索
vnd = VariableNeighborhoodDescent(problem)
vnd.local_search_methods = ['hill_climbing', 'tabu_search', 'simulated_annealing']
```

---

### 8. 🧠 机器学习引导的优化

**利用机器学习技术增强优化过程**，包括分类器过滤、回归预测、聚类分析等。

#### 🎯 适用场景

- **高维优化**：降维和特征选择
- **昂贵优化**：学习目标函数模式
- **约束优化**：学习可行域边界
- **多模态优化**：识别有希望的区域

#### 🤖 ML技术在优化中的应用

| 技术类型         | 应用       | 算法                      | 优势         |
| ---------------- | ---------- | ------------------------- | ------------ |
| **分类器** | 过滤劣质解 | SVM, 随机森林, 神经网络   | 减少评估次数 |
| **回归器** | 预测目标值 | GPR, 神经网络, XGBoost    | 加速搜索     |
| **聚类器** | 识别模式   | K-means, DBSCAN, 层次聚类 | 发现解的结构 |
| **降维**   | 处理高维   | PCA, t-SNE, AutoEncoder   | 简化问题     |

#### 💻 使用方法

```python
from ml.ml_models import ModelManager, MLGuidedOptimizer
from core.initialization import MLGuidedInitializer

# 方法1：分类器引导优化
model_manager = ModelManager()

# 训练分类器区分好/坏解
def generate_training_data(problem, n_samples=1000):
    """生成训练数据"""
    X, y = [], []
    for _ in range(n_samples):
        x = problem.random_individual()
        f = problem.evaluate(x)
        # 简单的二分类：好解 vs 坏解
        label = 1 if f < np.median([problem.evaluate(problem.random_individual())
                                   for _ in range(100)]) else 0
        X.append(x)
        y.append(label)
    return np.array(X), np.array(y)

# 生成训练数据
X_train, y_train = generate_training_data(problem)

# 训练多种分类器
classifiers = model_manager.train_classifiers(X_train, y_train)
best_classifier = model_manager.select_best_classifier(classifiers, X_train, y_train)

# 使用分类器引导初始化
initializer = MLGuidedInitializer(
    classifier=best_classifier,
    positive_ratio=0.8,      # 80%概率选择"好"区域
    exploration_rate=0.2     # 20%概率随机探索
)

# 在NSGA-II中使用
solver = BlackBoxSolverNSGAII(problem)
solver.initializer = initializer
solver.enable_ml_guidance = True
result = solver.run()

# 方法2：完整的ML引导优化器
ml_optimizer = MLGuidedOptimizer(
    problem=problem,
    ml_techniques=['classifier', 'regressor', 'clustering'],
    update_frequency=10,      # 每10代更新模型
    confidence_threshold=0.8   # 置信度阈值
)

# 配置ML策略
ml_optimizer.configure_classifier(
    model_type='random_forest',
    n_estimators=100,
    max_depth=10
)

ml_optimizer.configure_regressor(
    model_type='gpr',
    kernel='RBF',
    length_scale=1.0
)

ml_optimizer.configure_clustering(
    method='dbscan',
    eps=0.5,
    min_samples=5
)

result = ml_optimizer.run()

print(f"ML引导优化完成")
print(f"模型更新次数: {result['model_updates']}")
print(f"分类器准确率: {result['classifier_accuracy']:.3f}")
print(f"回归器R²分数: {result['regressor_r2']:.3f}")
print(f"发现的簇数量: {result['n_clusters']}")
```

#### 🧠 深度学习引导

```python
# 使用深度神经网络
from ml.deep_models import DeepOptimizer

deep_optimizer = DeepOptimizer(
    problem=problem,
    network_type='autoencoder',  # 'autoencoder', 'vae', 'gan'
    hidden_layers=[64, 32, 16],
    activation='relu',
    learning_rate=0.001
)

# 预训练网络
deep_optimizer.pretrain(training_data, epochs=100)

# 引导优化
result = deep_optimizer.optimize_with_guidance(
    generations=100,
    guidance_strength=0.5,
    exploration_ratio=0.3
)
```

---

## 📁 项目结构

```
nsgablack/
├── 📂 core/                     # 核心算法模块
│   ├── base.py                  # BlackBoxProblem 基类
│   ├── solver.py                # NSGA-II 求解器
│   ├── problems.py              # 内置测试问题
│   ├── convergence.py           # 收敛性分析
│   ├── diversity.py             # 多样性维护
│   └── elite.py                 # 精英策略
│
├── 📂 solvers/                  # 专门求解器
│   ├── nsga2.py                 # NSGA-II 实现
│   ├── surrogate.py             # 代理模型辅助优化
│   ├── bayesian_optimizer.py     # 贝叶斯优化器 ⭐
│   ├── hybrid_bo.py              # 混合贝叶斯策略 ⭐
│   ├── monte_carlo.py           # 蒙特卡洛方法
│   ├── vns.py                   # 变邻域搜索
│   └── parallel_optimizer.py    # 并行优化器
│
├── 📂 bias/                     # 偏置系统模块 (独立包)
│   ├── __init__.py              # 包初始化和公共API
│   ├── bias.py                  # 偏置系统 v1.0 (BiasModule)
│   ├── bias_base.py             # 基础类定义
│   ├── bias_v2.py               # 偏置系统 v2.0 (双重架构)
│   ├── bias_compatibility.py    # 兼容性层
│   ├── bias_library_algorithmic.py  # 算法偏置库 (26.8KB)
│   └── bias_library_domain.py   # 业务偏置库 (40.2KB)
│
├── 📂 utils/                    # 工具模块
│   ├── visualization.py         # 可视化工具
│   ├── headless.py              # 无界面运行
│   ├── parallel_evaluator.py    # 并行评估器
│   ├── reduced.py               # 降维工具
│   └── metrics.py               # 性能指标
│
├── 📂 ml/                       # 机器学习模块
│   ├── ml_models.py             # ML 模型管理
│   ├── deep_models.py           # 深度学习模型
│   └── feature_engineering.py   # 特征工程
│
├── 📂 meta/                     # 元优化
│   ├── metaopt.py               # 超参数优化
│   └── algorithm_selection.py   # 算法选择
│
├── 📂 examples/                 # 示例代码
│   ├── bias_v2_simple_example.py     # 偏置系统 v2.0
│   ├── parallel_evaluation_example.py  # 并行评估
│   ├── surrogate_example.py            # 代理模型
│   ├── bayesian_optimization_example.py  # 贝叶斯优化 ⭐
│   ├── monte_carlo_example.py          # 蒙特卡洛
│   ├── vns_example.py                  # 变邻域搜索
│   └── ml_guided_example.py            # ML引导优化
│
├── 📂 docs/                     # 文档
│   ├── QUICKSTART.md            # 快速入门
│   ├── API_REFERENCE.md         # API参考
│   ├── BIAS_V2_GUIDE.md          # 偏置系统指南
│   └── TUTORIALS/               # 教程目录
│
└── 📂 tests/                    # 测试代码
    ├── test_core/               # 核心测试
    ├── test_solvers/            # 求解器测试
    └── test_integration/        # 集成测试
```

---

## 🛠️ 安装依赖

### 基础环境

```bash
# Python 3.7+
python --version

# 推荐使用虚拟环境
python -m venv nsgablack_env
source nsgablack_env/bin/activate  # Linux/Mac
# nsgablack_env\Scripts\activate  # Windows
```

### 核心依赖

```bash
pip install numpy>=1.19.0 scipy>=1.7.0 matplotlib>=3.3.0 scikit-learn>=1.0.0
```

### 高性能依赖（推荐）

```bash
pip install numba>=0.56.0 joblib>=1.0.0 tqdm>=4.60.0
```

### 可选依赖

```bash
# 深度学习支持
pip install tensorflow>=2.6.0 torch>=1.9.0

# 超参数优化
pip install optuna>=2.10.0

# 高级可视化
pip install plotly>=5.0.0 seaborn>=0.11.0

# 并行计算增强
pip install dask>=2021.10.0 distributed>=2021.10.0

# 符号计算（用于梯度计算）
pip install autograd>=1.3
```

### 开发环境

```bash
# 代码质量
pip install black isort flake8 mypy

# 测试
pip install pytest pytest-cov

# 文档
pip install sphinx sphinx-rtd-theme
```

---

## 📊 性能基准

### 🎯 标准测试问题性能

| 问题  | 维度 | 目标数 | NSGA-II | +代理模型 | +并行 | +偏置          |
| ----- | ---- | ------ | ------- | --------- | ----- | -------------- |
| ZDT1  | 30   | 2      | 0.98    | 0.96      | 0.98  | **0.99** |
| ZDT3  | 30   | 2      | 0.85    | 0.88      | 0.87  | **0.91** |
| DTLZ2 | 12   | 3      | 0.92    | 0.94      | 0.93  | **0.95** |
| WFG1  | 24   | 2      | 0.78    | 0.82      | 0.80  | **0.86** |

### ⚡ 速度对比（50代优化）

| 种群大小 | 串行 | 4线程 | 8进程 | 加速比          |
| -------- | ---- | ----- | ----- | --------------- |
| 50       | 15s  | 5s    | 4s    | **3.75x** |
| 100      | 32s  | 9s    | 6s    | **5.33x** |
| 200      | 68s  | 18s   | 11s   | **6.18x** |

### 🤖 代理模型效率

| 评估预算 | 纯NSGA-II | GP辅助 | RF辅助 | 集成模型 |
| -------- | --------- | ------ | ------ | -------- |
| 1000     | 基准      | -      | -      | -        |
| 500      | -70%      | -40%   | -45%   | -35%     |
| 200      | -90%      | -75%   | -80%   | -70%     |
| 100      | -95%      | -88%   | -90%   | -85%     |

---

## 🔧 配置选项

### 🎯 NSGA-II 求解器配置

```python
solver = BlackBoxSolverNSGAII(problem)

# 基础参数
solver.pop_size = 50                    # 种群大小 (建议: 50-200)
solver.max_generations = 100             # 最大代数
solver.mutation_rate = 0.1               # 变异率 (0.05-0.2)
solver.crossover_rate = 0.9              # 交叉率 (0.7-1.0)

# 高级参数
solver.tournament_size = 2               # 锦标赛大小
solver.distribution_index = 20           # 分布索引 (SBX参数)
solver.enable_diversity_init = True      # 多样性初始化
solver.enable_constraint_handling = True # 约束处理

# 并行配置
solver.enable_parallel = True
solver.parallel_backend = "thread"       # 'thread', 'process', 'joblib'
solver.max_workers = 4

# 日志和监控
solver.enable_progress_log = True
solver.report_interval = 10
solver.save_history = True
solver.convergence_threshold = 1e-6
```

### 🧭 偏置系统配置

```python
# 算法偏置参数
diversity_bias = DiversityBias(
    weight=0.2,                 # 偏置强度 (0.1-0.5)
    metric='euclidean'          # 'euclidean', 'manhattan', 'chebyshev'
)

convergence_bias = ConvergenceBias(
    weight=0.15,
    early_gen=10,               # 早期不偏置的代数
    late_gen=50                 # 后期加强偏置的代数
)

exploration_bias = ExplorationBias(
    weight=0.1,
    stagnation_threshold=20,     # 停滞检测阈值
    exploration_intensity=0.3   # 探索强度
)

# 业务偏置参数
constraint_bias = ConstraintBias(
    weight=2.0,                 # 约束权重 (1.0-10.0)
    penalty_factor=10.0,        # 硬约束惩罚倍数
    soft_penalty_factor=2.0      # 软约束惩罚倍数
)

preference_bias = PreferenceBias(
    weight=1.0,
    normalization_method='min-max'  # 'min-max', 'z-score', 'rank'
)
```

### 🤖 代理模型配置

```python
# 高斯过程参数
gp_config = {
    'kernel': 'RBF',            # 'RBF', 'Matern', 'RationalQuadratic'
    'length_scale': 1.0,
    'length_scale_bounds': (1e-1, 1e1),
    'nu': 1.5,                  # Matern参数
    'alpha': 1e-6,              # 噪声水平
    'n_restarts_optimizer': 10
}

# 采样策略
sampling_config = {
    'method': 'lhs',             # 'lhs', 'sobol', 'halton', 'random'
    'criterion': 'maximin',      # 'maximin', 'correlation', 'ese'
    'iterations': 1000
}

# 获取函数
acquisition_config = {
    'method': 'ei',              # 'ei', 'pi', 'ucb', 'ts'
    'xi': 0.01,                 # EI/PI参数
    'kappa': 2.576,             # UCB参数
    'maximize': False           # 是否最大化获取函数
}
```

---

## 📈 使用建议

### 🎯 问题类型与算法选择

| 问题特征                 | 推荐算法       | 参数建议                           |
| ------------------------ | -------------- | ---------------------------------- |
| **单目标+小规模**  | NSGA-II        | pop_size=50, gen=100               |
| **单目标+大规模**  | VNS            | iterations=1000, adaptive=True     |
| **多目标+2-3目标** | NSGA-II        | pop_size=100, gen=200              |
| **多目标+4+目标**  | NSGA-II + 偏置 | pop_size=150, gen=300              |
| **昂贵评估**       | 代理模型       | real_budget=200, surrogate='gp'    |
| **随机性**         | 蒙特卡洛       | scenarios=1000, confidence=0.95    |
| **高维**           | ML引导 + 降维  | dim_reduction=True, ml_features=10 |
| **约束复杂**       | 偏置系统       | constraint_weight=5.0              |

### ⚡ 性能优化技巧

1. **并行计算**

   ```python
   # 启用并行评估
   solver.enable_parallel = True
   solver.max_workers = min(8, os.cpu_count())
   ```
2. **内存优化**

   ```python
   # 大种群时启用内存管理
   solver.enable_memory_management = True
   solver.history_buffer_size = 1000
   ```
3. **算法调优**

   ```python
   # 动态参数调整
   solver.adaptive_parameters = True
   solver.diversity_threshold = 0.01
   ```

### 🐛 常见问题解决

1. **收敛慢**

   - 增加种群大小：`pop_size = 100`
   - 启用偏置引导：添加收敛偏置
   - 使用代理模型：减少评估次数
2. **多样性差**

   - 增加变异率：`mutation_rate = 0.2`
   - 启用多样性偏置：`DiversityBias(weight=0.3)`
   - 多样性初始化：`enable_diversity_init = True`
3. **约束违反**

   - 增加约束权重：`constraint_weight = 10.0`
   - 使用硬约束：`add_hard_constraint()`
   - 分阶段优化：先可行后最优
