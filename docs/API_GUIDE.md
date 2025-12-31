# nsgablack 快速API指南

<div align="center">

**5分钟上手 - 从入门到精通**

</div>

---

## 目录

- [快速开始](#快速开始)
- [核心API](#核心api)
- [偏置系统API](#偏置系统api)
- [多智能体API](#多智能体api)
- [高级功能API](#高级功能api)
- [常见用法](#常见用法)

---

## 快速开始

### 最简示例（3行代码）

```python
from nsgablack.core import ZDT1BlackBox, BlackBoxSolverNSGAII

problem = ZDT1BlackBox(dimension=10)
result = BlackBoxSolverNSGAII(problem).run()
```

### 标准示例

```python
from nsgablack.core import ZDT1BlackBox, BlackBoxSolverNSGAII

# 1. 创建问题
problem = ZDT1BlackBox(dimension=10)

# 2. 创建求解器
solver = BlackBoxSolverNSGAII(problem)
solver.pop_size = 100
solver.max_generations = 200

# 3. 运行优化
result = solver.run()

# 4. 获取结果
pareto_solutions = result['pareto_solutions']
pareto_objectives = result['pareto_objectives']
```

---

## 核心API

### 1. 问题定义 API

#### BlackBoxProblem（基类）

```python
from nsgablack.core.base import BlackBoxProblem

class MyProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(
            name="MyProblem",
            dimension=2,
            bounds={
                'x1': [0, 10],
                'x2': [0, 10]
            }
        )

    def evaluate(self, x):
        """评估目标函数"""
        f1 = x[0]**2 + x[1]**2
        f2 = (x[0] - 5)**2 + (x[1] - 5)**2
        return [f1, f2]

    def evaluate_constraints(self, x):
        """评估约束（可选）"""
        c1 = max(0, x[0] + x[1] - 10)
        c2 = max(0, x[0] - 8)
        return [c1, c2]

# 使用
problem = MyProblem()
```

#### 标准测试问题

```python
from nsgablack.core.problems import (
    ZDT1BlackBox,    # ZDT1问题
    ZDT2BlackBox,    # ZDT2问题
    ZDT3BlackBox,    # ZDT3问题
    DTLZ1BlackBox,   # DTLZ1问题
    DTLZ2BlackBox    # DTLZ2问题
)

# 使用
problem = ZDT1BlackBox(dimension=30)
```

### 2. 求解器 API

#### BlackBoxSolverNSGAII（核心求解器）

```python
from nsgablack.core.solver import BlackBoxSolverNSGAII

solver = BlackBoxSolverNSGAII(problem)

# 基础参数
solver.pop_size = 100              # 种群大小
solver.max_generations = 200       # 最大迭代次数
solver.crossover_prob = 0.9        # 交叉概率
solver.mutation_prob = 0.1         # 变异概率
solver.distribution_index = 20     # 分布指数

# 高级参数
solver.enable_elite = True         # 启用精英保留
solver.enable_bias = False         # 启用偏置系统
solver.enable_convergence_detection = True  # 启用收敛检测

# 运行
result = solver.run()
```

#### 返回结果格式

```python
result = {
    'pareto_solutions': array([[...], [...], ...]),  # Pareto解集
    'pareto_objectives': array([[...], [...], ...]), # Pareto目标值
    'pareto_constraints': array([[...], [...], ...]),# 约束违背度
    'generations': 150,                              # 实际迭代次数
    'evaluations': 15000,                            # 评估次数
    'elapsed_time': 12.5,                            # 耗时（秒）
    'converged': True,                               # 是否收敛
    'history': {...}                                 # 历史记录
}
```

### 3. 求解器选择

```python
from nsgablack.solvers import (
    BlackBoxSolverNSGAII,        # NSGA-II
    BlackBoxSolverMOEAD,         # MOEA/D
    BayesianOptimizer,           # 贝叶斯优化
    HybridBayesianOptimizer,     # 混合贝叶斯优化
    VariableNeighborhoodSearch,  # 变邻域搜索
    MonteCarloOptimizer          # 蒙特卡洛优化
)

# NSGA-II（推荐）
solver = BlackBoxSolverNSGAII(problem)

# MOEA/D（基于分解）
solver = BlackBoxSolverMOEAD(problem)

# 贝叶斯优化（昂贵评估）
solver = BayesianOptimizer(problem)

# 混合优化
solver = HybridBayesianOptimizer(problem)
```

---

## 偏置系统API

### 1. 基础偏置使用

```python
from nsgablack.bias.bias_v2 import UniversalBiasManager
from nsgablack.bias.bias_library_algorithmic import DiversityBias
from nsgablack.bias.bias_library_domain import ConstraintBias

# 创建偏置管理器
bias_manager = UniversalBiasManager()

# 添加算法偏置
bias_manager.algorithmic_manager.add_bias(
    DiversityBias(weight=0.15)
)

# 添加领域偏置
bias_manager.domain_manager.add_bias(
    ConstraintBias(weight=0.5)
)

# 应用到求解器
solver.bias_manager = bias_manager
solver.enable_bias = True
```

### 2. 预置偏置类型

#### 算法偏置

```python
from nsgablack.bias.bias_library_algorithmic import (
    DiversityBias,           # 多样性偏置
    ConvergenceBias,         # 收敛偏置
    ExplorationBias,         # 探索偏置
    SimulatedAnnealingBias   # 模拟退火偏置
)

# 多样性偏置 - 保持种群多样性
diversity_bias = DiversityBias(weight=0.2)

# 收敛偏置 - 加速向Pareto前沿收敛
convergence_bias = ConvergenceBias(weight=0.1)

# 探索偏置 - 增强全局搜索
exploration_bias = ExplorationBias(weight=0.15)

# 模拟退火偏置 - 注入SA思想
sa_bias = SimulatedAnnealingBias(
    initial_weight=0.2,
    initial_temperature=100.0,
    cooling_rate=0.995
)
```

#### 领域偏置

```python
from nsgablack.bias.bias_library_domain import (
    ConstraintBias,          # 约束偏置
    PreferenceBias,          # 偏好偏置
    RuleBasedBias,           # 规则偏置
    FeasibilityBias          # 可行性偏置
)

# 约束偏置 - 处理约束条件
constraint_bias = ConstraintBias(weight=0.5)
constraint_bias.add_hard_constraint(lambda x: max(0, x[0] + x[1] - 1))

# 偏好偏置 - 引入决策者偏好
preference_bias = PreferenceBias(
    preferred_objectives=[0],  # 优先优化第一个目标
    weight=0.3
)

# 规则偏置 - 基于领域规则
rule_bias = RuleBasedBias(weight=0.4)
rule_bias.add_rule(lambda x: "apply_penalty" if x[0] > 5 else "ok")
```

### 3. 自适应偏置

```python
from nsgablack.bias.adaptive_algorithmic_bias import AdaptiveAlgorithmicManager

# 创建自适应管理器
adaptive_manager = AdaptiveAlgorithmicManager()

# 添加偏置
adaptive_manager.add_bias(DiversityBias(weight=0.15))
adaptive_manager.add_bias(SimulatedAnnealingBias(weight=0.2))

# 基于优化状态自动调整
solver.adaptive_bias_manager = adaptive_manager
```

### 4. 元学习偏置选择

```python
from nsgablack.bias.meta_learning_bias_selector import MetaLearningBiasSelector

# AI分析问题特征
selector = MetaLearningBiasSelector()
problem_features = selector.analyze_problem(problem)

# 获取智能推荐
recommendations = selector.recommend_biases(problem_features)

# 一键应用
bias_manager = selector.create_optimal_bias_manager(problem)
solver.bias_manager = bias_manager
```

---

## 多智能体API

### 1. 基础使用

```python
from nsgablack.solvers.multi_agent import MultiAgentBlackBoxSolver

# 创建多智能体求解器
solver = MultiAgentBlackBoxSolver(problem)

# 运行优化
result = solver.run()
```

### 2. 配置智能体比例

```python
from nsgablack.solvers.multi_agent import MultiAgentBlackBoxSolver, AgentRole

# 自定义配置
config = {
    'total_population': 200,
    'agent_ratios': {
        AgentRole.EXPLORER: 0.3,     # 探索者
        AgentRole.EXPLOITER: 0.4,    # 开发者
        AgentRole.WAITER: 0.2,       # 等待者
        AgentRole.COORDINATOR: 0.1   # 协调者
    },
    'max_generations': 200,
    'communication_interval': 5,    # 信息交流间隔
    'adaptation_interval': 20,      # 策略调整间隔
    'dynamic_ratios': True          # 动态调整
}

solver = MultiAgentBlackBoxSolver(problem, config=config)
```

### 3. 智能体角色说明

```python
class AgentRole(Enum):
    EXPLORER = "explorer"      # 探索者：广泛搜索
    EXPLOITER = "exploiter"    # 开发者：深入优化
    WAITER = "waiter"          # 等待者：学习模式
    COORDINATOR = "coordinator" # 协调者：动态调整
```

---

## 高级功能API

### 1. 并行计算

```python
from nsgablack.utils.parallel_evaluator import ParallelEvaluator

# 创建并行评估器
evaluator = ParallelEvaluator(
    backend='auto',        # 自动选择后端
    max_workers='auto',    # 自动确定工作进程数
    memory_limit='8GB'     # 内存限制
)

# 应用到求解器
solver.parallel_evaluator = evaluator
solver.batch_size = 50
```

### 2. 代理模型

```python
from nsgablack.solvers.surrogate import EnsembleSurrogate
from nsgablack.utils.surrogate_model import SurrogateModel

# 创建集成代理模型
surrogate = EnsembleSurrogate([
    SurrogateModel('gaussian_process'),  # 高斯过程
    SurrogateModel('random_forest'),     # 随机森林
    SurrogateModel('rbf_network')        # RBF网络
])

# 应用到求解器
solver.surrogate_model = surrogate
solver.evaluation_budget = 1000  # 限制真实评估次数
```

### 3. 可视化

```python
from nsgablack.utils.visualization import SolverVisualizationMixin

class VisualSolver(SolverVisualizationMixin, BlackBoxSolverNSGAII):
    def __init__(self, problem):
        super().__init__(problem)
        self.enable_visualization = True
        self.plot_interval = 10  # 每10代更新

# 运行（弹出可视化窗口）
solver = VisualSolver(problem)
solver.run()
```

### 4. 实验跟踪

```python
from nsgablack.utils.experiment import ExperimentResult

# 创建实验记录
experiment = ExperimentResult(
    problem_name="MyProblem",
    algorithm="NSGA-II",
    config={'pop_size': 100, 'generations': 200}
)

# 设置结果
experiment.set_results(
    pareto_solutions=result['pareto_solutions'],
    pareto_objectives=result['pareto_objectives'],
    generations=result['generations'],
    evaluations=result['evaluations'],
    elapsed_time=result['elapsed_time'],
    history=result['history']
)

# 保存到文件
experiment.save_to_csv('results.csv')
experiment.save_to_json('metadata.json')
```

### 5. 流形降维

```python
from nsgablack.utils.manifold_reduction import ManifoldReducer

# 创建降维器
reducer = ManifoldReducer(method='pca')
reducer.n_components = 5

# 准备降维问题
reduced_problem = reducer.prepare_reduced_problem(
    original_problem, n_components=5
)

# 在降维空间优化
solver = BlackBoxSolverNSGAII(reduced_problem)
result_reduced = solver.run()

# 解码回原始空间
final_solution = reducer.decode_solution(result_reduced['pareto_solutions'][0])
```

### 6. 特征选择

```python
from nsgablack.utils.feature_selection import UniversalFeatureSelector

# 创建特征选择器
selector = UniversalFeatureSelector()
selector.methods = ['mutual_info', 'random_forest']
selector.strategy = 'cumulative_threshold'
selector.threshold = 0.95

# 选择特征
selected_features, reduced_problem = selector.select_features(
    original_problem, X_sample, y_sample
)
```

---

## 常见用法

### 用法1：带约束的优化

```python
from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.solver import BlackBoxSolverNSGAII
from nsgablack.bias.bias_v2 import UniversalBiasManager
from nsgablack.bias.bias_library_domain import ConstraintBias

# 定义约束问题
class ConstrainedProblem(BlackBoxProblem):
    def evaluate(self, x):
        return [x[0]**2, (x[0]-2)**2]

    def evaluate_constraints(self, x):
        return [max(0, x[0] + x[1] - 1)]

# 创建约束偏置
bias_manager = UniversalBiasManager()
constraint_bias = ConstraintBias(weight=5.0)
constraint_bias.add_hard_constraint(lambda x: max(0, x[0] + x[1] - 1))
bias_manager.domain_manager.add_bias(constraint_bias)

# 求解
problem = ConstrainedProblem()
solver = BlackBoxSolverNSGAII(problem)
solver.bias_manager = bias_manager
solver.enable_bias = True
result = solver.run()
```

### 用法2：TSP问题

```python
from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.solver import BlackBoxSolverNSGAII
import numpy as np

class TSPProblem(BlackBoxProblem):
    def __init__(self, cities):
        super().__init__("TSP", dimension=len(cities), bounds={
            f'x{i}': [0, 1] for i in range(len(cities))
        })
        self.cities = np.array(cities)

    def evaluate(self, x):
        # 连续编码通过排序得到路径
        tour_order = np.argsort(x)
        tour = self.cities[tour_order]

        # 计算总距离
        distances = np.sqrt(np.sum(np.diff(tour, axis=0)**2, axis=1))
        total_distance = np.sum(distances) + np.sqrt(np.sum((tour[-1] - tour[0])**2))

        return [total_distance]

# 求解
cities = np.random.rand(20, 2)  # 20个城市
problem = TSPProblem(cities)
solver = BlackBoxSolverNSGAII(problem)
solver.pop_size = 100
solver.max_generations = 500
result = solver.run()
```

### 用法3：机器学习超参数优化

```python
from nsgablack.core.base import BlackBoxProblem
from sklearn.model_selection import cross_val_score
from sklearn.ensemble import RandomForestClassifier

class HyperparameterOptimization(BlackBoxProblem):
    def __init__(self, X, y):
        super().__init__(
            "HyperparameterOpt",
            dimension=3,
            bounds={
                'n_estimators': [10, 200],
                'max_depth': [3, 20],
                'min_samples_split': [2, 10]
            }
        )
        self.X = X
        self.y = y

    def evaluate(self, x):
        # 解码参数
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

        # 返回目标：错误率和模型复杂度
        error_rate = 1 - scores.mean()
        complexity = n_estimators * max_depth / 1000

        return [error_rate, complexity]

# 求解
from sklearn.datasets import load_iris
X, y = load_iris(return_X_y=True)

problem = HyperparameterOptimization(X, y)
solver = BlackBoxSolverNSGAII(problem)
solver.pop_size = 50
solver.max_generations = 100
result = solver.run()
```

### 用法4：多目标工程设计

```python
from nsgablack.core.base import BlackBoxProblem
from nsgablack.bias.bias_v2 import UniversalBiasManager
from nsgablack.bias.bias_library_domain import PreferenceBias

class EngineeringDesign(BlackBoxProblem):
    def evaluate(self, x):
        # x: [长度, 截面积, 材料密度]
        length, area, density = x

        # 目标1：重量最小
        weight = length * area * density

        # 目标2：成本最小
        cost = length * area * 100 + density * 50

        # 目标3：强度最大（转换为最小化）
        strength = -(area * 1000 / length)

        return [weight, cost, strength]

    def evaluate_constraints(self, x):
        length, area, density = x
        c1 = max(0, 10 - length)      # 长度 >= 10
        c2 = max(0, area - 5)         # 截面积 <= 5
        c3 = max(0, 2 - density)      # 密度 >= 2
        return [c1, c2, c3]

# 使用偏好偏置
bias_manager = UniversalBiasManager()
preference_bias = PreferenceBias(
    preferred_objectives=[0, 1],  # 优先考虑重量和成本
    weights=[0.5, 0.3, 0.2]
)
bias_manager.domain_manager.add_bias(preference_bias)

# 求解
problem = EngineeringDesign()
solver = BlackBoxSolverNSGAII(problem)
solver.bias_manager = bias_manager
solver.enable_bias = True
result = solver.run()
```

### 用法5：并行加速

```python
from nsgablack.utils.parallel_evaluator import ParallelEvaluator

# 昂贵评估问题
class ExpensiveProblem(BlackBoxProblem):
    def evaluate(self, x):
        import time
        time.sleep(0.1)  # 模拟昂贵计算
        return [x[0]**2, x[1]**2]

# 并行加速
problem = ExpensiveProblem()
solver = BlackBoxSolverNSGAII(problem)

# 配置并行
evaluator = ParallelEvaluator(
    backend='multiprocessing',
    max_workers=8
)
solver.parallel_evaluator = evaluator

# 运行（8倍加速）
result = solver.run()
```

---

## API速查表

### 问题定义

| 类/方法 | 说明 |
|--------|------|
| `BlackBoxProblem` | 问题基类 |
| `evaluate(x)` | 评估目标函数 |
| `evaluate_constraints(x)` | 评估约束（可选） |
| `ZDT1BlackBox` | ZDT1测试问题 |
| `DTLZ2BlackBox` | DTLZ2测试问题 |

### 求解器

| 类/方法 | 说明 |
|--------|------|
| `BlackBoxSolverNSGAII` | NSGA-II求解器 |
| `BlackBoxSolverMOEAD` | MOEA/D求解器 |
| `BayesianOptimizer` | 贝叶斯优化器 |
| `MultiAgentBlackBoxSolver` | 多智能体求解器 |
| `solver.run()` | 运行优化 |
| `result['pareto_solutions']` | 获取Pareto解 |
| `result['pareto_objectives']` | 获取目标值 |

### 偏置系统

| 类/方法 | 说明 |
|--------|------|
| `UniversalBiasManager` | 统一偏置管理器 |
| `DiversityBias` | 多样性偏置 |
| `ConstraintBias` | 约束偏置 |
| `SimulatedAnnealingBias` | 模拟退火偏置 |
| `MetaLearningBiasSelector` | 元学习选择器 |

### 高级功能

| 类/方法 | 说明 |
|--------|------|
| `ParallelEvaluator` | 并行评估器 |
| `EnsembleSurrogate` | 集成代理模型 |
| `ManifoldReducer` | 流形降维 |
| `ExperimentResult` | 实验跟踪 |
| `SolverVisualizationMixin` | 可视化混入 |

---

**更多示例请查看 `examples/` 目录**
