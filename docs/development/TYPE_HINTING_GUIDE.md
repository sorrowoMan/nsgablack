# NSGABlack 类型提示改进指南

本文档说明如何为NSGABlack框架添加和改进类型提示，以提升代码质量和IDE支持。

## 一、为什么需要类型提示

类型提示（Type Hints）的好处：
1. **更好的IDE支持**：自动补全、参数提示
2. **静态类型检查**：在运行前发现错误
3. **文档作用**：自文档化代码
4. **重构安全**：确保重构时类型一致性

## 二、基本类型提示示例

### 2.1 简单函数

```python
# ❌ 之前
def evaluate(x, dimension):
    return sum(x**2)

# ✅ 改进后
from typing import Union
import numpy as np

def evaluate(x: np.ndarray, dimension: int) -> float:
    """评估函数。

    Args:
        x: 决策变量向量
        dimension: 问题维度

    Returns:
        目标函数值
    """
    return float(np.sum(x**2))
```

### 2.2 复杂类型

```python
from typing import List, Dict, Tuple, Optional, Callable, Any

# 字典类型
def create_config(
    learning_rate: float,
    layers: List[int],
    activation: str
) -> Dict[str, Any]:
    return {
        'learning_rate': learning_rate,
        'layers': layers,
        'activation': activation
    }

# 可选参数
def optimize(
    x0: np.ndarray,
    max_iter: Optional[int] = None
) -> np.ndarray:
    if max_iter is None:
        max_iter = 100
    # ...

# 回调函数
CallbackType = Callable[[float, Dict[str, Any]], None]

def run_optimization(callback: CallbackType) -> None:
    callback(0.5, {'iteration': 10})
```

### 2.3 类的类型提示

```python
from typing import List, Optional

class Solver:
    """优化求解器。"""

    def __init__(
        self,
        problem: 'BlackBoxProblem',
        max_iterations: int = 100,
        tolerance: float = 1e-6
    ) -> None:
        """初始化求解器。

        Args:
            problem: 优化问题实例
            max_iterations: 最大迭代次数
            tolerance: 收敛容忍度
        """
        self.problem: BlackBoxProblem = problem
        self.max_iterations: int = max_iterations
        self.tolerance: float = tolerance
        self.population: List[np.ndarray] = []
        self.best_solution: Optional[np.ndarray] = None
        self.best_fitness: float = float('inf')

    def run(self) -> Tuple[np.ndarray, float]:
        """运行优化算法。

        Returns:
            (最优解, 最优目标值)
        """
        # ...
        return self.best_solution, self.best_fitness
```

## 三、Protocol（结构化类型）

使用`Protocol`定义接口：

```python
from typing import Protocol
from abc import abstractmethod

class Optimizer(Protocol):
    """优化器接口。"""

    def optimize(self, x0: np.ndarray) -> np.ndarray:
        """优化函数。"""
        ...

class Problem(Protocol):
    """问题接口。"""

    def evaluate(self, x: np.ndarray) -> float:
        """评估函数。"""
        ...

    @property
    def dimension(self) -> int:
        """问题维度。"""
        ...

    @property
    def bounds(self) -> List[Tuple[float, float]]:
        """变量边界。"""
        ...
```

## 四、泛型类型

```python
from typing import TypeVar, Generic, List

T = TypeVar('T')

class Population(Generic[T]):
    """种群容器。"""

    def __init__(self) -> None:
        self.individuals: List[T] = []

    def add(self, individual: T) -> None:
        self.individuals.append(individual)

    def get_best(self) -> T:
        return min(self.individuals, key=lambda x: x.fitness)

# 使用
class Individual:
    def __init__(self, x: np.ndarray, fitness: float):
        self.x = x
        self.fitness = fitness

pop: Population[Individual] = Population()
pop.add(Individual(np.array([1.0, 2.0]), 5.0))
```

## 五、TypedDict（字典类型）

```python
from typing import TypedDict

class OptimizationResult(TypedDict):
    """优化结果。"""
    solution: np.ndarray
    fitness: float
    iterations: int
    converged: bool
    message: str

def optimize(problem: Problem) -> OptimizationResult:
    """运行优化。"""
    # ...
    return {
        'solution': best_x,
        'fitness': best_f,
        'iterations': iters,
        'converged': True,
        'message': 'Optimization successful'
    }
```

## 六、常见类型标注模式

### 6.1 数组类型

```python
import numpy as np
from typing import Union

# 单个数组
def process(x: np.ndarray) -> np.ndarray:
    return x * 2

# 多个数组
def concatenate(arrays: List[np.ndarray]) -> np.ndarray:
    return np.concatenate(arrays)

# 特定形状
def reshape(x: np.ndarray) -> np.ndarray:
    return x.reshape(-1, 1)

# 可选数组
def normalize(x: Optional[np.ndarray] = None) -> np.ndarray:
    if x is None:
        x = np.zeros(10)
    return x / np.max(x)
```

### 6.2 回调函数

