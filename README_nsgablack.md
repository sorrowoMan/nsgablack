# nsgablack - 模块化多目标优化框架

一个面向黑箱函数和工程仿真的模块化优化框架，提供 NSGA-II、代理模型、降维等多种优化策略。

## 目录

1. [快速开始](#快速开始)
2. [项目结构](#项目结构)
3. [核心功能](#核心功能)
4. [使用指南](#使用指南)
5. [API参考](#api参考)

---

## 快速开始

### 安装

```bash
# 基础依赖
pip install numpy scipy matplotlib scikit-learn

# 可选依赖（推荐）
pip install numba optuna tqdm joblib tensorflow
```

### 最简单示例

```python
from nsgablack import BlackBoxSolverNSGAII, SphereBlackBox

# 创建问题
problem = SphereBlackBox(dimension=3)

# 创建求解器
solver = BlackBoxSolverNSGAII(problem)
solver.pop_size = 40
solver.max_generations = 50

# 运行优化
solver.initialize_population()
for _ in range(solver.max_generations):
    solver.animate(frame=None)

print(f"最优解: {solver.pareto_solutions['individuals'][0]}")
```

---

## 项目结构

```
nsgablack/
├── core/              # 核心算法
│   ├── base.py       # 问题基类
│   ├── solver.py     # NSGA-II求解器
│   ├── problems.py   # 内置测试问题
│   ├── convergence.py # 收敛性分析
│   ├── diversity.py  # 多样性维护
│   └── elite.py      # 精英策略
│
├── solvers/          # 求解器
│   ├── nsga2.py     # NSGA-II实现
│   ├── surrogate.py  # 代理模型辅助
│   ├── monte_carlo.py # 蒙特卡洛方法
│   └── vns.py       # 变邻域搜索
│
├── utils/            # 工具模块
│   ├── visualization.py # 可视化
│   ├── feature_selection.py # 特征选择
│   ├── manifold_reduction.py # 流形降维
│   ├── bias.py      # 搜索偏向
│   ├── headless.py  # 无界面运行
│   └── parallel_runs.py # 并行运行
│
├── ml/               # 机器学习
│   └── ml_models.py # ML模型管理
│
├── meta/             # 元优化
│   └── metaopt.py   # 超参数优化
│
└── examples/         # 示例代码
```

---

## 核心功能

### 1. 多目标优化 (NSGA-II)

```python
from nsgablack import BlackBoxSolverNSGAII, ZDT1BlackBox

problem = ZDT1BlackBox(dimension=10)
solver = BlackBoxSolverNSGAII(problem)
solver.pop_size = 80
solver.max_generations = 100

solver.initialize_population()
for _ in range(solver.max_generations):
    solver.animate(frame=None)

print(f"Pareto解数量: {len(solver.pareto_solutions['individuals'])}")
```

### 2. 代理模型辅助优化

适用于昂贵的黑箱函数（如仿真）：

```python
from nsgablack.solvers import run_surrogate_assisted

result = run_surrogate_assisted(
    problem,
    surrogate_type='gp',      # 'gp', 'rbf', 'rf', 'ensemble'
    real_eval_budget=200,
    initial_samples=30
)

print(f"真实评估次数: {result['real_eval_count']}")
```

### 3. 特征选择与降维

```python
from nsgablack.utils import UniversalFeatureSelector

selector = UniversalFeatureSelector()
reduced_problem = selector.prepare_reduced_problem(
    objective_func=my_func,
    bounds=bounds,
    n_features=5,
    initial_samples=50
)

# 在降维空间优化
result = run_headless_single_objective(
    reduced_problem['reduced_objective'],
    reduced_problem['reduced_bounds']
)

# 映射回原空间
full_x = reduced_problem['expand_to_full'](result['x'])
```

### 4. 流形降维

```python
from nsgablack.utils import prepare_pca_reduced_problem

reduced = prepare_pca_reduced_problem(
    objective_func=my_func,
    bounds=bounds,
    n_components=3,
    initial_samples=200
)

# 使用降维后的问题
result = optimize(reduced['reduced_objective'], reduced['reduced_bounds'])
full_solution = reduced['expand_to_full'](result['x'])
```

### 5. 智能搜索引导 (Bias)

```python
from nsgablack.utils import create_standard_bias

solver = BlackBoxSolverNSGAII(problem)
solver.enable_bias = True
solver.bias_module = create_standard_bias(
    problem,
    reward_weight=0.05,
    penalty_weight=1.0
)
```

### 6. 并行批量运行

```python
from nsgablack.utils import run_headless_in_parallel

summary = run_headless_in_parallel(
    objective=sphere,
    bounds=bounds,
    n_runs=8,
    backend="process",
    max_generations=50
)

print(f"最优结果: {summary['best_fun']}")
```

### 7. 元优化

```python
from nsgablack.meta import bayesian_meta_optimize

result = bayesian_meta_optimize(
    base_problem_factory=lambda: MyProblem(),
    n_calls=25,
    backend="skopt"
)

best_params = result["best_params"]
print(f"最优超参数: pop_size={best_params.pop_size}")
```

---

## 使用指南

### 定义自己的问题

```python
from nsgablack.core import BlackBoxProblem
import numpy as np

class MyProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(
            name="我的问题",
            dimension=3,
            bounds={'x0': (-5, 5), 'x1': (-5, 5), 'x2': (-5, 5)}
        )

    def evaluate(self, x):
        """单目标优化"""
        return np.sum(x**2)

    def get_num_objectives(self):
        return 1
```

### 带约束的问题

```python
class ConstrainedProblem(BlackBoxProblem):
    def evaluate(self, x):
        return x[0]**2 + x[1]**2

    def evaluate_constraints(self, x):
        # g(x) <= 0 为可行
        return np.array([
            x[0] + x[1] - 1.0,  # x0 + x1 <= 1
            0.2 - x[0]          # x0 >= 0.2
        ])
```

### 多目标问题

```python
class MultiObjectiveProblem(BlackBoxProblem):
    def evaluate(self, x):
        f1 = np.sum(x**2)
        f2 = np.sum((x - 1)**2)
        return np.array([f1, f2])

    def get_num_objectives(self):
        return 2
```

### 无界面运行

```python
from nsgablack.utils import run_headless_single_objective

result = run_headless_single_objective(
    objective=my_func,
    bounds=[(-5, 5)] * 3,
    pop_size=40,
    max_generations=50,
    enable_diversity_init=True
)

print(f"最优解: {result['x']}")
print(f"最优值: {result['fun']}")
```

---

## API参考

### 核心类

#### BlackBoxProblem

```python
BlackBoxProblem(name, dimension, bounds)
```

**方法:**
- `evaluate(x)` - 计算目标函数值
- `evaluate_constraints(x)` - 计算约束违背度
- `get_num_objectives()` - 返回目标数量

#### BlackBoxSolverNSGAII

```python
BlackBoxSolverNSGAII(problem)
```

**主要参数:**
- `pop_size` (int, 默认80) - 种群大小
- `max_generations` (int, 默认150) - 最大代数
- `crossover_rate` (float, 默认0.85) - 交叉概率
- `mutation_rate` (float, 默认0.15) - 变异概率
- `enable_diversity_init` (bool) - 启用多样性初始化
- `enable_elite_retention` (bool) - 启用精英保留

**方法:**
- `initialize_population()` - 初始化种群
- `animate(frame)` - 执行一代进化
- `run()` - 完整运行优化

### 求解器

#### SurrogateAssistedNSGAII

```python
from nsgablack.solvers import SurrogateAssistedNSGAII

solver = SurrogateAssistedNSGAII(problem, surrogate_type='gp')
solver.real_eval_budget = 200
solver.run()
```

**参数:**
- `surrogate_type` - 'gp', 'rbf', 'rf', 'ensemble'
- `real_eval_budget` - 真实评估预算
- `initial_samples` - 初始样本数
- `enable_quality_check` - 启用质量监控

#### BlackBoxSolverVNS

```python
from nsgablack.solvers import BlackBoxSolverVNS

solver = BlackBoxSolverVNS(problem)
solver.max_iterations = 200
solver.k_max = 5
result = solver.run()
```

### 工具函数

#### run_headless_single_objective

```python
from nsgablack.utils import run_headless_single_objective

result = run_headless_single_objective(
    objective,
    bounds,
    pop_size=80,
    max_generations=150,
    enable_diversity_init=False,
    maximize=False
)
```

#### UniversalFeatureSelector

```python
from nsgablack.utils import UniversalFeatureSelector

selector = UniversalFeatureSelector()
selected = selector.smart_feature_selection(
    X, y,
    reduction_method='cumulative',
    threshold=0.95
)
```

#### 降维函数

```python
from nsgablack.utils import (
    prepare_pca_reduced_problem,
    prepare_kpca_reduced_problem,
    prepare_pls_reduced_problem,
    prepare_autoencoder_reduced_problem
)
```

### 内置问题

```python
from nsgablack.core import (
    SphereBlackBox,
    ZDT1BlackBox,
    ExpensiveSimulationBlackBox,
    NeuralNetworkHyperparameterOptimization,
    EngineeringDesignOptimization,
    BusinessPortfolioOptimization
)
```

---

## 高级特性

### 1. 模型保存与加载

```python
# 保存代理模型
solver.save_surrogate('models/my_model.pkl')

# 加载模型
solver.load_surrogate('models/my_model.pkl')
```

### 2. 质量监控

```python
solver.enable_quality_check = True
solver.quality_threshold = 0.6

# 查看质量历史
for metric in solver.model_metrics:
    print(f"R²={metric['r2']:.3f}, RMSE={metric['rmse']:.3f}")
```

### 3. 自定义Bias

```python
from nsgablack.utils import BiasModule

bias = BiasModule()

def my_reward(x):
    return np.exp(-np.linalg.norm(x))

bias.add_reward(my_reward, weight=0.1)
solver.bias_module = bias
```

### 4. 元优化可视化

```python
from nsgablack.meta import bayesian_meta_optimize, plot_metaopt_history

result = bayesian_meta_optimize(...)
plot_metaopt_history(result['history'])
```

---

## 性能优化

### Numba加速

安装numba后自动启用JIT加速：

```bash
pip install numba
```

### 并行运行

```python
from nsgablack.utils import run_headless_in_parallel

summary = run_headless_in_parallel(
    objective=my_func,
    bounds=bounds,
    n_runs=8,
    backend="process",  # 多进程
    max_workers=4
)
```

---

## 示例

查看 `examples/` 目录获取更多示例：

- `bias_example.py` - Bias模块使用
- `monte_carlo_example.py` - 蒙特卡洛方法
- `surrogate_example.py` - 代理模型优化
- `ml_guided_ga_example.py` - ML引导的GA

---

## 许可证

MIT License

---

## 贡献

欢迎提交Issue和Pull Request！
