# 局部优化技术分析与建议

## 现状分析

### 已有的局部优化能力

1. **VNS (变邻域搜索)**
   - 位置：`solvers/vns.py`
   - 特点：系统性地探索不同邻域
   - 局限：实现较为简单，缺乏高级策略

2. **GradientApproximationBias**
   - 位置：`bias/bias_library_algorithmic.py`
   - 特点：数值梯度近似
   - 局限：仅提供梯度信息，不实现完整优化

### 缺失的局部优化技术

1. **基于梯度的方法**
   - 梯度下降法 (GD)
   - 共轭梯度法 (CG)
   - BFGS/L-BFGS (拟牛顿法)
   - 牛顿法

2. **无梯度方法**
   - Nelder-Mead 单纯形法
   - Powell 方法
   - COBYLA (约束优化)
   - SLSQP (序列二次规划)

3. **混合优化策略**
   - Memetic Algorithm (文化基因算法)
   - Hybrid GA-LS (遗传算法+局部搜索)
   - Multi-start 局部优化

## 技术方案建议

### 方案一：扩展偏置系统 (推荐) ⭐

**优势：**
- 保持架构统一性
- 可以灵活组合多种局部优化策略
- 与现有系统无缝集成

**实现思路：**
1. 创建新的局部优化偏置类
2. 每个偏置实现一种局部优化策略
3. 可以组合使用多个局部偏置

```python
# 新增局部优化偏置
class GradientDescentBias(AlgorithmicBias)
class NewtonMethodBias(AlgorithmicBias)
class NelderMeadBias(AlgorithmicBias)
class LineSearchBias(AlgorithmicBias)
class TrustRegionBias(AlgorithmicBias)

# 组合使用
bias_manager.add_bias(GradientDescentBias(weight=0.3, learning_rate=0.01))
bias_manager.add_bias(LineSearchBias(weight=0.2, method='backtracking'))
```

### 方案二：独立局部优化模块

**结构：**
```
solvers/
├── local/
│   ├── gradient_based.py    # 基于梯度的方法
│   ├── gradient_free.py     # 无梯度方法
│   ├── hybrid.py           # 混合策略
│   └── utils.py            # 辅助函数
```

**优势：**
- 模块职责清晰
- 可以独立发展
- 便于实现复杂的局部优化算法

### 方案三：混合方案 (最佳)

结合偏置系统和独立模块：

1. **简单局部优化** → 偏置系统
2. **复杂局部优化** → 独立模块
3. **混合策略** → 两者结合

## 具体实现建议

### 1. 扩展偏置库 - 局部优化偏置

```python
# 在 bias/library_algorithmic.py 中添加

class GradientDescentBias(AlgorithmicBias):
    """梯度下降偏置"""

    def __init__(self, weight=0.1, learning_rate=0.01, momentum=0.9):
        super().__init__("gradient_descent", weight)
        self.learning_rate = learning_rate
        self.momentum = momentum
        self.velocity = None

    def apply(self, x, eval_func, context):
        if not context.best_solution:
            return 0

        # 计算梯度
        gradient = self._compute_gradient(x, eval_func)

        # 更新速度（带惯性）
        if self.velocity is None:
            self.velocity = -gradient
        else:
            self.velocity = self.momentum * self.velocity - (1-self.momentum) * gradient

        # 计算改进方向
        improvement = np.dot(self.velocity, context.best_solution - x)
        return self.weight * improvement

class NewtonMethodBias(AlgorithmicBias):
    """牛顿法偏置"""

    def __init__(self, weight=0.2, regularization=1e-6):
        super().__init__("newton_method", weight)
        self.regularization = regularization

    def apply(self, x, eval_func, context):
        # 计算梯度和Hessian矩阵
        gradient = self._compute_gradient(x, eval_func)
        hessian = self._compute_hessian(x, eval_func)

        # 正则化避免奇异性
        hessian += self.regularization * np.eye(len(x))

        # 牛顿步
        newton_step = np.linalg.solve(hessian, gradient)

        # 评估改进潜力
        expected_improvement = -0.5 * np.dot(gradient, newton_step)
        return self.weight * expected_improvement

class LineSearchBias(AlgorithmicBias):
    """线搜索偏置"""

    def __init__(self, weight=0.15, method='armijo', alpha=0.5, beta=0.8):
        super().__init__("line_search", weight)
        self.method = method
        self.alpha = alpha  # Armijo条件参数
        self.beta = beta    # 回缩因子

    def apply(self, x, eval_func, context):
        if not context.search_direction:
            return 0

        # 执行线搜索找到合适步长
        step_size = self._line_search(x, context.search_direction, eval_func)

        # 返回步长作为偏置
        return self.weight * step_size
```

