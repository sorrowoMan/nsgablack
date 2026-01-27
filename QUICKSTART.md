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
git clone https://github.com/sorrowoMan/nsgablack.git
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

# 定义带约束的问题
class ConstrainedProblem(BlackBoxProblem):
    def evaluate(self, x):
        return [x[0]**2, (x[0]-2)**2]

    def evaluate_constraints(self, x):
        # 约束：x[0] + x[1] <= 1 （约定：g(x) <= 0 为可行，>0 为违背度）
        return [max(0, x[0] + x[1] - 1)]

# 求解
problem = ConstrainedProblem()
solver = BlackBoxSolverNSGAII(problem)
result = solver.run()

print("找到满足约束的Pareto解！")
```

---

## 常见使用场景

### 场景1：函数优化

```python
from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.solver import BlackBoxSolverNSGAII
import numpy as np

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

### 1) 用 BiasModule 挂偏置（快速落地业务新想法）

你可以从“领域软约束/倾向”开始：先让算法往你希望的方向走，再慢慢细化为更严格的约束或更专门的算子。

```python
from nsgablack.bias import BiasModule
from nsgablack.bias.domain import CallableBias

bias = BiasModule()

# 例：把“超预算”当作软惩罚（你可以直接把业务逻辑写成一个 callable）
def over_budget_penalty(x, constraints=None, context=None) -> float:
    budget = (constraints or {}).get("budget", None)
    if budget is None:
        return 0.0
    return max(0.0, float(sum(x) - budget))

bias.add(CallableBias("over_budget", over_budget_penalty, weight=1.0))
solver.bias = bias
```

### 2) 用 Adapter 做“算法角色化/阶段化”

当你发现“单一算法底座不够用”，最稳的做法是把策略拆成 Adapter，然后用 Suite/Controller 负责装配与协同。

```python
from nsgablack.core.adapters import VNSAdapter, MultiStrategyControllerAdapter, StrategySpec

controller = MultiStrategyControllerAdapter(
    strategies=[
        StrategySpec(name="vns_refine", adapter=VNSAdapter()),
    ]
)
solver.adapter = controller
```

提示：不知道有什么可用的 Adapter/Plugin/Suite？直接用 Catalog 搜：

```bash
python -m nsgablack catalog search vns
python -m nsgablack catalog search suite
```

### 3) 昂贵评估：用 surrogate_evaluation 插件接入代理模型（可选）

代理模型在框架里被当作“插件能力”，不侵入 Problem/Representation/Bias 的核心结构：

- 你先把 `problem.evaluate(x)` 写稳定
- 再用 `utils/plugins/surrogate_evaluation.py` 把“少量真实评估 + 大量代理预测”接进流程

对应细节请直接看：`docs/user_guide/surrogate_workflow.md`

---

## 故障排除

### 问题1：导入错误

**错误**：`ModuleNotFoundError: No module named 'nsgablack'`

**解决方案**：
```bash
# 方案 A（推荐）：开发模式安装
cd nsgablack
pip install -e .

# 方案 B：从项目上一级目录运行
cd ..
python -m nsgablack ...

# 方案 C：临时加 PYTHONPATH（Windows PowerShell）
$env:PYTHONPATH=".."
python -m nsgablack ...
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

# 需要时再接入 surrogate 插件（减少真实评估次数）
# 参考：docs/user_guide/surrogate_workflow.md
```

### 问题4：收敛速度慢

**解决方案**：
```python
# 加入更贴合问题的 Bias（领域/算法/信号驱动）
# 参考：docs/guides/DECOUPLING_BIAS.md

# 调整变异率
solver.mutation_prob = 0.2  # 增加变异率
```

### 问题5：结果不理想

**解决方案**：
```python
# 增加迭代次数
solver.max_generations = 500

# 增大种群
solver.pop_size = 200

# 尝试不同算法
如果你想快速跑通“现代路径”，建议使用 `BlackBoxSolverNSGAII` 或 `BlankSolverBase` / `ComposableSolver`，并通过 Pipeline/Bias/Plugin/Adapter/Suite 组合。

提示：不确定“有什么可用组件”时，用 Catalog 搜索：
```bash
python -m nsgablack catalog search vns
python -m nsgablack catalog search suite
```
```

---

## 下一步

现在你已经掌握了基础，可以：

1. **阅读详细文档**：
   - `START_HERE.md` - 入口地图（最短路径 + 索引）
   - `WORKFLOW_END_TO_END.md` - 面对一个问题的端到端落地流程
   - `docs/user_guide/catalog.md` - Catalog / Suites 的用法

2. **探索示例**：
   ```bash
   cd examples
   python end_to_end_workflow_demo.py
   python blank_vs_composable_demo.py
   python multi_strategy_coop_demo.py
   ```

3. **查看测试**：
   ```bash
   pytest -q
   ```

4. **运行基准测试**：
   ```bash
   python -m nsgablack catalog show suite.benchmark_harness
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
# 先用 Suite 跑通官方权威组合（避免漏配），再逐步替换其中某一块做实验。
# 参考：docs/user_guide/catalog.md + docs/AUTHORITATIVE_EXAMPLES.md

result = solver.run()
```

---

**祝你优化愉快！如有问题，请查看[完整文档](docs/)或提交Issue。**
