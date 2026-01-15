# NSGABlack 文档字符串改进指南

本文档说明如何为NSGABlack框架编写高质量的Google风格文档字符串。

## 一、为什么需要高质量文档字符串

文档字符串（Docstrings）的好处：
1. **自动生成API文档**：Sphinx可以提取文档
2. **IDE支持**：悬停显示帮助信息
3. **自文档化**：代码即文档
4. **提升可维护性**：清晰说明意图和用法

## 二、Google风格 vs NumPy风格

NSGABlack采用**Google风格**文档字符串（更简洁易读）。

### 对比示例

**Google风格（推荐）**：
```python
def evaluate(self, x: np.ndarray) -> float:
    """评估目标函数。

    Args:
        x: 决策变量向量，形状为(dimension,)。

    Returns:
        目标函数值。

    Raises:
        ValueError: 如果x的维度不正确。

    Examples:
        >>> problem = MyProblem()
        >>> problem.evaluate(np.array([1.0, 2.0]))
        5.0
    """
    return np.sum(x**2)
```

**NumPy风格（较冗长）**：
```python
def evaluate(self, x):
    """评估目标函数。

    Parameters
    ----------
    x : np.ndarray
        决策变量向量，形状为(dimension,)。

    Returns
    -------
    float
        目标函数值。

    Raises
    ------
    ValueError
        如果x的维度不正确。

    Examples
    --------
    >>> problem = MyProblem()
    >>> problem.evaluate(np.array([1.0, 2.0]))
    5.0
    """
    return np.sum(x**2)
```

## 三、基本模板

### 3.1 简单函数

```python
def function_name(arg1: str, arg2: int = 10) -> bool:
    """函数简短描述（一句话）。

    更详细的描述（可选）。可以多行，解释函数的用途、
    算法细节、注意事项等。

    Args:
        arg1: 参数1的描述。
        arg2: 参数2的描述，默认为10。

    Returns:
        返回值的描述。

    Raises:
        ValueError: 参数无效时抛出。
    """
    pass
```

### 3.2 类的文档

```python
class MyClass:
    """类的简短描述。

    更详细的类描述。说明类的用途、设计思路、使用场景等。

    Attributes:
        attr1: 属性1的描述。
        attr2: 属性2的描述。

    Examples:
        基本用法：

        >>> obj = MyClass(arg1="value")
        >>> obj.method()
        'result'

        高级用法：

        >>> obj = MyClass(arg1="value", arg2=123)
        >>> obj.method()
        'advanced_result'
    """

    def __init__(self, arg1: str, arg2: int = 10):
        """初始化MyClass。

        Args:
            arg1: 参数1的描述。
            arg2: 参数2的描述，默认为10。
        """
        self.attr1 = arg1
        self.attr2 = arg2

    def method(self) -> str:
        """方法的简短描述。

        Returns:
            方法返回值的描述。
        """
        return f"{self.attr1}-{self.attr2}"
```

### 3.3 带有复杂参数的函数

```python
from typing import List, Dict, Optional, Callable

def complex_function(
    data: List[np.ndarray],
    config: Optional[Dict[str, Any]] = None,
    callback: Optional[Callable[[float], None]] = None
) -> Dict[str, float]:
    """复杂函数的完整文档示例。

    这个函数处理多个数组，使用配置字典，支持回调函数。
    它是NSGABlack中处理复杂数据的典型示例。

    Args:
        data: 要处理的数组列表。每个数组的形状应该一致。
        config: 配置字典，包含以下键：
            - 'learning_rate' (float): 学习率，默认0.01
            - 'max_iter' (int): 最大迭代次数，默认100
            - 'tolerance' (float): 收敛容忍度，默认1e-6
            如果为None，使用默认配置。
        callback: 可选的回调函数，在每次迭代后调用。
            接收当前目标值作为参数。

    Returns:
        包含结果的字典：
            - 'final_value' (float): 最终目标函数值
            - 'iterations' (int): 实际迭代次数
            - 'converged' (bool): 是否收敛

    Raises:
        ValueError: 如果data为空或配置无效。
        RuntimeError: 如果优化过程失败。

    Examples:
        基本用法：

        >>> data = [np.array([1, 2, 3]), np.array([4, 5, 6])]
        >>> result = complex_function(data)
        >>> print(result['final_value'])
        1.234

        带配置：

        >>> config = {'learning_rate': 0.1, 'max_iter': 50}
        >>> result = complex_function(data, config=config)
        >>> print(result['converged'])
        True

        带回调：

        >>> def my_callback(value: float) -> None:
        ...     print(f"Current value: {value}")
        >>> result = complex_function(data, callback=my_callback)
        Current value: 5.0
        Current value: 3.0
        Current value: 1.5

    Note:
        这个函数使用了梯度下降算法，可能会陷入局部最优。
        建议多次运行并选择最佳结果。

    See Also:
        `simple_function`: 简化版的处理函数
        `advanced_function`: 增强版，支持并行处理
    """
    pass
```