```python
from typing import Callable

# 简单回调
ProgressCallback = Callable[[int, float], None]

def optimize_with_callback(
    callback: ProgressCallback
) -> None:
    for i in range(10):
        callback(i, float(i) / 10)

# 使用
def my_callback(iteration: int, progress: float) -> None:
    print(f"Iteration {iteration}: {progress:.2%}")

optimize_with_callback(my_callback)
```

### 6.3 联合类型

```python
from typing import Union

Number = Union[int, float]

def compute(x: Number) -> Number:
    return x * 2

# 或者使用 TypeVar
T = TypeVar('T', bound=Union[int, float, np.ndarray])
```

## 七、改进现有代码的步骤

### 步骤1: 添加基本类型

```python
# 之前
def evaluate(self, x):
    return sum(x**2)

# 之后
def evaluate(self, x: np.ndarray) -> float:
    return float(np.sum(x**2))
```

### 步骤2: 添加复杂类型

```python
# 之前（旧 API，已移除）：add_penalty / add_reward
# 现在（推荐）：用 CallableBias + BiasModule.add
from nsgablack.bias import BiasModule
from nsgablack.bias.domain import CallableBias

def add_penalty_rule(
    bias: BiasModule,
    func: Callable[[np.ndarray], float],
    weight: float = 1.0,
) -> None:
    bias.add(CallableBias(name="rule", func=func, weight=weight, mode="penalty"))
```

### 步骤3: 添加类属性类型

```python
# 之前
class Solver:
    def __init__(self, problem):
        self.problem = problem
        self.population = []
        self.best_x = None

# 之后
class Solver:
    problem: 'Problem'
    population: List[np.ndarray]
    best_x: Optional[np.ndarray]

    def __init__(self, problem: 'Problem') -> None:
        self.problem = problem
        self.population = []
        self.best_x = None
```

## 八、mypy配置

项目已配置mypy（见`pyproject.toml`）：

```toml
[tool.mypy]
python_version = "3.8"
disallow_untyped_defs = false  # 渐进式：先不强制
check_untyped_defs = true      # 检查有类型的代码
ignore_missing_imports = true  # 忽略第三方库
```

运行mypy：

```bash
# 检查所有代码
mypy .

# 检查特定模块
mypy bias/ core/ representation/ utils/ catalog/

# 生成HTML报告
mypy --html-report ./mypy-report .
```

## 九、类型提示最佳实践

### ✅ DO（推荐）

1. **为公共API添加类型**
```python
def public_api(x: np.ndarray) -> float:
    ...
```

2. **使用描述性类型别名**
```python
FitnessValue = float
Solution = np.ndarray
Population = List[Solution]
```

3. **标注返回值**
```python
def optimize() -> Tuple[np.ndarray, float]:
    ...
```

4. **使用Protocol定义接口**
```python
class Evaluable(Protocol):
    def evaluate(self, x: np.ndarray) -> float:
        ...
```

### ❌ DON'T（不推荐）

1. **不要过度使用Any**
```python
# 不好
def process(x: Any) -> Any:
    ...

# 好
def process(x: np.ndarray) -> np.ndarray:
    ...
```

2. **不要忽略类型检查器警告**
```python
# 不要这样做
def bad_function(x):  # type: ignore
    ...
```

3. **不要使用过于复杂的类型**
```python
# 不好（过于复杂）
def process(
    x: Union[List[Dict[str, Union[int, float]]], None]
) -> Dict[str, List[float]]:
    ...

# 好（使用类型别名）
ConfigDict = Dict[str, Union[int, float]]
def process(x: Optional[List[ConfigDict]]) -> Dict[str, List[float]]:
    ...
```

## 十、渐进式类型提示策略

对于大型项目，采用渐进式策略：

### 阶段1: 核心模块（高优先级）
- `bias/bias_module.py`
- `core/solver.py`
- `core/base.py`
- （已清理）历史/实验目录（如需追溯请查看 git 历史）

### 阶段2: 工具模块（中优先级）
- `utils/representation/`
- `utils/analysis/metrics.py`
- （已清理）旧 experimental surrogate（如需追溯请查看 git 历史）
- `utils/surrogate/`（轻量工具层）

### 阶段3: 实验和示例（低优先级）
- ~~`deprecated/legacy/experiments/`~~（历史实验脚本，目录已清理；新内容建议放 examples/ 或 docs/cases/；如需追溯请查看 git 历史）

## 十一、检查清单

添加类型提示时，确保：

- [ ] 所有公共函数有类型提示
- [ ] 所有公共方法有类型提示
- [ ] 类属性有类型标注
- [ ] 复杂类型使用类型别名
- [ ] 避免过度使用`Any`
- [ ] 通过mypy检查
- [ ] IDE提供正确的自动补全

## 十二、资源

- [Python类型提示官方文档](https://docs.python.org/3/library/typing.html)
- [mypy文档](https://mypy.readthedocs.io/)
- [类型提示速查表](https://mypy.readthedocs.io/en/stable/cheat_sheet_py3.html)

---

**状态**: 🟡 进行中
**目标**: 70%+ 的代码有完整的类型提示
**当前进度**: ~40%（核心模块已完成）
