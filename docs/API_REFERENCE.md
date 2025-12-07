# API 参考文档

## 核心 API

### BlackBoxProblem

黑箱优化问题的基类。

```python
class BlackBoxProblem:
    def __init__(self, name: str, dimension: int, bounds: Dict[str, Tuple[float, float]])

    def evaluate(self, x: np.ndarray) -> Union[float, np.ndarray]
    def evaluate_constraints(self, x: np.ndarray) -> np.ndarray  # 可选
    def get_num_objectives(self) -> int  # 可选，默认为1
```

**参数：**
- `name`: 问题描述名称
- `dimension`: 决策变量维度
- `bounds`: 变量边界，格式为 `{'x0': (min, max), 'x1': (min, max), ...}`

**示例：**
```python
class MyProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(
            name="MyProblem",
            dimension=3,
            bounds={'x0': (0, 1), 'x1': (-1, 1), 'x2': (0, 10)}
        )

    def evaluate(self, x):
        return x[0]**2 + x[1]**2 + x[2]**2

    def evaluate_constraints(self, x):
        return np.array([x[0] + x[1] - 1,  # g1(x) <= 0
                        0.5 - x[2]])       # g2(x) <= 0
```

### BlackBoxSolverNSGAII

NSGA-II 多目标优化求解器，支持并行评估。

```python
class BlackBoxSolverNSGAII:
    def __init__(self, problem: BlackBoxProblem)
    def run(self, return_experiment: bool = False) -> Dict
    def initialize_population(self) -> None
    def animate(self, frame: Optional[int] = None) -> None

    # 并行评估支持
    def enable_parallel(self, backend: str = "thread", max_workers: int = None,
                       auto_configure: bool = True, **kwargs) -> None
    def disable_parallel(self) -> None
    def get_parallel_stats(self) -> Dict
```

**配置参数：**
- `pop_size`: 种群大小 (默认: 40)
- `max_generations`: 最大代数 (默认: 100)
- `mutation_rate`: 变异率 (默认: 0.1)
- `crossover_rate`: 交叉率 (默认: 0.9)
- `enable_bias`: 启用偏置模块 (默认: False)
- `enable_diversity_init`: 启用多样性初始化 (默认: False)
- `enable_progress_log`: 启用进度日志 (默认: True)
- `report_interval`: 日志报告间隔 (默认: 10)

#### 并行评估配置

**启用并行评估：**
```python
# 方法1：直接启用
solver.enable_parallel(
    backend="thread",      # 后端类型
    max_workers=4,        # 工作线程/进程数
    auto_configure=True   # 自动优化配置
)

# 方法2：使用求解器扩展
from utils.solver_extensions import create_parallel_solver

solver = create_parallel_solver(
    BlackBoxSolverNSGAII,
    problem=problem,
    parallel_backend="thread",
    max_workers=4,
    pop_size=50,
    max_generations=100
)
```

**并行后端选择：**
- `thread`: 线程池（推荐Windows使用）
  - 优点：低内存开销，启动快
  - 适用：I/O密集型、混合型任务
  - 限制：Python GIL限制CPU并行

- `process`: 进程池（推荐Linux/macOS使用）
  - 优点：真正的CPU并行，绕过GIL
  - 适用：CPU密集型任务
  - 限制：高内存开销，启动慢

- `joblib`: Joblib后端
  - 优点：灵活的负载均衡，内存优化
  - 适用：大规模评估，长时间运行
  - 要求：需安装joblib包

**高级配置：**
```python
solver.enable_parallel(
    backend="thread",
    max_workers=4,
    chunk_size=10,             # 批次大小
    enable_load_balancing=True,    # 负载均衡
    timeout=30.0,              # 单个任务超时
    retry_count=3              # 失败重试次数
)
```

**返回值：**
```python
{
    'pareto_solutions': {
        'individuals': np.ndarray,  # Pareto 解
        'objectives': np.ndarray,   # 对应的目标值
        'constraint_violations': np.ndarray  # 约束违反度
    },
    'convergence_metrics': List[Dict],  # 收敛指标历史
    'evaluations': int,                 # 总评估次数
    'experiment': ExperimentResult      # 实验结果 (如果 return_experiment=True)
}
```

## 偏置模块