### 2. 新增混合优化求解器

```python
# solvers/hybrid.py
class HybridNSGALocal(BlackBoxSolverNSGAII):
    """混合NSGA-II与局部优化的求解器"""

    def __init__(self, problem):
        super().__init__(problem)
        self.local_optimizer = None
        self.local_frequency = 10  # 每10代进行一次局部优化
        self.local_fraction = 0.1  # 10%的个体进行局部优化

    def _apply_local_search(self, population):
        """对部分个体应用局部搜索"""
        n_local = int(len(population) * self.local_fraction)
        selected = np.random.choice(len(population), n_local, replace=False)

        for idx in selected:
            individual = population[idx]
            improved = self.local_optimizer.optimize(individual)
            population[idx] = improved

    def run(self):
        # 主NSGA-II循环
        for gen in range(self.max_generations):
            # 标准NSGA-II操作
            self._evolution_step()

            # 定期局部优化
            if gen % self.local_frequency == 0:
                self._apply_local_search(self.population)

        return self._get_results()
```

### 3. 局部优化实用偏置

```python
class AdaptiveLocalBias(AlgorithmicBias):
    """自适应局部优化偏置"""

    def __init__(self, weight=0.2):
        super().__init__("adaptive_local", weight)
        self.success_history = []
        self.current_method = "gradient_descent"

    def apply(self, x, eval_func, context):
        # 根据成功率选择方法
        if self._should_switch_method():
            self._select_best_method()

        # 应用当前选择的局部优化方法
        if self.current_method == "gradient_descent":
            return self._gradient_descent_step(x, eval_func)
        elif self.current_method == "newton":
            return self._newton_step(x, eval_func)
        else:
            return self._nelder_mead_step(x, eval_func)

class MultiStartLocalBias(AlgorithmicBias):
    """多起点局部优化偏置"""

    def __init__(self, weight=0.3, n_starts=5):
        super().__init__("multi_start_local", weight)
        self.n_starts = n_starts
        self.local_optima = []

    def apply(self, x, eval_func, context):
        # 从多个起点进行局部优化
        best_value = float('inf')

        for _ in range(self.n_starts):
            # 生成随机起点
            start_point = self._generate_start_point(x)

            # 局部优化
            local_optimum = self._local_optimize(start_point, eval_func)
            self.local_optima.append(local_optimum)

            # 更新最优解
            if local_optimum['value'] < best_value:
                best_value = local_optimum['value']

        # 返回改进潜力
        current_value = eval_func(x)
        improvement = current_value - best_value
        return self.weight * max(0, improvement)
```

## 使用建议

### 1. 简单场景
```python
# 直接使用偏置
from bias import AlgorithmicBiasManager
from bias.bias_library_algorithmic import GradientDescentBias

bias_manager = AlgorithmicBiasManager()
bias_manager.add_bias(GradientDescentBias(weight=0.2, learning_rate=0.01))
```

### 2. 复杂场景
```python
# 使用混合求解器
from solvers.hybrid import HybridNSGALocal
from bias import UniversalBiasManager

# 配置局部优化器
solver = HybridNSGALocal(problem)
solver.local_optimizer = GradientBasedOptimizer(method='L-BFGS-B')
solver.local_frequency = 5

# 添加偏置引导
solver.bias_manager = bias_manager
```

### 3. 自适应场景
```python
# 自适应选择局部优化方法
bias_manager.add_bias(AdaptiveLocalBias(weight=0.25))
bias_manager.add_bias(MultiStartLocalBias(weight=0.15))
```

## 总结

建议采用**偏置系统扩展**的方案，因为：

1. **架构一致**：与现有设计保持统一
2. **灵活性高**：可以组合多种策略
3. **易于实现**：复用现有基础设施
4. **扩展性好**：便于添加新的局部优化方法

对于特别复杂的局部优化需求，可以考虑添加独立的局部优化模块作为补充。