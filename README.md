# nsgablack - 模块化多目标优化框架

一个面向黑箱函数和工程仿真的模块化优化框架，提供 NSGA-II、代理模型、降维、偏置引导等多种优化策略。

## 📋 目录

- [🚀 快速开始](#-快速开始)
- [✨ 核心功能](#-核心功能)
  - [1. 并行种群评估 ⚡](#1-并行种群评估-)
  - [2. 多目标优化 (NSGA-II)](#2-多目标优化-nsga-ii)
  - [3. 代理模型辅助优化](#3-代理模型辅助优化)
  - [4. 偏置引导优化](#4-偏置引导优化)
  - [5. 蒙特卡洛优化](#5-蒙特卡洛优化)
  - [6. 变邻域搜索 (VNS)](#6-变邻域搜索-vns)
  - [7. 机器学习引导的优化](#7-机器学习引导的优化)
- [🛠️ 安装依赖](#️-安装依赖)
- [📊 示例结果](#-示例结果)
- [🔧 配置选项](#-配置选项)
- [📈 性能优化建议](#-性能优化建议)
- [🤝 贡献指南](#-贡献指南)
- [📄 许可证](#-许可证)
- [🙏 致谢](#-致谢)

## 🚀 快速开始

### 运行示例

项目现在支持直接运行示例文件，无需额外配置：

```bash
# 运行并行评估示例（推荐用于昂贵函数）
python examples/parallel_evaluation_example_fixed.py

# 运行基础偏置优化示例
python examples/bias_example.py

# 运行代理模型辅助优化
python examples/surrogate_example.py

# 运行蒙特卡洛优化示例
python examples/monte_carlo_example.py

# 运行多目标优化示例
python examples/examples.py
```

### 基础使用

```python
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.base import BlackBoxProblem
from core.solver import BlackBoxSolverNSGAII
from utils.bias import BiasModule, create_standard_bias

# 定义问题
class SphereProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="Sphere", dimension=2, bounds={'x0': (-5, 5), 'x1': (-5, 5)})

    def evaluate(self, x):
        return np.sum(x**2)

# 创建求解器
solver = BlackBoxSolverNSGAII(problem)
solver.pop_size = 40
solver.max_generations = 50
solver.enable_progress_log = True

# 运行优化
result = solver.run()
print(f"最优解: {result['pareto_solutions']['individuals'][0]}")
```

## 📁 项目结构

```
nsgablack/
├── core/                     # 核心算法模块
│   ├── base.py              # BlackBoxProblem 基类
│   ├── solver.py            # NSGA-II 求解器
│   ├── problems.py          # 内置测试问题
│   ├── convergence.py       # 收敛性分析
│   ├── diversity.py         # 多样性维护
│   └── elite.py             # 精英策略
│
├── solvers/                 # 专门求解器
│   ├── nsga2.py            # NSGA-II 实现
│   ├── surrogate.py        # 代理模型辅助优化
│   ├── monte_carlo.py      # 蒙特卡洛方法
│   └── vns.py              # 变邻域搜索
│
├── utils/                   # 工具模块
│   ├── bias.py             # 偏置引导模块
│   ├── visualization.py    # 可视化工具
│   ├── headless.py         # 无界面运行
│   ├── parallel_runs.py    # 并行运行支持
│   └── reduced.py          # 降维工具
│
├── ml/                      # 机器学习模块
│   └── ml_models.py        # ML 模型管理
│
├── meta/                    # 元优化
│   └── metaopt.py          # 超参数优化
│
└── examples/                # 示例代码
    ├── bias_example.py              # 偏置优化示例
    ├── surrogate_example.py         # 代理模型示例
    ├── monte_carlo_example.py       # 蒙特卡洛示例
    ├── ml_guided_ga_example.py      # ML+GA 示例
    └── experiment_tracking_example.py # 实验跟踪示例
```

## ✨ 核心功能

### 1. 并行种群评估 ⚡

**针对昂贵函数优化的加速利器**，支持多线程/多进程并行评估，显著提升优化效率。

```python
from utils.parallel_evaluator import ParallelEvaluator

# 创建并行评估器
evaluator = ParallelEvaluator(
    backend="thread",        # 后端: 'thread' | 'process' | 'joblib'
    max_workers=4,          # 工作线程/进程数
    chunk_size=10,          # 批次大小
    enable_load_balancing=True  # 负载均衡
)

# 并行评估种群
objectives, violations = evaluator.evaluate_population(population, problem)
```

**性能提升**：

- 种群规模 50：**3-4倍加速**
- 种群规模 100：**4-5倍加速**
- 适用于：CAE仿真、CFD计算、机器学习模型训练等昂贵评估

### 2. 多目标优化 (NSGA-II)

problem = ZDT1BlackBox(dimension=10)
solver = BlackBoxSolverNSGAII(problem)
solver.pop_size = 80
solver.max_generations = 100
solver.enable_progress_log = True

result = solver.run()
print(f"Pareto解数量: {len(result['pareto_solutions']['individuals'])}")

### 3.代理模型辅助优化

```

### 3. 代理模型辅助优化

适用于昂贵的黑箱函数（如工程仿真）：

```python
from solvers.surrogate import run_surrogate_assisted

result = run_surrogate_assisted(
    problem,
    surrogate_type='gp',      # 'gp', 'rbf', 'rf', 'ensemble'
    real_eval_budget=200,
    initial_samples=30
)

print(f"真实评估次数: {result['real_eval_count']}")
```

### 4. 偏置引导优化

使用 BiasModule 引导搜索方向：

```python
from utils.bias import BiasModule, create_standard_bias

# 创建偏置模块
bias = create_standard_bias(
    problem,
    reward_weight=0.05,    # 奖励权重
    penalty_weight=1.0     # 惩罚权重
)

# 启用偏置
solver.enable_bias = True
solver.bias_module = bias
```

#### 自定义偏置函数

```python
# 添加自定义奖励：接近特定点
def proximity_reward(x):
    target = np.array([1.0, 1.0])
    distance = np.linalg.norm(x - target)
    return np.exp(-distance)

bias.add_reward(proximity_reward, weight=0.1, name="proximity")
```

### 5. 蒙特卡洛优化

处理随机性问题：

```python
from solvers.monte_carlo import (
    StochasticProblem, optimize_with_monte_carlo
)

class StochasticInventory(StochasticProblem):
    def evaluate_scenario(self, x, scenario):
        # 对每个随机场景的评估
        demand = scenario['demand']
        inventory_cost = 0.1 * x[0]
        shortage_cost = max(0, demand - x[0]) * 10
        return inventory_cost + shortage_cost

result = optimize_with_monte_carlo(
    problem=StochasticInventory(),
    n_scenarios=1000,
    confidence_level=0.95
)
```

### 6. 变邻域搜索 (VNS)

```python
from solvers.vns import BlackBoxSolverVNS

solver = BlackBoxSolverVNS(problem)
solver.max_iterations = 100
solver.enable_bias = True  # 支持 BiasModule

result = solver.run()
print(f"最优解: {result['best_x']}")
```

### 7. 机器学习引导的优化

使用分类器过滤劣质解：

```python
from ml.ml_models import ModelManager
from core.diversity import ClassifierHistoryAwareInitializer

# 训练分类器区分好/坏解
model_manager = ModelManager()
model_manager.train_classifier(samples, labels)

# 使用分类器引导初始化
initializer = ClassifierHistoryAwareInitializer(
    model_manager.classifier,
    similarity_threshold=0.1
)
```

## 🛠️ 安装依赖

```bash
# 基础依赖
pip install numpy scipy matplotlib scikit-learn

# 推荐依赖
pip install numba joblib tqdm

# 可选依赖（用于高级功能）
pip install optuna tensorflow
```

## 📊 示例结果

运行示例的预期输出：

```bash
$ python examples/bias_example.py

============================================================
示例 1: 基础使用 - 标准 bias 配置
============================================================
[进度] 第10代 | 拥挤度距离: 0.003532 | 最优解: [-0.210514,  0.095997]
[进度] 第20代 | 拥挤度距离: 0.028814 | 最优解: [-0.152567,  0.208182]
...

最优解: [-0.33908839  1.30004826]
最优值: [1.78478631]
```

## 🔧 配置选项

### NSGA-II 求解器配置

```python
solver = BlackBoxSolverNSGAII(problem)
solver.pop_size = 40              # 种群大小
solver.max_generations = 50       # 最大代数
solver.mutation_rate = 0.1        # 变异率
solver.crossover_rate = 0.9       # 交叉率
solver.enable_diversity_init = True  # 多样性初始化
solver.enable_progress_log = True   # 进度日志
solver.report_interval = 10        # 报告间隔
```

### 偏置模块配置

```python
# 标准偏置配置
bias = create_standard_bias(
    problem,
    reward_weight=0.05,      # 奖励权重 (建议 0.01-0.1)
    penalty_weight=1.0       # 惩罚权重 (建议 1.0-10.0)
)

# 或手动配置
bias = BiasModule()
bias.add_reward(my_reward_func, weight=0.1, name="custom_reward")
bias.add_penalty(my_penalty_func, weight=5.0, name="constraint_penalty")
```

## 📈 性能优化建议

1. **昂贵的仿真**：使用代理模型辅助优化
2. **高维问题**：使用降维预处理
3. **随机问题**：使用蒙特卡洛方法
4. **约束问题**：使用偏置模块的约束罚函数
5. **大搜索空间**：启用多样性初始化

## 🤝 贡献指南

1. Fork 项目
2. 创建特性分支：`git checkout -b feature/AmazingFeature`
3. 提交更改：`git commit -m 'Add some AmazingFeature'`
4. 推送分支：`git push origin feature/AmazingFeature`
5. 开启 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🙏 致谢

- NSGA-II 算法基于 Deb 等人的工作
- 代理模型实现借鉴了多个开源优化库
- 感谢所有贡献者的反馈和建议

## 📚 更多文档

- [快速入门指南](docs/QUICKSTART.md) - 5分钟上手教程
- [API 参考文档](docs/API_REFERENCE.md) - 详细的 API 文档
- [示例代码](examples/) - 各种使用场景的完整示例

## 🔗 相关链接

- [NSGA-II 算法论文](https://ieeexplore.ieee.org/document/996017)
- [代理模型优化综述](https://www.sciencedirect.com/science/article/pii/S0377221719308168)
- [Python 优化工具对比](https://github.com/jvkersch/pyopt-benchmark)

---

**注意**：项目已修复导入问题，现在可以直接运行 `python examples/*.py` 来测试各种功能！