### BiasModule

可扩展的优化偏向模块，用于引导搜索方向。

```python
class BiasModule:
    def __init__(self)
    def add_reward(self, func: Callable, weight: float = 0.05, name: str = "")
    def add_penalty(self, func: Callable, weight: float = 1.0, name: str = "")
    def compute_bias(self, x: np.ndarray, f_original: float, individual_id: Optional[int] = None) -> float
    def update_history(self, x: np.ndarray, f: float)
    def clear(self)
```

### 便捷函数

```python
def create_standard_bias(problem: BlackBoxProblem, reward_weight: float = 0.05,
                        penalty_weight: float = 1.0) -> BiasModule
```

创建包含约束罚函数和接近最优解奖励的标准偏置模块。

**内置奖励函数：**
- `proximity_reward(x, best_x, scale=1.0)`: 接近历史最优解的奖励
- `improvement_reward(f_current, f_previous, scale=1.0)`: 目标改进速度奖励
- `feasibility_depth_reward(constraint_values, scale=1.0)`: 深度可行性奖励
- `diversity_reward(x, population, scale=1.0, k=5)`: 多样性贡献奖励

**内置罚函数：**
- `constraint_penalty(constraint_values, scale=1.0)`: 标准约束罚函数
- `boundary_penalty(x, bounds, scale=1.0)`: 边界惩罚
- `stagnation_penalty(generation, last_improvement_gen, scale=0.01)`: 停滞惩罚

## 求解器

### 单目标优化 (run_headless_single_objective)

适用于任意单目标函数的快速优化，支持并行评估。

```python
def run_headless_single_objective(objective: Callable,
                                 bounds: List[Tuple[float, float]],
                                 *,
                                 pop_size: int = 80,
                                 max_generations: int = 150,
                                 parallel_backend: str = "thread",
                                 max_workers: int = None,
                                 enable_parallel: bool = False,
                                 **kwargs) -> Dict
```

**并行评估配置：**
```python
# 启用并行评估
result = run_headless_single_objective(
    objective=my_expensive_function,
    bounds=[(0, 10), (-5, 5)],
    enable_parallel=True,        # 启用并行
    parallel_backend="thread",   # 后端类型
    max_workers=4,              # 工作线程数
    pop_size=100,
    max_generations=200
)

# 获取性能统计
print(f"总评估时间: {result['total_time']:.2f}s")
print(f"平均评估时间: {result.get('avg_eval_time', 0)*1000:.2f}ms")
```

**参数说明：**
- `parallel_backend`: 并行后端 ('thread', 'process', 'joblib')
- `max_workers`: 工作线程/进程数（默认：CPU核心数）
- `enable_parallel`: 是否启用并行评估

### 代理模型辅助优化

```python
def run_surrogate_assisted(problem: BlackBoxProblem,
                          surrogate_type: str = 'gp',
                          real_eval_budget: int = 200,
                          initial_samples: int = 30,
                          acquisition: str = 'ei') -> Dict
```

**参数：**
- `surrogate_type`: 代理模型类型 ('gp', 'rbf', 'rf', 'ensemble')
- `real_eval_budget`: 真实函数评估预算
- `initial_samples`: 初始采样数量
- `acquisition`: 采集函数 ('ei', 'poi', 'ucb')

### 蒙特卡洛优化

```python
class StochasticProblem(BlackBoxProblem):
    def evaluate_scenario(self, x: np.ndarray, scenario: Dict) -> float
    def sample_scenario(self) -> Dict

def optimize_with_monte_carlo(problem: StochasticProblem,
                             n_scenarios: int = 1000,
                             confidence_level: float = 0.95,
                             risk_preference: str = 'risk-neutral') -> Dict
```

### 变邻域搜索

```python
class BlackBoxSolverVNS:
    def __init__(self, problem: BlackBoxProblem)
    def run(self) -> Dict
```

**配置参数：**
- `max_iterations`: 最大迭代次数
- `neighborhood_sizes`: 邻域大小列表
- `enable_bias`: 启用偏置模块

## 机器学习模块

### ModelManager

机器学习模型管理器。