## 四、特殊部分的文档

### 4.1 带有类型提示的函数

```python
from typing import Union, List

def process_data(
    data: Union[np.ndarray, List[float]],
    normalize: bool = True
) -> np.ndarray:
    """处理和标准化数据。

    Args:
        data: 输入数据，可以是numpy数组或列表。
        normalize: 是否标准化数据到[0,1]范围，默认为True。

    Returns:
        处理后的numpy数组。

    Raises:
        TypeError: 如果data不是数组或列表。
        ValueError: 如果data为空。

    Examples:
        >>> process_data([1, 2, 3])
        array([0. , 0.5, 1. ])

        >>> process_data(np.array([1, 2, 3]), normalize=False)
        array([1, 2, 3])
    """
    pass
```

### 4.2 抽象基类和接口

```python
from abc import ABC, abstractmethod

class Optimizer(ABC):
    """优化器抽象基类。

    所有优化器都应该继承这个类并实现optimize方法。

    Attributes:
        max_iterations: 最大迭代次数。
        tolerance: 收敛容忍度。
        verbose: 是否打印详细日志。

    Note:
        子类必须实现optimize方法。
    """

    def __init__(
        self,
        max_iterations: int = 100,
        tolerance: float = 1e-6,
        verbose: bool = False
    ):
        """初始化优化器。

        Args:
            max_iterations: 最大迭代次数，默认100。
            tolerance: 收敛容忍度，默认1e-6。
            verbose: 是否打印详细日志，默认False。
        """
        self.max_iterations = max_iterations
        self.tolerance = tolerance
        self.verbose = verbose

    @abstractmethod
    def optimize(self, x0: np.ndarray) -> np.ndarray:
        """执行优化。

        Args:
            x0: 初始点。

        Returns:
            优化后的解。

        Raises:
            NotImplementedError: 子类必须实现此方法。
        """
        raise NotImplementedError
```

### 4.3 生成器和异步函数

```python
def batch_generator(data: np.ndarray, batch_size: int):
    """批量数据生成器。

    Args:
        data: 完整数据集。
        batch_size: 每批的样本数量。

    Yields:
        每批数据的numpy数组。

    Examples:
        >>> data = np.arange(100)
        >>> for batch in batch_generator(data, batch_size=10):
        ...     print(batch.shape)
        (10,)
        (10,)
        ...
    """
    for i in range(0, len(data), batch_size):
        yield data[i:i + batch_size]
```

## 五、文档字符串最佳实践

### ✅ DO（推荐）

1. **以简短摘要开始**
```python
def evaluate(self, x):
    """评估目标函数。"""  # 简洁
```

2. **描述所有参数**
```python
def optimize(self, x0, lr=0.01, max_iter=100):
    """优化函数。

    Args:
        x0: 初始点。
        lr: 学习率，默认0.01。
        max_iter: 最大迭代次数，默认100。
    """
```

3. **提供使用示例**
```python
def run(self):
    """运行优化算法。

    Examples:
        >>> solver = MySolver()
        >>> solver.run()
        Optimization completed in 50 iterations.
    """
```

4. **说明可能的异常**
```python
def load(self, path):
    """加载数据。

    Raises:
        FileNotFoundError: 文件不存在。
        ValueError: 文件格式错误。
    """
```

### ❌ DON'T（不推荐）

1. **不要省略参数文档**
```python
# 不好
def process(x, y, z):
    """处理数据。"""
    pass
```

2. **不要写无用的文档**
```python
# 不好
def set_value(self, value):
    """设置value。"""  # 这不是文档
    pass
```

