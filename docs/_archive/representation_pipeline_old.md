# Representation Pipeline 架构说明

## 概述

Representation Pipeline 是一个**模块化的表示处理系统**，用于处理不同类型的优化问题（整数、二进制、排列、矩阵、图等）。

它解决了纯偏置方法的性能问题：**直接在正确的表示空间初始化和搜索，而不是通过随机初始化+约束来"过滤"解**。

---

## 🎯 设计动机

### 问题：纯偏置方法的性能陷阱

**场景**：优化 50×50 整数矩阵（值范围 0-5000）

```python
# ❌ 低效方法：随机初始化 + 偏置约束
# 搜索空间：[0, 5000]^(2500) ≈ 10^15000 种可能
# 大部分随机值会被偏置拒绝，收敛极慢

# ✅ 高效方法：直接在整数空间初始化
# 初始化：从 0 或小范围开始
# 搜索：在整数空间变异
# 收敛：快 10-100 倍
```

### 解决方案：三层可插拔架构

```
┌─────────────────────────────────────────────┐
│           Representation Pipeline           │
├─────────────────────────────────────────────┤
│                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ Encoding │  │  Repair  │  │  Init/   │  │
│  │          │  │          │  │  Mutate  │  │
│  │ 编码/解码 │  │  修复    │  │ 初始化/  │  │
│  │          │  │          │  │  变异    │  │
│  └──────────┘  └──────────┘  └──────────┘  │
│       ↓             ↓             ↓         │
│  连续↔离散      非法→合法    直接生成合法   │
│                                             │
└─────────────────────────────────────────────┘
```

---

## 📐 核心接口

### 1. EncodingPlugin（编码插件）

```python
class EncodingPlugin(Protocol):
    def encode(self, x: Any, context: Optional[dict] = None) -> Any:
        """将外部表示转换为内部表示"""
        ...

    def decode(self, x: Any, context: Optional[dict] = None) -> Any:
        """将内部表示转换回外部表示"""
        ...
```

**用途**：
- **Random Key 编码**：连续向量 → 排列（用于 TSP）
- **二进制编码**：整数 → 二进制串
- **图编码**：邻接矩阵 ↔ 边列表

**示例**：
```python
class RandomKeyPermutationDecoder:
    def decode(self, x: np.ndarray) -> np.ndarray:
        # [0.3, 0.8, 0.1, 0.6] → [2, 0, 3, 1]
        return np.argsort(x)

    def encode(self, x: np.ndarray) -> np.ndarray:
        # [2, 0, 3, 1] → [0.3, 0.8, 0.1, 0.6]
        return np.asarray(x, dtype=float)
```

---

### 2. RepairPlugin（修复插件）

```python
class RepairPlugin(Protocol):
    def repair(self, x: Any, context: Optional[dict] = None) -> Any:
        """将非法解修复为合法解"""
        ...
```

**用途**：
- **边界修复**：裁剪超出边界的值
- **约束修复**：调整解以满足线性约束
- **结构修复**：确保图的连通性、排列的有效性

**示例**：
```python
class MatrixRowColSumRepair:
    def repair(self, x: np.ndarray, context: dict) -> np.ndarray:
        """修复矩阵以满足行列和约束"""
        mat = x.reshape(rows, cols)
        # 调整元素使得每行每列的和满足目标
        for i in range(rows):
            diff = target_row_sums[i] - np.sum(mat[i])
            mat[i, random_col] += diff
        return mat.reshape(-1)
```

---

### 3. InitPlugin（初始化插件）

```python
class InitPlugin(Protocol):
    def initialize(self, problem: Any, context: Optional[dict] = None) -> Any:
        """在正确的表示空间初始化解"""
        ...
```

**用途**：
- **直接在整数空间初始化**：不是 [0, 5000] 随机，而是 [0, 10] 开始
- **直接生成排列**：不是随机向量+解码，而是直接随机排列
- **直接生成稀疏矩阵**：控制非零元素数量

