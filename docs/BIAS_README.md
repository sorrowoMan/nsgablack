# Bias 模块使用指南

## 概述

Bias 模块是一个可扩展的优化偏向系统，通过**奖函数**和**罚函数**来引导遗传算法的搜索方向。

### 核心思想

- **罚函数（Penalty）**：惩罚不良解，避免往更差的方向优化
- **奖函数（Reward）**：奖励优质解，引导快速收敛到好的方向
- **方向引导**：基于历史信息的智能偏向

### 设计原则

- 奖函数权重（0.01-0.1）远小于罚函数（1.0-10.0）
- 避免过度引导导致早熟收敛
- 配合 VNS 等方法跳出局部最优

## 快速开始

### 1. 基础使用

```python
import numpy as np
from nsgablack.base import BlackBoxProblem
from nsgablack.solver import BlackBoxSolverNSGAII
from nsgablack.bias import create_standard_bias

# 定义问题
class MyProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="MyProblem", dimension=2,
                        bounds={'x0': (-5, 5), 'x1': (-5, 5)})

    def evaluate(self, x):
        return np.sum(x**2)

problem = MyProblem()

# 创建求解器
solver = BlackBoxSolverNSGAII(problem)

# 启用 bias 模块（使用标准配置）
solver.enable_bias = True
solver.bias_module = create_standard_bias(problem,
                                         reward_weight=0.05,
                                         penalty_weight=1.0)

# 运行优化
result = solver.run()
```

### 2. 自定义奖励函数

```python
from nsgablack.bias import BiasModule

# 创建 bias 模块
bias = BiasModule()

# 添加自定义奖励：奖励接近目标点的解
def proximity_reward(x):
    target = np.array([1.0, 1.0])
    distance = np.linalg.norm(x - target)
    return np.exp(-distance)  # 距离越近奖励越大

bias.add_reward(proximity_reward, weight=0.1, name="proximity")

# 应用到求解器
solver.enable_bias = True
solver.bias_module = bias
```

### 3. 约束优化

```python
# 定义带约束的问题
class ConstrainedProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="Constrained", dimension=2,
                        bounds={'x0': (-2, 2), 'x1': (-2, 2)})

    def evaluate(self, x):
        return x[0]**2 + x[1]**2

    def evaluate_constraints(self, x):
        # g(x) <= 0 为可行
        return np.array([1 - x[0] - x[1]])  # x + y >= 1

problem = ConstrainedProblem()

# 使用标准 bias（自动包含约束罚函数）
solver = BlackBoxSolverNSGAII(problem)
solver.enable_bias = True
solver.bias_module = create_standard_bias(problem,
                                         reward_weight=0.05,
                                         penalty_weight=5.0)  # 更高的罚函数权重
```

## 已集成的模块

Bias 模块已集成到以下求解器中：

1. **BlackBoxSolverNSGAII** (`solver.py`) - 主要的 NSGA-II 求解器
2. **SurrogateAssistedNSGAII** (`surrogate.py`) - 代理模型辅助优化
3. **BlackBoxSolverVNS** (`vns.py`) - 变邻域搜索

## 内置奖励函数库

### 1. 接近历史最优解奖励
```python
from nsgablack.bias import proximity_reward

def my_reward(x):
    return proximity_reward(x, best_x, scale=1.0, normalize=True)
```

### 2. 目标改进速度奖励
```python
from nsgablack.bias import improvement_reward

reward = improvement_reward(f_current, f_previous, scale=1.0)
```

### 3. 深度可行性奖励
```python
from nsgablack.bias import feasibility_depth_reward

reward = feasibility_depth_reward(constraint_values, scale=1.0)
```

### 4. 多样性贡献奖励
```python
from nsgablack.bias import diversity_reward

reward = diversity_reward(x, population, scale=1.0, k=5)
```

## 内置罚函数库

### 1. 标准约束罚函数
```python
from nsgablack.bias import constraint_penalty

penalty = constraint_penalty(constraint_values, scale=1.0)
```

### 2. 边界惩罚
```python
from nsgablack.bias import boundary_penalty

penalty = boundary_penalty(x, bounds, scale=1.0)
```

### 3. 停滞惩罚
```python
from nsgablack.bias import stagnation_penalty

penalty = stagnation_penalty(generation, last_improvement_gen, scale=0.01)
```

## 完整示例

查看 `bias_example.py` 获取更多示例：

```bash
python -m nsgablack.bias_example
```

示例包括：
1. 基础使用 - 标准 bias 配置
2. 自定义奖励函数
3. 约束优化
4. 多目标优化
5. VNS + Bias

## 参数调优建议

### 奖励权重
- **保守**：0.01 - 0.03（轻微引导）
- **标准**：0.05 - 0.1（平衡引导）
- **激进**：0.1 - 0.2（强引导，可能早熟）

### 罚函数权重
- **轻度约束**：1.0 - 3.0
- **中度约束**：5.0 - 10.0
- **严格约束**：10.0+

### 使用建议
1. 从标准配置开始（reward=0.05, penalty=1.0）
2. 如果收敛太慢，适当增加奖励权重
3. 如果早熟收敛，减少奖励权重或增加种群多样性
4. 对于约束问题，根据约束严格程度调整罚函数权重

## API 参考

### BiasModule

```python
class BiasModule:
    def add_penalty(self, func: Callable, weight: float = 1.0, name: str = "")
    def add_reward(self, func: Callable, weight: float = 0.05, name: str = "")
    def compute_bias(self, x: np.ndarray, f_original: float,
                    individual_id: Optional[int] = None) -> float
    def update_history(self, x: np.ndarray, f: float)
    def clear()
```

### create_standard_bias

```python
def create_standard_bias(problem,
                        reward_weight: float = 0.05,
                        penalty_weight: float = 1.0) -> BiasModule
```

创建包含以下功能的标准 bias 模块：
- 约束罚函数
- 接近最优解奖励
- 深度可行性奖励

## 注意事项

1. **权重平衡**：奖励权重应远小于罚函数权重
2. **多目标**：对每个目标分别应用 bias
3. **性能影响**：bias 计算会增加少量计算开销
4. **调试**：可通过 `bias_module.history_best_f` 查看历史最优值

## 未来扩展

可以添加更多高级功能：
- 自适应权重调整
- 基于梯度的引导
- 多阶段偏向策略
- 与代理模型的深度集成