3. **不要使用过时的格式**
```python
# 不好（Epytext风格）
def evaluate(self, x):
    """@param x: 决策变量
    @return: 目标值
    """
    pass
```

## 六、改进现有文档的步骤

### 步骤1: 检查现有文档

```bash
# 使用pydocstyle检查文档风格
pip install pydocstyle
pydocstyle bias/ core/ solvers/
```

### 步骤2: 添加基本文档

```python
# 之前
def add_penalty(self, func, weight=1.0):
    self.penalties.append({'func': func, 'weight': weight})

# 之后
def add_penalty(self, func: Callable, weight: float = 1.0) -> None:
    """添加罚函数。

    Args:
        func: 罚函数，接受x返回惩罚值。
        weight: 权重，通常为1.0-10.0，默认1.0。
    """
    self.penalties.append({'func': func, 'weight': weight})
```

### 步骤3: 添加详细文档

```python
# 添加详细描述、示例、异常说明等
def add_penalty(
    self,
    func: Callable[[np.ndarray], float],
    weight: float = 1.0,
    name: str = ""
) -> None:
    """添加罚函数到偏置模块。

    罚函数用于惩罚不良解，增加其目标函数值。
    多个罚函数会线性叠加。

    Args:
        func: 罚函数，接受决策变量x，返回惩罚值（>=0）。
        weight: 权重系数，通常为1.0-10.0。较大的权重会
            更严格地惩罚违反约束的解，默认为1.0。
        name: 罚函数的名称，用于调试和日志，默认为空字符串。

    Examples:
        添加边界约束罚函数：

        >>> bias = BiasModule()
        >>> def bounds_penalty(x):
        ...     return np.sum(np.maximum(np.abs(x) - 5, 0))
        >>> bias.add_penalty(bounds_penalty, weight=10.0, name="bounds")

        添加自定义约束：

        >>> def custom_penalty(x):
        ...     if x[0] + x[1] > 10:
        ...         return (x[0] + x[1] - 10) ** 2
        ...     return 0
        >>> bias.add_penalty(custom_penalty, weight=5.0)

    Note:
        - 罚函数返回值必须非负
        - 罚函数会被调用多次，避免重复计算
        - 使用weight控制惩罚强度
    """
    self.penalties.append({'func': func, 'weight': weight, 'name': name})
```

## 七、自动化工具

### 7.1 检查文档风格

```bash
# 安装pydocstyle
pip install pydocstyle

# 检查特定模块
pydocstyle bias/bias.py

# 检查整个项目
pydocstyle .

# 配置pydocstyle（添加到setup.cfg或pydocstyle.ini）
[pydocstyle]
convention = google
add-ignore = D100,D104,D105  # 忽略一些规则
```

### 7.2 生成API文档

```bash
# 使用Sphinx生成文档
cd docs
make html

# 生成的文档在 docs/_build/html/
```

### 7.3 IDE集成

- **VSCode**: 安装`Python Docstring Generator`扩展
- **PyCharm**: 内置文档字符串模板
- **快捷键**:
  - PyCharm: Alt + Insert → Docstring
  - VSCode: Python Docstring Generator

## 八、检查清单

编写文档字符串时，确保：

- [ ] 每个公共模块有模块文档
- [ ] 每个公共类有类文档
- [ ] 每个公共方法/函数有文档
- [ ] 所有参数都有说明
- [ ] 返回值已说明
- [ ] 异常已记录
- [ ] 关键功能有示例
- [ ] 复杂逻辑有Note说明
- [ ] 相关函数有See Also
- [ ] 通过pydocstyle检查

## 九、模板文件

### bias模块模板

```python
"""模块简短描述。

详细描述...

Example:
    基本用法：

    >>> from bias import BiasModule
    >>> bias = BiasModule()
    >>> bias.add_penalty(my_penalty, weight=1.0)
"""
```

### solver模块模板

```python
"""求解器模块。

提供各种优化算法的实现...
"""
```

## 十、资源

- [Google Python风格指南](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)
- [Napolean文档扩展](https://sphinxcontrib-napoleon.readthedocs.io/)
- [pydocstyle文档](https://www.pydocstyle.org/)

---

**状态**: 🟡 进行中
**目标**: 90%+ 的公共API有完整文档
**当前进度**: ~60%（核心模块已完成）