**示例**：
```python
@dataclass
class IntegerInitializer:
    low: int = 0      # 从小范围开始
    high: int = 10

    def initialize(self, problem, context) -> np.ndarray:
        # ✅ 直接生成整数 [0, 10]
        # ❌ 而不是随机 [0, 5000] 然后筛选
        return np.random.randint(self.low, self.high + 1, problem.dimension)
```

---

### 4. MutationPlugin（变异插件）

```python
class MutationPlugin(Protocol):
    def mutate(self, x: Any, context: Optional[dict] = None) -> Any:
        """在正确的表示空间变异解"""
        ...
```

**用途**：
- **整数变异**：整数加噪声 → 四舍五入回整数
- **排列变异**：交换、逆转、2-opt
- **稀疏变异**：保持稀疏结构

**示例**：
```python
class IntegerMutation:
    def mutate(self, x: np.ndarray, context) -> np.ndarray:
        # 整数 + 高斯噪声 → 回整到整数
        mutated = x + np.random.normal(0, self.sigma, size=x.shape)
        return np.clip(np.round(mutated), self.low, self.high).astype(int)
```

---

## 🔧 RepresentationPipeline

### 核心类

```python
@dataclass
class RepresentationPipeline:
    encoder: Optional[EncodingPlugin] = None
    repair: Optional[RepairPlugin] = None
    initializer: Optional[InitPlugin] = None
    mutator: Optional[MutationPlugin] = None

    def init(self, problem, context) -> Any:
        """初始化：生成初始解 → 可选修复"""
        if self.initializer is None:
            raise ValueError("initializer is required")
        x = self.initializer.initialize(problem, context)
        if self.repair is not None:
            x = self.repair.repair(x, context)
        return x

    def mutate(self, x, context) -> Any:
        """变异：变异解 → 可选修复"""
        if self.mutator is None:
            raise ValueError("mutator is required")
        x = self.mutator.mutate(x, context)
        if self.repair is not None:
            x = self.repair.repair(x, context)
        return x

    def decode(self, x, context) -> Any:
        """解码：内部表示 → 外部表示"""
        if self.encoder is None:
            return x
        return self.encoder.decode(x, context)

    def encode(self, x, context) -> Any:
        """编码：外部表示 → 内部表示"""
        if self.encoder is None:
            return x
        return self.encoder.encode(x, context)
```

### 与求解器集成

```python
# core/solver.py
class EvolutionSolver:
    def __init__(self, problem):
        ...
        self.representation_pipeline: RepresentationPipeline = None

    def set_representation_pipeline(self, pipeline):
        """附加表示管道"""
        self.representation_pipeline = pipeline

    def _initialize_population(self):
        """使用管道初始化种群"""
        if self.representation_pipeline is not None:
            for i in range(self.pop_size):
                context = {'generation': 0, 'bounds': self.var_bounds}
                self.population[i] = self.representation_pipeline.init(
                    self.problem, context
                )

    def mutate(self, offspring):
        """使用管道变异"""
        if self.representation_pipeline is not None:
            for i in range(pop_size):
                context = {'generation': self.generation}
                offspring[i] = self.representation_pipeline.mutate(
                    offspring[i], context
                )
```

---

## 📚 内置表示类型

### 1. 整数表示（`integer.py`）

```python
from nsgablack.representation import IntegerInitializer, IntegerMutation

# 直接在整数空间操作
pipeline = RepresentationPipeline(
    initializer=IntegerInitializer(low=0, high=10),  # 从小范围开始
    mutator=IntegerMutation(sigma=1.0, low=0, high=100),
)

# 使用
solver = EvolutionSolver(problem)
solver.set_representation_pipeline(pipeline)
result = solver.run()
```

**优点**：
- ✅ 初始化效率高（从小范围开始）
- ✅ 变异自然（整数空间）
- ✅ 无需后处理

