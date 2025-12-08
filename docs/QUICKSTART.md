# 快速入门指南

本指南将帮助您在 5 分钟内开始使用 nsgablack 优化框架。

## 第一步：环境准备

确保您已安装必要的依赖：

```bash
# 基础依赖
pip install numpy scipy matplotlib scikit-learn

# 可选但推荐的依赖
pip install numba joblib tqdm
```

## 第二步：运行第一个示例

直接运行项目中的示例：

```bash
cd nsgablack
python examples/bias_v2_example.py
```

您应该看到类似这样的输出：

```
============================================================
偏置系统 v2.0 示例 - 双重架构演示
============================================================
[OK] 创建偏置管理器成功
[OK] 添加算法偏置: 多样性偏置 (weight=0.2)
[OK] 添加业务偏置: 约束偏置 (weight=1.5)
[OK] 计算偏置值: 0.0000
...
```

## 第三步：创建您自己的优化问题

### 简单单目标优化

```python
import numpy as np
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.base import BlackBoxProblem
from core.solver import BlackBoxSolverNSGAII

# 1. 定义您的问题
class MyOptimizationProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(
            name="我的优化问题",
            dimension=2,
            bounds={'x0': (-5, 5), 'x1': (-5, 5)}
        )

    def evaluate(self, x):
        # 定义您的目标函数
        # 这里以简单的球函数为例：最小化 x^2 + y^2
        return x[0]**2 + x[1]**2

# 2. 创建问题实例
problem = MyOptimizationProblem()

# 3. 创建求解器
solver = BlackBoxSolverNSGAII(problem)
solver.pop_size = 50
solver.max_generations = 100
solver.enable_progress_log = True

# 4. 运行优化
result = solver.run()

# 5. 查看结果
best_solution = result['pareto_solutions']['individuals'][0]
best_value = result['pareto_solutions']['objectives'][0]

print(f"最优解: {best_solution}")
print(f"最优值: {best_value}")
```

### 添加约束

```python
class ConstrainedProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(
            name="约束优化问题",
            dimension=2,
            bounds={'x0': (0, 5), 'x1': (0, 5)}
        )

    def evaluate(self, x):
        # 目标函数：最小化成本
        return x[0] + x[1]

    def evaluate_constraints(self, x):
        # 约束条件：g(x) <= 0
        # 约束1: x0 + x1 >= 3  =>  3 - x0 - x1 <= 0
        # 约束2: x0 >= 1         =>  1 - x0 <= 0
        return np.array([
            3 - x[0] - x[1],  # 约束1
            1 - x[0]          # 约束2
        ])

# 使用偏置系统 v2.0 处理约束
from utils.bias_v2 import UniversalBiasManager, ConstraintBias

problem = ConstrainedProblem()
solver = BlackBoxSolverNSGAII(problem)
solver.enable_bias = True

# 创建约束偏置
bias_manager = UniversalBiasManager()
constraint_bias = ConstraintBias(weight=10.0)

# 添加约束函数
constraint_bias.add_hard_constraint(lambda x: max(0, 3 - x[0] - x[1]))
constraint_bias.add_hard_constraint(lambda x: max(0, 1 - x[0]))

bias_manager.domain_manager.add_bias(constraint_bias)
solver.bias_manager = bias_manager

result = solver.run()
```

### 多目标优化

```python
class MultiObjectiveProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(
            name="多目标问题",
            dimension=3,
            bounds={'x0': (0, 1), 'x1': (0, 1), 'x2': (0, 1)}
        )

    def evaluate(self, x):
        # 多个目标函数
        f1 = x[0] + x[1] + x[2]            # 最小化总和
        f2 = np.sqrt(x[0]**2 + x[1]**2 + x[2]**2)  # 最小化欧氏距离
        return np.array([f1, f2])

    def get_num_objectives(self):
        return 2  # 告诉求解器这是多目标问题

problem = MultiObjectiveProblem()
solver = BlackBoxSolverNSGAII(problem)
solver.pop_size = 100
solver.max_generations = 150

result = solver.run()

print(f"找到 {len(result['pareto_solutions']['individuals'])} 个 Pareto 解")
for i in range(min(5, len(result['pareto_solutions']['individuals']))):
    obj = result['pareto_solutions']['objectives'][i]
    print(f"解 {i+1}: 目标值 = {obj}")
```

## 第四步：使用高级功能

### 代理模型辅助优化（适合昂贵函数）

```python
from solvers.surrogate import run_surrogate_assisted

# 当您的函数评估很耗时（如需要调用仿真软件）
class ExpensiveProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__("昂贵函数", dimension=5, bounds={f'x{i}': (0, 1) for i in range(5)})

    def evaluate(self, x):
        # 模拟昂贵的计算
        import time
        time.sleep(0.1)  # 假设每次评估需要 0.1 秒
        return np.sum(x**2)

# 使用代理模型减少真实评估次数
result = run_surrogate_assisted(
    problem=ExpensiveProblem(),
    surrogate_type='gp',      # 高斯过程代理模型
    real_eval_budget=50,      # 只允许 50 次真实评估
    initial_samples=10        # 初始样本数
)

print(f"使用代理模型，仅用 {result['real_eval_count']} 次真实评估")
```

### 自定义偏置函数