```python
class ModelManager:
    def __init__(self)
    def train_classifier(self, X: np.ndarray, y: np.ndarray, model_type: str = 'rf')
    def train_regressor(self, X: np.ndarray, y: np.ndarray, model_type: str = 'rf')
    def predict(self, X: np.ndarray) -> np.ndarray
    def save_model(self, filepath: str)
    def load_model(self, filepath: str)
```

## 工具模块

### 可视化

```python
class SolverVisualizationMixin:
    def plot_pareto_front(self, save_path: Optional[str] = None)
    def plot_convergence(self, save_path: Optional[str] = None)
    def animate_convergence(self, save_path: Optional[str] = None)
```

### 并行运行

```python
def run_parallel_optimization(problem: BlackBoxProblem,
                             n_runs: int = 10,
                             n_processes: Optional[int] = None) -> List[Dict]
```

### 实验跟踪

```python
class ExperimentTracker:
    def __init__(self, base_dir: str = "./experiments")
    def log_run(self, result: Dict, problem: BlackBoxProblem,
                solver_config: Dict) -> str
    def load_experiment(self, exp_dir: str) -> Dict
    def compare_experiments(self, exp_dirs: List[str]) -> Dict
```

## 内置问题

### 单目标问题
- `SphereBlackBox`: 球函数
- `RastriginBlackBox`: Rastrigin 函数

### 多目标问题
- `ZDT1BlackBox`: ZDT1 问题
- `ZDT2BlackBox`: ZDT2 问题

### 工程问题
- `NeuralNetworkHyperparameterOptimization`: 神经网络超参数优化
- `EngineeringDesignOptimization`: 工程设计优化
- `BusinessPortfolioOptimization`: 投资组合优化

## 使用模式

### 1. 基础单目标优化

```python
from core.base import BlackBoxProblem
from core.solver import BlackBoxSolverNSGAII

# 定义问题
problem = MyProblem()

# 创建求解器
solver = BlackBoxSolverNSGAII(problem)
solver.pop_size = 50
solver.max_generations = 100

# 运行优化
result = solver.run()
best_solution = result['pareto_solutions']['individuals'][0]
best_value = result['pareto_solutions']['objectives'][0]
```

### 2. 约束优化

```python
from utils.bias import create_standard_bias

# 创建带约束的问题
problem = ConstrainedProblem()

# 启用约束处理
solver = BlackBoxSolverNSGAII(problem)
solver.enable_bias = True
solver.bias_module = create_standard_bias(problem, penalty_weight=5.0)

result = solver.run()
```

### 3. 昂贵函数优化

```python
from solvers.surrogate import run_surrogate_assisted

# 使用代理模型减少评估次数
result = run_surrogate_assisted(
    problem=expensive_problem,
    surrogate_type='gp',
    real_eval_budget=100,
    initial_samples=20
)
```

### 4. 多目标优化

```python
from core.problems import ZDT1BlackBox

# 多目标问题
problem = ZDT1BlackBox(dimension=5)
solver = BlackBoxSolverNSGAII(problem)
solver.pop_size = 100
solver.max_generations = 150

result = solver.run()
pareto_front = result['pareto_solutions']
```

### 5. 批量实验

```python
from utils.parallel_runs import run_parallel_optimization
from utils.experiment import ExperimentTracker

# 并行运行多次优化
results = run_parallel_optimization(problem, n_runs=20)

# 记录实验
tracker = ExperimentTracker()
for i, result in enumerate(results):
    tracker.log_run(result, problem, solver.config)

# 比较结果
comparison = tracker.compare_experiments(
    [f"run_{i}" for i in range(len(results))]
)
```

## 性能调优建议

### 内存优化
- 对于大种群，考虑使用 `numpy.ndarray` 而不是 `list`
- 定期清理不必要的历史数据

### 计算优化
- 启用 numba 加速（如果可用）
- 使用并行处理评估昂贵的函数
- 对约束评估进行缓存

### 算法调优
- 根据问题复杂度调整种群大小
- 使用合适的变异率和交叉率
- 启用多样性初始化避免早熟收敛

## 错误处理

常见错误及解决方案：

1. **ImportError**: 确保正确设置了 Python 路径
2. **ValueError**: 检查边界设置是否正确
3. **MemoryError**: 减少种群大小或使用更高效的数据结构
4. **ConvergenceError**: 增加最大代数或调整算法参数