---

### 2. 矩阵表示（`matrix.py`）

```python
from nsgablack.representation import (
    IntegerMatrixInitializer,
    MatrixRowColSumRepair,
    IntegerMatrixMutation,
)

# 带行列和约束的矩阵
pipeline = RepresentationPipeline(
    initializer=IntegerMatrixInitializer(rows=5, cols=5, low=0, high=5),
    repair=MatrixRowColSumRepair(
        row_sums=np.full(5, 20),
        col_sums=np.full(5, 20),
    ),
    mutator=IntegerMatrixMutation(sigma=0.5, low=0, high=10),
)
```

**支持的修复**：
- `MatrixRowColSumRepair` - 行列和约束
- `MatrixSparsityRepair` - 稀疏性约束
- `MatrixBlockSumRepair` - 块和约束

---

### 3. 二进制表示（`binary.py`）

```python
from nsgablack.representation import (
    BinaryInitializer,
    BitFlipMutation,
    BinaryCapacityRepair,
)

# 背包问题
pipeline = RepresentationPipeline(
    initializer=BinaryInitializer(probability=0.3),
    mutator=BitFlipMutation(rate=0.05),
    repair=BinaryCapacityRepair(capacity=50, exact=False),
)
```

---

### 4. 排列表示（`permutation.py`）

**方法 1：直接排列**

```python
from nsgablack.representation import (
    PermutationInitializer,
    PermutationSwapMutation,
)

# 直接在排列空间操作
pipeline = RepresentationPipeline(
    initializer=PermutationInitializer(),  # 直接生成排列
    mutator=PermutationSwapMutation(),      # 交换变异
)
```

**方法 2：随机键编码**

```python
from nsgablack.representation import (
    RandomKeyInitializer,
    RandomKeyMutation,
    RandomKeyPermutationDecoder,
)

# 连续空间优化 → 解码为排列
pipeline = RepresentationPipeline(
    initializer=RandomKeyInitializer(0.0, 1.0),
    mutator=RandomKeyMutation(sigma=0.1, low=0.0, high=1.0),
    encoder=RandomKeyPermutationDecoder(),
)
```

---

### 5. 连续表示（`continuous.py`）

```python
from nsgablack.representation import (
    UniformInitializer,
    GaussianMutation,
    ClipRepair,
)

# 连续优化
pipeline = RepresentationPipeline(
    initializer=UniformInitializer(low=-5.12, high=5.12),
    mutator=GaussianMutation(sigma=0.5, low=-5.12, high=5.12),
    repair=ClipRepair(low=-5.12, high=5.12),
)
```

---

### 6. 图表示（`graph.py`）

```python
from nsgablack.representation import (
    GraphEdgeInitializer,
    GraphEdgeMutation,
    GraphConnectivityRepair,
    GraphDegreeRepair,
)

# 图结构优化
pipeline = RepresentationPipeline(
    initializer=GraphEdgeInitializer(num_nodes=10, density=0.1),
    mutator=GraphEdgeMutation(rate=0.02),
    repair=GraphConnectivityRepair(),  # 确保连通性
)
```

**支持的修复**：
- `GraphConnectivityRepair` - 连通性约束
- `GraphDegreeRepair` - 度约束

---

## 🚀 完整示例

### 示例 1：整数优化

```python
from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.evolution_solver import EvolutionSolver
from nsgablack.representation import RepresentationPipeline
from nsgablack.representation.integer import IntegerInitializer, IntegerMutation

class IntegerProblem(BlackBoxProblem):
    def __init__(self):
        bounds = {f"x{i}": [0, 100] for i in range(10)}
        super().__init__(name="Integer", dimension=10, bounds=bounds)

    def evaluate(self, x):
        x = np.asarray(x, dtype=int)
        return [np.sum(x ** 2)]  # 最小化平方和

# 创建管道
pipeline = RepresentationPipeline(
    initializer=IntegerInitializer(low=0, high=10),  # 从小范围开始
    mutator=IntegerMutation(sigma=1.0, low=0, high=100),
)

# 求解
problem = IntegerProblem()
solver = EvolutionSolver(problem)
solver.set_representation_pipeline(pipeline)
result = solver.run()
```