```python
from utils.bias_v2 import UniversalBiasManager, PreferenceBias, PrecisionBias

class CustomProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__("自定义问题", dimension=2, bounds={'x0': (-10, 10), 'x1': (-10, 10)})

    def evaluate(self, x):
        # Rosenbrock 函数（全局最优在 [1, 1]）
        return 100 * (x[1] - x[0]**2)**2 + (1 - x[0])**2

problem = CustomProblem()

# 创建偏置管理器
bias_manager = UniversalBiasManager()

# 添加算法偏置：精度偏置，在已知好解附近搜索
precision_bias = PrecisionBias(weight=0.2, precision_radius=0.5)
precision_bias.add_good_solution(np.array([1.0, 1.0]))  # 已知的最优解
bias_manager.algorithmic_manager.add_bias(precision_bias)

# 添加业务偏置：偏好偏置，引导向特定目标
preference_bias = PreferenceBias(weight=1.0)
preference_bias.set_preference('distance_to_optimal', 'minimize', weight=2.0)
bias_manager.domain_manager.add_bias(preference_bias)
solver = BlackBoxSolverNSGAII(problem)
solver.enable_bias = True
solver.bias_manager = bias_manager

result = solver.run()
```

## 常见使用场景

### 1. 参数调优

```python
# 调优机器学习模型的超参数
class HyperparameterTuning(BlackBoxProblem):
    def __init__(self):
        super().__init__(
            name="超参数调优",
            dimension=3,
            bounds={
                'learning_rate': (0.001, 0.1),
                'batch_size': (16, 128),
                'hidden_units': (32, 256)
            }
        )

    def evaluate(self, x):
        lr, batch_size, hidden = int(x[0] * 1000) / 1000, int(x[1]), int(x[2])

        # 这里训练您的模型并返回验证损失
        # val_loss = train_model(lr, batch_size, hidden)
        # 返回模拟的验证损失
        return (lr - 0.01)**2 + (batch_size - 64)**2 / 1000 + (hidden - 128)**2 / 10000
```

### 2. 工程设计

```python
# 工程设计优化（如结构优化、流体力学等）
class EngineeringDesign(BlackBoxProblem):
    def __init__(self):
        super().__init__(
            name="结构设计优化",
            dimension=4,
            bounds={
                'length': (1.0, 10.0),
                'width': (0.5, 5.0),
                'height': (0.5, 5.0),
                'thickness': (0.1, 1.0)
            }
        )

    def evaluate(self, x):
        length, width, height, thickness = x

        # 目标1：最小化重量
        weight = length * width * height * thickness

        # 目标2：最大化强度（简化模型）
        strength = thickness * (width + height) / length

        # 返回负的强度（因为我们要最小化）
        return np.array([weight, -strength])

    def get_num_objectives(self):
        return 2
```

### 3. 投资组合优化

```python
# 投资组合优化
class PortfolioOptimization(BlackBoxProblem):
    def __init__(self, n_assets=5):
        bounds = {f'asset_{i}': (0, 1) for i in range(n_assets)}
        super().__init__(
            name="投资组合优化",
            dimension=n_assets,
            bounds=bounds
        )
        self.expected_returns = np.random.randn(n_assets) * 0.1  # 预期收益率
        self.cov_matrix = np.random.randn(n_assets, n_assets) * 0.01  # 协方差矩阵
        self.cov_matrix = self.cov_matrix @ self.cov_matrix.T  # 确保正定

    def evaluate(self, x):
        # 归一化权重
        weights = x / np.sum(x)

        # 目标1：最大化预期收益
        expected_return = np.sum(weights * self.expected_returns)

        # 目标2：最小化风险（方差）
        risk = np.sqrt(weights @ self.cov_matrix @ weights.T)

        # 返回负收益（最小化）和风险
        return np.array([-expected_return, risk])

    def get_num_objectives(self):
        return 2
```

## 调试和故障排除

### 常见问题

1. **导入错误**
   ```python
   # 确保添加了路径设置
   import sys, os
   sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
   ```

2. **收敛问题**
   ```python
   # 尝试增加种群大小或代数
   solver.pop_size = 100  # 增加种群
   solver.max_generations = 200  # 增加代数

   # 启用多样性初始化
   solver.enable_diversity_init = True
   ```

3. **约束违反**
   ```python
   # 增加约束惩罚权重
   from utils.bias_v2 import UniversalBiasManager, ConstraintBias

   bias_manager = UniversalBiasManager()
   constraint_bias = ConstraintBias(weight=10.0)
   # 添加问题的约束...
   bias_manager.domain_manager.add_bias(constraint_bias)
   solver.bias_manager = bias_manager
   ```

### 性能监控

```python
# 启用详细的进度日志
solver.enable_progress_log = True
solver.report_interval = 5  # 每 5 代报告一次

# 运行后查看收敛历史
if 'convergence_metrics' in result:
    metrics = result['convergence_metrics']
    print("收敛历史:")
    for i, metric in enumerate(metrics[-5:]):  # 显示最后 5 个
        print(f"代 {i}: 最佳值 = {metric['best_objective']}")
```

## 下一步

现在您已经掌握了基础知识，可以：

1. 查看 `examples/` 目录中的更多示例
2. 阅读 [API 参考文档](API_REFERENCE.md) 了解详细功能
3. 尝试不同的算法和配置
4. 根据您的具体问题定制优化策略

祝您优化愉快！🚀