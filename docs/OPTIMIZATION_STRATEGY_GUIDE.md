# nsgablack 优化策略选择指南
## 傻瓜式说明书 - 什么问题用什么方法

> 🎯 **目标**：根据你的具体问题，快速选择最适合的优化策略，无需深入了解算法细节

---

## 📖 快速导航

- [第一步：诊断你的问题](#第一步诊断你的问题)
- [第二步：选择优化策略](#第二步选择优化策略)
- [第三步：配置和运行](#第三步配置和运行)
- [常见场景实战指南](#常见场景实战指南)
- [性能优化技巧](#性能优化技巧)
- [组合策略推荐](#组合策略推荐)

---

## 🩺 第一步：诊断你的问题

### 快速检查清单

请根据你的实际情况勾选：

#### **A. 函数特征**
- [ ] 单次评估时间 > 100ms  → **昂贵函数**
- [ ] 单次评估时间 < 10ms   → **快速函数**
- [ ] 函数结果有随机性      → **随机性问题**
- [ ] 函数有很多局部最优    → **多模态问题**
- [ ] 函数不可导/黑箱       → **黑箱优化**

#### **B. 问题规模**
- [ ] 变量数量 < 10         → **低维问题**
- [ ] 变量数量 10-50       → **中维问题**
- [ ] 变量数量 > 50         → **高维问题**
- [ ] 需要同时优化多个目标   → **多目标问题**
- [ ] 有约束条件            → **约束问题**

#### **C. 计算资源**
- [ ] 可以并行计算          → **可并行化**
- [ ] 内存受限              → **内存敏感**
- [ ] 时间紧迫（<1小时）     → **时间敏感**
- [ ] 有GPU资源            → **GPU可用**

#### **D. 应用场景**
- [ ] 工程仿真（CAE/CFD）   → **工程仿真**
- [ ] 机器学习调参          → **ML调参**
- [ ] 参数设计/优化         → **设计优化**
- [ ] 路径规划/调度         → **规划问题**
- [ ] 金融建模/投资组合     → **金融问题**

---

## 🎯 第二步：选择优化策略

### 策略选择决策树

```
开始
  │
  ├─ 单次评估 > 100ms？
  │   ├─ 是 → 使用【并行评估】
  │   └─ 否 → 继续判断
  │
  ├─ 多目标问题？
  │   ├─ 是 → 【NSGA-II + 并行评估】
  │   └─ 否 → 继续判断
  │
  ├─ 评估非常昂贵（>1s）？
  │   ├─ 是 → 【代理模型 + 并行评估】
  │   └─ 否 → 继续判断
  │
  ├─ 有约束条件？
  │   ├─ 是 → 【偏置引导 + 并行评估】
  │   └─ 否 → 继续判断
  │
  ├─ 结果随机？
  │   ├─ 是 → 【蒙特卡洛 + 并行评估】
  │   └─ 否 → 【基础优化 + 并行评估】
```

### 场景-策略映射表

| 场景类型 | 推荐策略 | 配置建议 | 预期加速 |
|---------|---------|---------|---------|
| **工程仿真优化** | 代理模型 + 并行评估 | surrogate_type='gp', backend='thread' | 5-10x |
| **机器学习调参** | 并行评估 + 偏置引导 | max_workers=4, enable_bias=True | 3-5x |
| **多目标设计** | NSGA-II + 并行评估 | pop_size=100, backend='thread' | 3-4x |
| **约束优化** | 偏置引导 + 并行评估 | penalty_weight=5.0, max_workers=4 | 2-3x |
| **随机优化** | 蒙特卡洛 + 并行评估 | n_scenarios=1000, backend='joblib' | 2-4x |
| **超大规模搜索** | VNS + 并行评估 | max_iterations=200, chunk_size=10 | 3-5x |
| **快速原型** | 基础NSGA-II | pop_size=40, 无并行 | 基准 |

---

## ⚙️ 第三步：配置和运行

### 通用配置模板

#### **模板1：昂贵工程仿真**
```python
from core.solver import BlackBoxSolverNSGAII
from solvers.surrogate import run_surrogate_assisted

# 方法1：NSGA-II + 并行评估
solver = BlackBoxSolverNSGAII(problem)
solver.pop_size = 50
solver.max_generations = 100
solver.enable_parallel(
    backend="thread",
    max_workers=4
)
result = solver.run()

# 方法2：代理模型（超昂贵）
result = run_surrogate_assisted(
    problem,
    surrogate_type='gp',
    real_eval_budget=200,
    initial_samples=30
)
```

#### **模板2：机器学习调参**
```python
from utils.headless import run_headless_single_objective

def model_performance(params):
    # 你的模型训练和评估代码
    train_model(params)
    return validate_model()

result = run_headless_single_objective(
    model_performance,
    bounds=[(0.001, 0.1), (10, 500), (0.1, 0.9)],  # lr, batch_size, dropout
    enable_parallel=True,
    parallel_backend="thread",
    max_workers=4,
    pop_size=60,
    max_generations=80
)
```

#### **模板3：多目标约束优化**
```python
from core.solver import BlackBoxSolverNSGAII
from utils.bias import create_standard_bias

solver = BlackBoxSolverNSGAII(problem)
solver.pop_size = 80
solver.max_generations = 150

# 启用约束处理
solver.enable_bias = True
solver.bias_module = create_standard_bias(
    problem,
    reward_weight=0.02,
    penalty_weight=10.0  # 约束惩罚权重
)

# 启用并行评估
solver.enable_parallel(
    backend="thread",
    max_workers=4
)

result = solver.run()
```

---

## 🎪 常见场景实战指南

### 场景1：CAE/CFD仿真优化
**问题**：结构分析、流体力学等单次仿真需要几秒到几分钟
**策略**：代理模型 + 并行评估

```python
# 步骤1：使用代理模型减少仿真次数
result = run_surrogate_assisted(
    problem,
    surrogate_type='gp',      # 高斯过程适合小样本
    real_eval_budget=100,     # 只运行100次真实仿真
    initial_samples=20        # 初始样本
)

# 步骤2：并行加速真实仿真
solver.enable_parallel(
    backend="process",        # CPU密集型用进程
    max_workers=min(8, os.cpu_count())
)
```

**预期效果**：从1000次仿真减少到100次，速度提升10倍

---

### 场景2：深度学习超参数优化
**问题**：神经网络架构搜索，每次训练需要几分钟
**策略**：并行评估 + 早停 + 偏置引导

```python
def dl_objective(params):
    lr, batch_size, dropout, layers = params

    # 早停策略
    early_stopping = EarlyStopping(patience=10)

    # 训练模型
    model = create_model(layers, dropout)
    history = model.train(
        lr=lr,
        batch_size=int(batch_size),
        epochs=100,
        callbacks=[early_stopping]
    )

    return history['val_loss'][-1]

# 并行调参
result = run_headless_single_objective(
    dl_objective,
    bounds=[(0.0001, 0.01), (16, 256), (0.1, 0.5), (2, 10)],
    enable_parallel=True,
    max_workers=2,  # 考虑GPU内存限制
    pop_size=40,
    max_generations=60
)
```

**预期效果**：2-4倍加速，自动避免过拟合配置

---

### 场景3：机械零件多目标优化
**问题**：同时优化重量、强度、成本，有约束条件
**策略**：NSGA-II + 偏置引导 + 并行评估

```python
class MechanicalPart(BlackBoxProblem):
    def evaluate(self, x):
        weight = calculate_weight(x)
        strength = calculate_strength(x)
        cost = calculate_cost(x)
        return [weight, -strength, cost]  # 最小化重量、成本，最大化强度

    def evaluate_constraints(self, x):
        stress = calculate_stress(x)
        return [stress - max_stress]  # 应力约束

# 配置优化器
solver = BlackBoxSolverNSGAII(problem)
solver.pop_size = 100
solver.max_generations = 200

# 约束处理
solver.enable_bias = True
solver.bias_module = create_standard_bias(
    problem,
    penalty_weight=20.0  # 严格处理约束
)

# 并行评估
solver.enable_parallel(
    backend="thread",
    max_workers=4
)

result = solver.run()

# 分析Pareto前沿
pareto_solutions = result['pareto_solutions']['individuals']
pareto_objectives = result['pareto_solutions']['objectives']
```

**预期效果**：3-4倍加速，获得多样化的设计方案

---

### 场景4：投资组合优化
**问题**：随机收益，需要考虑风险
**策略**：蒙特卡洛 + 并行评估

```python
from solvers.monte_carlo import StochasticProblem, optimize_with_monte_carlo

class PortfolioOptimization(StochasticProblem):
    def evaluate_scenario(self, x, scenario):
        # x: 资产配置比例
        # scenario: 市场场景（收益率等）
        returns = np.dot(x, scenario['returns'])
        risk = np.sqrt(np.dot(x.T, np.dot(scenario['cov_matrix'], x)))

        # 目标：最大化收益，最小化风险
        return -returns + 0.5 * risk  # 负号因为要最小化

    def sample_scenario(self):
        # 生成随机市场场景
        return {
            'returns': np.random.multivariate_normal(mean_returns, cov_matrix),
            'cov_matrix': cov_matrix
        }

result = optimize_with_monte_carlo(
    PortfolioOptimization(),
    n_scenarios=1000,         # 蒙特卡洛场景数
    confidence_level=0.95,    # 置信水平
    enable_parallel=True,     # 启用并行
    max_workers=4
)
```

**预期效果**：2-3倍加速，稳健的投资组合

---

## 🚀 性能优化技巧

### 1. 并行评估优化

```python
# 根据问题类型选择后端
backend = "thread" if problem_type == "io_bound" else "process"

# 动态调整工作进程数
max_workers = min(8, os.cpu_count()) if backend == "process" else 16

# 批次大小优化
chunk_size = max(1, pop_size // (max_workers * 2))

solver.enable_parallel(
    backend=backend,
    max_workers=max_workers,
    chunk_size=chunk_size,
    enable_load_balancing=True
)
```

### 2. 内存优化

```python
# 对于大规模问题，使用生成器
def population_generator(pop_size, dimension, bounds):
    for _ in range(pop_size):
        yield np.random.uniform(bounds[:, 0], bounds[:, 1])

# 定期清理历史数据
if generation % 20 == 0:
    solver.clear_history()
```

### 3. 早停策略

```python
# 基于改进的早停
class EarlyStopMonitor:
    def __init__(self, patience=50, tolerance=1e-6):
        self.patience = patience
        self.tolerance = tolerance
        self.best_value = float('inf')
        self.no_improvement_count = 0

    def should_stop(self, current_value):
        if current_value < self.best_value - self.tolerance:
            self.best_value = current_value
            self.no_improvement_count = 0
            return False
        else:
            self.no_improvement_count += 1
            return self.no_improvement_count >= self.patience

# 使用早停
monitor = EarlyStopMonitor(patience=30)
for generation in range(max_generations):
    result = solver.step()
    if monitor.should_stop(result['best_value']):
        print(f"Early stop at generation {generation}")
        break
```

---

## 🎭 组合策略推荐

### 高级组合方案

#### **方案1：超昂贵仿真**
```
代理模型 → 并行评估 → 偏置引导
预估加速：20-50倍
```

#### **方案2：大规模多目标**
```
降维预处理 → NSGA-II → 并行评估 → VNS精调
预估加速：10-20倍
```

#### **方案3：实时优化**
```
线程并行 → 增量学习 → 偏置引导
预估加速：5-10倍
```

### 组合使用示例

```python
# 超昂贵仿真的完整流程
from utils.manifold_reduction import apply_pca_reduction
from solvers.surrogate import run_surrogate_assisted
from core.solver import BlackBoxSolverNSGAII

# 步骤1：降维（如果高维）
if problem.dimension > 20:
    problem_reduced = apply_pca_reduction(problem, n_components=10)
else:
    problem_reduced = problem

# 步骤2：代理模型初步探索
surrogate_result = run_surrogate_assisted(
    problem_reduced,
    surrogate_type='gp',
    real_eval_budget=50
)

# 步骤3：基于代理结果初始化NSGA-II
solver = BlackBoxSolverNSGAII(problem_reduced)
solver.pop_size = 100
solver.max_generations = 100

# 使用代理结果的Pareto解作为初始种群
solver.initialize_population(surrogate_result['pareto_solutions']['individuals'])

# 步骤4：并行精确优化
solver.enable_parallel(
    backend="process",
    max_workers=8
)

# 步骤5：偏置引导（如果有约束）
if has_constraints:
    from utils.bias import create_standard_bias
    solver.enable_bias = True
    solver.bias_module = create_standard_bias(
        problem_reduced,
        penalty_weight=10.0
    )

# 运行最终优化
result = solver.run()
```

---

## ❓ 常见问题

### Q1: 我应该选择多大的种群大小？
```
变量数 < 10:   pop_size = 50
变量数 10-30:  pop_size = 100
变量数 > 30:   pop_size = 150-200
```

### Q2: 如何判断优化是否收敛？
- 目标值连续50代无改进
- Pareto前沿稳定
- 拥挤度接近理论值

### Q3: 并行评估总是有效吗？
- 种群 < 20: 不建议并行
- 单次评估 < 1ms: 不建议并行
- 内存受限: 减少并行数

### Q4: 什么时候需要代理模型？
- 单次评估 > 1秒
- 总评估预算 < 1000
- 函数平滑且连续

---

## 📚 相关资源

- [API参考文档](API_REFERENCE.md)
- [并行评估详细指南](PARALLEL_EVALUATION_GUIDE.md)
- [偏置模块说明](BIAS_README.md)
- [示例代码集合](../examples/)

---

## 🎯 总结

记住这个黄金法则：

> **简单问题用简单方法，复杂问题用组合策略，昂贵问题必须并行！**

如果你还是不确定，选择：
```python
# 不会错的默认配置
solver.enable_parallel(backend="thread", max_workers=4)
solver.pop_size = 80
solver.max_generations = 100
```

这个配置对90%的问题都有效！

---

*💡 提示：保存这个指南，遇到问题时随时查阅！*