### 示例 2：TSP（随机键编码）

```python
class TSPRandomKeysProblem(BlackBoxProblem):
    def __init__(self, cities):
        self.cities = np.array(cities)
        self.decoder = RandomKeyPermutationDecoder()
        n = len(cities)
        bounds = {f"x{i}": [0.0, 1.0] for i in range(n)}
        super().__init__(name="TSP", dimension=n, bounds=bounds)

    def evaluate(self, x):
        tour = self.decoder.decode(np.asarray(x))
        total = 0.0
        for i in range(len(tour)):
            j = (i + 1) % len(tour)
            total += np.linalg.norm(self.cities[tour[i]] - self.cities[tour[j]])
        return [total]

# 创建管道
pipeline = RepresentationPipeline(
    initializer=RandomKeyInitializer(0.0, 1.0),
    mutator=RandomKeyMutation(sigma=0.08, low=0.0, high=1.0),
    encoder=problem.decoder,
)

# 求解
solver = EvolutionSolver(problem)
solver.set_representation_pipeline(pipeline)
result = solver.run()
```

---

## 📊 性能对比

### 场景：50×50 整数矩阵（值 0-5000）

| 方法 | 初始化 | 收敛代数 | 总时间 |
|------|--------|----------|--------|
| **随机 + 偏置约束** | 随机 [0, 5000] | >500 | 很慢 |
| **整数管道** | 从 [0, 10] 开始 | ~50 | **快 10-100 倍** |

### 原因分析

```python
# ❌ 随机 + 约束：大部分初始化无效
init = np.random.randint(0, 5000, size=2500)
# 99.9% 的值会被偏置系统拒绝

# ✅ 整数管道：从小范围开始，快速收敛
init = np.random.randint(0, 10, size=2500)
# 所有初始化都有效，快速接近最优解
```

---

## 🎯 设计原则

### 1. **直接在正确的空间操作**

```python
# ❌ 错误：连续空间 → 约束 → 整数
x = np.random.uniform(0, 5000, size=n)
x = bias.apply_constraint(x)  # 大部分值被拒绝

# ✅ 正确：直接整数空间
x = np.random.randint(0, 10, size=n)  # 从小范围开始
```

### 2. **修复是保障，不是主要机制**

```python
# 优先：通过初始化和变异生成合法解
# 修复：处理意外情况（如边界溢出）

pipeline = RepresentationPipeline(
    initializer=IntegerInitializer(low=0, high=10),  # 主要机制
    mutator=IntegerMutation(sigma=1.0),              # 主要机制
    repair=IntegerRepair(low=0, high=100),          # 保障机制
)
```

### 3. **编码用于表示转换，不是约束处理**

```python
# 编码：表示转换（连续 ↔ 离散）
encoder = RandomKeyPermutationDecoder()  # 连续向量 → 排列

# 约束：用偏置系统处理
bias = ConstraintBias()  # TSP 约束
```

---

## 🔧 与偏置系统的关系

### 清晰的职责分离

```
┌─────────────────────────────────────────────┐
│         Representation Pipeline              │
│  负责：编码、初始化、变异、修复               │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│            Bias System                      │
│  负责：软约束、硬约束、搜索引导               │
└─────────────────────────────────────────────┘
```

### 协作示例

```python
# Representation Pipeline：处理表示
pipeline = RepresentationPipeline(
    initializer=IntegerInitializer(low=0, high=10),
    mutator=IntegerMutation(sigma=1.0),
)

# Bias System：处理约束
bias = ConstraintBias(
    min_value=0,
    max_value=100,
    penalty_weight=1000,
)

# 求解器：组合使用
solver = EvolutionSolver(problem)
solver.set_representation_pipeline(pipeline)
solver.bias_module = bias
result = solver.run()
```

