# 并行评估集成指南

本指南介绍如何将种群内并行评估功能集成到nsgablack优化框架中。

## 什么是种群内并行评估

种群内并行评估是指在单次优化运行中，并行评估整个种群的个体，这与现有的 `utils/parallel/runs.py`（多次独立运行的并行）不同。

- **现有并行**: 多次独立运行优化 → `utils/parallel/runs.py`
- **新增并行**: 单次运行中并行评估种群 → `utils/parallel/evaluator.py`

## 架构设计

### 核心组件

1. **ParallelEvaluator** (`utils/parallel/evaluator.py`)

   - 核心并行评估引擎
   - 支持多种后端 (process, thread, joblib, ray)
   - 智能负载均衡和错误处理
2. **with_parallel_evaluation** (`utils/parallel/integration.py`)

   - 推荐的“集成方式”：在不改 Solver 源码的前提下，把并行评估能力注入到一次运行里
   - 保持 core 干净：并行属于工程能力（tool/plugin/suite），不属于求解器底座强绑定能力
3. **SmartEvaluatorSelector** (智能选择器)

   - 根据问题特性自动选择最佳并行策略
   - 考虑种群规模、问题类型、环境因素

## 使用方式

### 方式1: 独立使用 (推荐)

```python
from nsgablack.utils.parallel import ParallelEvaluator
from nsgablack.core.solver import BlackBoxSolverNSGAII

# 创建问题
problem = MyProblem()

# 创建并行评估器
evaluator = ParallelEvaluator(
    backend="process",
    max_workers=4,
    verbose=True
)

# 评估种群
population = np.random.uniform(-5, 5, (100, 10))
objectives, violations = evaluator.evaluate_population(population, problem)
```

### 方式2: 在一次运行中注入并行评估 (推荐)

```python
from nsgablack.utils.parallel import with_parallel_evaluation
from nsgablack.core.solver import BlackBoxSolverNSGAII

solver = BlackBoxSolverNSGAII(problem, pop_size=100, max_generations=200)

with with_parallel_evaluation(
    solver,
    backend="process",
    max_workers=4,
    auto_configure=True,
):
    result = solver.run()
```

说明：
- 这种方式不会改变你的 Solver 类型，只是在运行期间把 `ParallelEvaluator` 挂接进去
- 更符合当前框架的“单一路径收敛”：core 不做装配，装配在 suite/tool/plugin 层完成

## 配置选项

### 后端选择

```python
# CPU密集型任务 (推荐)
ParallelEvaluator(backend="process")

# I/O密集型任务
ParallelEvaluator(backend="thread")

# 大种群，内存敏感
ParallelEvaluator(backend="joblib")

# 分布式计算 (需要安装ray)
ParallelEvaluator(backend="ray")
```

### 性能调优

```python
evaluator = ParallelEvaluator(
    backend="process",
    max_workers=8,                    # 工作进程数
    chunk_size=10,                   # 批处理大小
    enable_load_balancing=True,      # 负载均衡
    retry_errors=True,               # 错误重试
    max_retries=3,                   # 最大重试次数
    verbose=True                     # 详细日志
)
```

### 智能自动配置

```python
from nsgablack.utils.parallel import SmartEvaluatorSelector

# 自动选择最佳配置
evaluator = SmartEvaluatorSelector.select_evaluator(
    problem=my_problem,
    population_size=100
)
```

## 性能对比

### 何时使用并行评估

| 种群规模 | 评估时间 | 推荐策略           |
| -------- | -------- | ------------------ |
| < 10     | < 1ms    | 不推荐并行         |
| 10-50    | 1-10ms   | 2-4进程            |
| 50-200   | 10-100ms | 4-8进程            |
| > 200    | > 100ms  | 8+进程，使用joblib |

### 实际测试结果

```python
# 运行性能测试
```

典型结果：

- 种群规模100: 3.2x 加速比 (4进程)
- 种群规模200: 3.8x 加速比 (4进程)
- 种群规模500: 4.0x 加速比 (8进程)

## 集成到现有代码

### 最小修改集成

```python
from nsgablack.utils.parallel import with_parallel_evaluation

solver = BlackBoxSolverNSGAII(problem)
with with_parallel_evaluation(solver, backend="process", max_workers=4):
    result = solver.run()
```

