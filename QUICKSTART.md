# nsgablack 快速开始指南

<div align="center">

**5分钟上手 - 从安装到第一个优化结果**

</div>

---

## 目录

- [安装](#安装)
- [5分钟快速体验](#5分钟快速体验)
- [常见使用场景](#常见使用场景)
- [进阶使用](#进阶使用)
- [故障排除](#故障排除)

---

## 安装

### 1. 克隆项目

```bash
git clone https://github.com/yourusername/nsgablack.git
cd nsgablack
```

### 2. 安装依赖

```bash
# 核心依赖（必需）
pip install -r requirements-core.txt

# 标准依赖（推荐）
pip install -r requirements.txt

# 开发依赖（可选）
pip install -r requirements-dev.txt
```

### 3. 验证安装

```python
python -c "from nsgablack.core import ZDT1BlackBox, BlackBoxSolverNSGAII; print('安装成功!')"
```

---

## 5分钟快速体验

### 示例1：最简单的多目标优化

```python
from nsgablack.core import ZDT1BlackBox, BlackBoxSolverNSGAII

# 创建标准测试问题
problem = ZDT1BlackBox(dimension=10)

# 创建求解器并运行
solver = BlackBoxSolverNSGAII(problem)
result = solver.run()

# 查看结果
print(f"找到 {len(result['pareto_solutions'])} 个Pareto最优解")
print(f"运行时间: {result['elapsed_time']:.2f} 秒")
```

**预期输出**：
```
找到 100 个Pareto最优解
运行时间: 3.45 秒
```

### 示例2：自定义问题

```python
from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.solver import BlackBoxSolverNSGAII
import numpy as np

# 定义自己的问题
class MyProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(
            name="SimpleProblem",
            dimension=2,
            bounds={'x1': [0, 10], 'x2': [0, 10]}
        )

    def evaluate(self, x):
        # 两个目标：最小化到原点和到(10,10)的距离
        f1 = x[0]**2 + x[1]**2
        f2 = (x[0]-10)**2 + (x[1]-10)**2
        return [f1, f2]

# 求解
problem = MyProblem()
solver = BlackBoxSolverNSGAII(problem)
solver.pop_size = 50
solver.max_generations = 100
result = solver.run()

# 查看最优解
best_idx = np.argmin([np.mean(obj) for obj in result['pareto_objectives']])
print(f"最优解: {result['pareto_solutions'][best_idx]}")
print(f"目标值: {result['pareto_objectives'][best_idx]}")
```

### 示例3：带约束的优化

```python
from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.solver import BlackBoxSolverNSGAII
from nsgablack.bias.bias_v2 import UniversalBiasManager
from nsgablack.bias.bias_library_domain import ConstraintBias

# 定义带约束的问题
class ConstrainedProblem(BlackBoxProblem):
    def evaluate(self, x):
        return [x[0]**2, (x[0]-2)**2]

    def evaluate_constraints(self, x):
        # 约束：x[0] + x[1] <= 1
        return [max(0, x[0] + x[1] - 1)]

# 使用约束偏置
bias_manager = UniversalBiasManager()
constraint_bias = ConstraintBias(weight=10.0)
constraint_bias.add_hard_constraint(lambda x: max(0, x[0] + x[1] - 1))
bias_manager.domain_manager.add_bias(constraint_bias)

# 求解
problem = ConstrainedProblem()
solver = BlackBoxSolverNSGAII(problem)
solver.bias_manager = bias_manager
solver.enable_bias = True
result = solver.run()

print("找到满足约束的Pareto解！")
```

---

## 常见使用场景

### 场景1：函数优化

```python
from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.solver import BlackBoxSolverNSGAII

# 数学函数优化
class FunctionOptimization(BlackBoxProblem):
    def __init__(self):
        super().__init__(
            name="FunctionOpt",
            dimension=5,
            bounds={f'x{i}': [-10, 10] for i in range(5)}
        )

    def evaluate(self, x):
        # Rastrigin函数（多峰函数）
        A = 10
        f1 = A * len(x) + sum([(xi**2 - A * np.cos(2 * np.pi * xi)) for xi in x])
        # Sphere函数
        f2 = sum([xi**2 for xi in x])
        return [f1, f2]

problem = FunctionOptimization()
solver = BlackBoxSolverNSGAII(problem)
solver.pop_size = 100
solver.max_generations = 200
result = solver.run()
```

### 场景2：TSP旅行商问题

```python
from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.solver import BlackBoxSolverNSGAII
import numpy as np

class TSPProblem(BlackBoxProblem):
    def __init__(self, cities):
        n = len(cities)
        super().__init__(
            "TSP",
            dimension=n,
            bounds={f'x{i}': [0, 1] for i in range(n)}
        )
        self.cities = np.array(cities)

    def evaluate(self, x):
        # 连续编码：通过排序得到访问顺序
        tour_order = np.argsort(x)
        tour = self.cities[tour_order]

        # 计算总距离
        distances = np.sqrt(np.sum(np.diff(tour, axis=0)**2, axis=1))
        total_distance = np.sum(distances) + np.sqrt(np.sum((tour[-1] - tour[0])**2))
        return [total_distance]

# 随机生成20个城市
cities = np.random.rand(20, 2)

# 求解
problem = TSPProblem(cities)
solver = BlackBoxSolverNSGAII(problem)
solver.pop_size = 100
solver.max_generations = 500
result = solver.run()

# 获取最优路径
best_solution = result['pareto_solutions'][0]
best_tour = np.argsort(best_solution)
print(f"最短路径访问顺序: {best_tour}")
```

### 场景3：机器学习超参数优化

```python
from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.solver import BlackBoxSolverNSGAII
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score
from sklearn.datasets import load_iris

class HyperparameterTuning(BlackBoxProblem):
    def __init__(self, X, y):
        super().__init__(
            "HyperparameterTuning",
            dimension=3,
            bounds={
                'n_estimators': [10, 200],
                'max_depth': [3, 30],
                'min_samples_split': [2, 20]
            }
        )
        self.X = X
        self.y = y

    def evaluate(self, x):
        # 解码超参数
        n_estimators = int(x[0])
        max_depth = int(x[1])
        min_samples_split = int(x[2])

        # 训练模型
        model = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            min_samples_split=min_samples_split,
            random_state=42
        )

        # 交叉验证
        scores = cross_val_score(model, self.X, self.y, cv=5)

        # 目标：错误率和模型复杂度
        error_rate = 1 - scores.mean()
        complexity = n_estimators * max_depth / 1000

        return [error_rate, complexity]

# 加载数据
X, y = load_iris(return_X_y=True)

# 优化
problem = HyperparameterTuning(X, y)
solver = BlackBoxSolverNSGAII(problem)
solver.pop_size = 30
solver.max_generations = 50
result = solver.run()

# 分析结果
for i, (sol, obj) in enumerate(zip(result['pareto_solutions'][:5], result['pareto_objectives'][:5])):
    print(f"解{i+1}: n_estimators={int(sol[0])}, max_depth={int(sol[1])}, "
          f"error_rate={obj[0]:.4f}, complexity={obj[1]:.4f}")
```

---

## 进阶使用

### 1. 使用偏置系统

```python
from nsgablack.bias.bias_v2 import UniversalBiasManager
from nsgablack.bias.bias_library_algorithmic import (
    DiversityBias, SimulatedAnnealingBias
)

# 创建偏置管理器
bias_manager = UniversalBiasManager()

# 添加多样性偏置
bias_manager.algorithmic_manager.add_bias(
    DiversityBias(weight=0.2)
)

# 添加模拟退火偏置
bias_manager.algorithmic_manager.add_bias(
    SimulatedAnnealingBias(
        initial_weight=0.15,
        initial_temperature=100.0,
        cooling_rate=0.99
    )
)

# 应用到求解器
solver.bias_manager = bias_manager
solver.enable_bias = True
result = solver.run()
```

### 2. 使用多智能体系统

```python
from nsgablack.solvers.multi_agent import MultiAgentBlackBoxSolver

# 创建多智能体求解器
solver = MultiAgentBlackBoxSolver(problem)

# 自定义配置
from nsgablack.solvers.multi_agent import AgentRole

config = {
    'total_population': 200,
    'agent_ratios': {
        AgentRole.EXPLORER: 0.3,     # 探索者
        AgentRole.EXPLOITER: 0.4,    # 开发者
        AgentRole.WAITER: 0.2,       # 等待者
        AgentRole.COORDINATOR: 0.1   # 协调者
    },
    'max_generations': 200
}

solver = MultiAgentBlackBoxSolver(problem, config=config)
result = solver.run()
```

### 3. 并行加速

```python
from nsgablack.utils.parallel_evaluator import ParallelEvaluator

# 创建并行评估器
evaluator = ParallelEvaluator(
    backend='multiprocessing',
    max_workers=8
)

# 应用到求解器
solver.parallel_evaluator = evaluator
result = solver.run()  # 自动并行加速
```

### 4. 实时可视化

```python
from nsgablack.utils.visualization import SolverVisualizationMixin

class VisualSolver(SolverVisualizationMixin, BlackBoxSolverNSGAII):
    def __init__(self, problem):
        super().__init__(problem)
        self.enable_visualization = True
        self.plot_interval = 10

# 运行（弹出可视化窗口）
solver = VisualSolver(problem)
solver.run()
```

### 5. 使用代理模型（昂贵评估）

```python
from nsgablack.solvers.surrogate import EnsembleSurrogate
from nsgablack.utils.surrogate_model import SurrogateModel

# 创建集成代理模型
surrogate = EnsembleSurrogate([
    SurrogateModel('gaussian_process'),
    SurrogateModel('random_forest'),
    SurrogateModel('rbf_network')
])

# 应用到求解器
solver.surrogate_model = surrogate
solver.evaluation_budget = 500  # 限制真实评估次数
result = solver.run()
```

---

## 故障排除

### 问题1：导入错误

**错误**：`ModuleNotFoundError: No module named 'nsgablack'`

**解决方案**：
```bash
# 确保在项目根目录
cd nsgablack

# 安装项目
pip install -e .

# 或者添加到Python路径
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### 问题2：依赖缺失

**错误**：`ImportError: No module named 'sklearn'`

**解决方案**：
```bash
pip install scikit-learn
```

### 问题3：内存不足

**错误**：`MemoryError` 或程序崩溃

**解决方案**：
```python
# 减小种群大小
solver.pop_size = 50  # 从100减少到50

# 启用内存优化
solver.enable_memory_optimization = True

# 使用代理模型减少评估次数
solver.surrogate_model = surrogate
solver.evaluation_budget = 200
```

### 问题4：收敛速度慢

**解决方案**：
```python
# 启用偏置系统
solver.bias_manager = bias_manager
solver.enable_bias = True

# 调整变异率
solver.mutation_prob = 0.2  # 增加变异率

# 使用多智能体系统
solver = MultiAgentBlackBoxSolver(problem)
```

### 问题5：结果不理想

**解决方案**：
```python
# 增加迭代次数
solver.max_generations = 500

# 增大种群
solver.pop_size = 200

# 尝试不同算法
from nsgablack.solvers import BlackBoxSolverMOEAD
solver = BlackBoxSolverMOEAD(problem)
```

---

## 下一步

现在你已经掌握了基础，可以：

1. **阅读详细文档**：
   - [多智能体系统](MULTI_AGENT_SYSTEM.md) - 了解多智能体优化
   - [API指南](API_GUIDE.md) - 完整API参考
   - [偏置系统](docs/bias_system_guide.md) - 深入偏置系统

2. **探索示例**：
   ```bash
   cd examples
   python bias_demo_minimal.py
   python intelligent_bias_system_demo.py
   python tsp_simple_demo.py
   ```

3. **查看测试**：
   ```bash
   python test/run_tests.py
   ```

4. **运行基准测试**：
   ```bash
   python test/performance_comparison.py
   ```

---

## 常用配置模板

### 快速模板（小规模问题）

```python
solver = BlackBoxSolverNSGAII(problem)
solver.pop_size = 50
solver.max_generations = 100
result = solver.run()
```

### 标准模板（中等规模问题）

```python
solver = BlackBoxSolverNSGAII(problem)
solver.pop_size = 100
solver.max_generations = 200
solver.enable_convergence_detection = True
result = solver.run()
```

### 高级模板（大规模问题）

```python
# 使用多智能体系统
solver = MultiAgentBlackBoxSolver(problem, config={
    'total_population': 400,
    'max_generations': 500
})

# 启用并行
solver.parallel_evaluator = ParallelEvaluator(max_workers=8)

# 启用偏置系统
solver.bias_manager = bias_manager
solver.enable_bias = True

result = solver.run()
```

---

**祝你优化愉快！如有问题，请查看[完整文档](docs/)或提交Issue。**