---

## 📈 扩展性

### 添加新表示类型

```python
# 1. 定义新插件
@dataclass
class MyCustomInitializer:
    def initialize(self, problem, context):
        return ...  # 自定义初始化逻辑

@dataclass
class MyCustomMutation:
    def mutate(self, x, context):
        return ...  # 自定义变异逻辑

# 2. 创建管道
pipeline = RepresentationPipeline(
    initializer=MyCustomInitializer(),
    mutator=MyCustomMutation(),
)

# 3. 附加到求解器
solver.set_representation_pipeline(pipeline)
```

### 组合多个插件

```python
# 复杂管道：编码 + 初始化 + 变异 + 多重修复
pipeline = RepresentationPipeline(
    encoder=MyEncoder(),                    # 编码/解码
    initializer=MyInitializer(),             # 初始化
    mutator=MyMutation(),                    # 变异
    repair=CompositeRepair([                 # 组合修复
        BoundaryRepair(),                    # 1. 边界
        ConstraintRepair(),                  # 2. 约束
        StructureRepair(),                   # 3. 结构
    ]),
)
```

---

## ✅ 最佳实践

### 1. 选择合适的表示类型

| 问题类型 | 推荐表示 | 原因 |
|----------|----------|------|
| 整数优化 | `IntegerInitializer` | 直接在整数空间 |
| 排列（TSP） | `RandomKey` + `Decoder` | 连续优化 → 排列 |
| 背包问题 | `BinaryInitializer` + `CapacityRepair` | 0/1 选择 |
| 矩阵约束 | `MatrixInitializer` + `RowColSumRepair` | 行列和约束 |
| 图结构 | `GraphInitializer` + `ConnectivityRepair` | 连通性 |

### 2. 从小范围初始化

```python
# ✅ 好：从小范围开始
pipeline = RepresentationPipeline(
    initializer=IntegerInitializer(low=0, high=10),
)

# ❌ 差：从大范围开始
pipeline = RepresentationPipeline(
    initializer=IntegerInitializer(low=0, high=5000),
)
```

### 3. 适度使用修复

```python
# ✅ 好：修复作为保障
pipeline = RepresentationPipeline(
    initializer=IntegerInitializer(low=0, high=10),  # 主要合法
    mutator=IntegerMutation(sigma=1.0),              # 主要合法
    repair=IntegerRepair(low=0, high=100),          # 偶尔修复
)

# ❌ 差：依赖修复生成合法解
pipeline = RepresentationPipeline(
    initializer=RandomInitializer(),      # 大部分非法
    mutator=RandomMutation(),             # 大部分非法
    repair=HeavyRepair(),                 # 依赖修复
)
```

### 4. 与偏置系统协同

```python
# Representation Pipeline：表示
pipeline = RepresentationPipeline(
    initializer=IntegerInitializer(low=0, high=10),
)

# Bias System：约束
bias = DomainBias(
    constraints=[...],
    penalty_weight=1000,
)

# 求解器：组合
solver.set_representation_pipeline(pipeline)
solver.bias_module = bias
```

---

## 🎓 总结

### Representation Pipeline 的价值

1. **性能**：直接在正确的空间初始化，避免大搜索空间的浪费
2. **模块化**：编码、初始化、变异、修复分离，可复用
3. **灵活性**：可插拔设计，易于扩展新表示类型
4. **清晰性**：职责明确，与偏置系统协同

### 与偏置系统的关系

- **Representation Pipeline**：处理**表示**（如何编码、初始化、变异）
- **Bias System**：处理**约束**（软约束、硬约束、搜索引导）

两者协同工作，但不重复职责。

---

**文档版本**: v1.0
**创建日期**: 2025-12-31
**作者**: NSGABlack Team