### 渐进式集成

```python
# 第一步：添加并行选项
class MySolver(BlackBoxSolverNSGAII):
    def __init__(self, problem, enable_parallel=False):
        super().__init__(problem)
        if enable_parallel:
            self.setup_parallel()

# 第二步：替换评估方法
def evaluate_population(self, population):
    if hasattr(self, 'parallel_evaluator'):
        return self.parallel_evaluator.evaluate_population(population, self.problem)
    else:
        return super().evaluate_population(population)
```

## 常见问题和解决方案

### 1. 导入错误

```python
# 确保添加了路径设置
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

### 2. 进程间序列化问题

```python
# 避免使用lambda函数和闭包
def my_evaluation_function(x):
    return x[0]**2 + x[1]**2  # 顶级函数

problem.evaluator = lambda x: x**2  #  无法序列化
```

### 3. 内存不足

```python
# 减少工作进程数
evaluator = ParallelEvaluator(
    backend="joblib",      # 更好的内存管理
    max_workers=2,         # 减少进程数
    chunk_size=5          # 小块处理
)
```

### 4. 性能不如预期

```python
# 检查评估时间是否太短
if avg_eval_time < 0.001:  # < 1ms
    print("评估时间太短，并行开销可能大于收益")
    # 考虑批量评估或增加计算复杂度
```

## 监控和调试

### 性能统计

```python
# 获取详细统计
stats = evaluator.get_stats()
print(f"总评估次数: {stats['total_evaluations']}")
print(f"平均评估时间: {stats['avg_evaluation_time']*1000:.2f}ms")
print(f"错误率: {stats['error_count']/stats['total_evaluations']:.2%}")

# 估算加速比
speedup = evaluator.estimate_speedup(population_size=100, avg_eval_time=0.01)
print(f"预估加速比: {speedup:.2f}x")
```

### 调试模式

```python
# 启用详细日志
evaluator = ParallelEvaluator(
    verbose=True,
    retry_errors=True,
    max_retries=1
)

# 运行测试
objectives, violations = evaluator.evaluate_population(
    population[:10],  # 先测试小样本
    problem
)
```

## 最佳实践

### 1. 自动配置优先

```python
from nsgablack.utils.parallel import with_parallel_evaluation

solver = BlackBoxSolverNSGAII(problem)
with with_parallel_evaluation(solver, auto_configure=True):
    result = solver.run()
```

### 2. 性能监控

```python
stats = evaluator.get_stats()
print(f"avg_eval_time(ms)={stats['avg_evaluation_time']*1000:.2f}")
print(f"errors={stats['error_count']}")
```

### 3. 错误处理

```python
# 启用重试机制
evaluator = ParallelEvaluator(
    retry_errors=True,
    max_retries=3
)
```

### 4. 资源管理

```python
# 使用上下文管理器
with ParallelEvaluator(backend="process") as evaluator:
    results = evaluator.evaluate_population(population, problem)
# 自动清理资源
```

## 🔮 扩展和定制

### 自定义后端

```python
class CustomBackend(ParallelEvaluator):
    def __init__(self, custom_config):
        super().__init__(backend="custom")
        self.custom_config = custom_config

    def _evaluate_with_custom_backend(self, tasks):
        # 实现自定义并行逻辑
        pass
```

### 集成到其他求解器

```python
from nsgablack.utils.parallel import with_parallel_evaluation

solver = MyCustomSolver(problem)
with with_parallel_evaluation(solver, backend="process", max_workers=4):
    result = solver.run()
```

## 相关资源

- [API文档](API_REFERENCE.md#并行评估)
- [性能基准测试](benchmarks/parallel_benchmark.py)

## Legacy: Mixin/装饰器方式（不推荐）

历史版本曾提供 `SolverExtensions`（Mixin/动态类注入）。为了避免 core 侵入性、减少维护压力，
这条路径已降权为 legacy（仍保留在 `nsgablack.utils.compat.solver_extensions` 供参考）。

---

**总结**: 种群内并行评估提供了强大的性能提升，通过多种集成方式可以轻松添加到现有代码中。建议从小规模测试开始，逐步应用到生产环境。
