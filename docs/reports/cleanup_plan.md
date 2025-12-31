# 代码库整理执行计划

## 📋 总览

**目标**: 整理 NSGABlack 代码库，消除重复，统一架构，完善文档

**预计时间**: 1-2 周

**优先级**: 高优先级（影响代码可维护性）

---

## 🎯 阶段 1: 清理重复代码（第 1-2 天）

### 任务 1.1: 统一求解器基类

**问题**: `solvers/base_solver.py` 和 `core/base_solver.py` 可能重复

**检查步骤**:
```bash
# 1. 对比两个文件
diff core/base_solver.py solvers/base_solver.py

# 2. 查看所有导入
grep -r "from.*base_solver import" --include="*.py"
grep -r "from.*base_solver import" --include="*.py" | grep solvers/
```

**执行步骤**:
1. 如果 `solvers/base_solver.py` 有额外功能
   - 合并到 `core/base_solver.py`
   - 删除 `solvers/base_solver.py`
2. 更新所有导入：
   ```python
   # 之前
   from solvers.base_solver import BaseSolver

   # 之后
   from core.base_solver import BaseSolver
   ```

**预期结果**: ✅ 只有一个求解器基类 `core/base_solver.py`

---

### 任务 1.2: 统一 NSGA-II 实现

**问题**: `core/solver.py` 和 `solvers/nsga2.py` 功能可能重复

**职责划分**:
- `core/solver.py`: NSGA-II **核心算法**（非支配排序、拥挤距离、SBX、变异）
- `solvers/nsga2.py`: 用户友好的**封装接口**

**执行步骤**:
1. 确保 `core/solver.py` 只包含核心算法
2. 确保 `solvers/nsga2.py` 是对 `core/solver.py` 的封装
3. 添加清晰的注释说明职责

**示例**:
```python
# core/solver.py - NSGA-II 核心算法
class NSGA2Core:
    """NSGA-II 核心算法实现"""
    def fast_non_dominated_sort(self, ...): ...
    def calculate_crowding_distance(self, ...): ...
    def sbx_crossover(self, ...): ...
    def polynomial_mutation(self, ...): ...

# solvers/nsga2.py - 用户友好封装
from core.solver import NSGA2Core

class NSGA2Solver(BaseSolver):
    """NSGA-II 求解器 - 用户友好的封装"""
    def __init__(self, problem, config):
        self.core = NSGA2Core()
        # 用户配置映射到核心参数
        ...
```

**预期结果**: ✅ 核心算法和用户接口分离

---

## 🎯 阶段 2: 完善缺失模块（第 3-5 天）

### 任务 2.1: 实现 `operators/` 模块

**当前状态**: ⚠️ 空目录

**需要实现的文件**:

#### 1. `operators/crossover.py` - 交叉算子

```python
"""
遗传算法交叉算子

提供各种交叉算子：
- SBX (Simulated Binary Crossover)
- 单点交叉
- 多点交叉
- 算术交叉
"""

from abc import ABC, abstractmethod
import numpy as np

class CrossoverOperator(ABC):
    """交叉算子基类"""
    @abstractmethod
    def crossover(self, parent1, parent2, **kwargs):
        pass

class SBXCrossover(CrossoverOperator):
    """SBX 交叉（NSGA-II 标准）"""
    def __init__(self, eta_c=15, prob=0.9):
        self.eta_c = eta_c  # 分布指数
        self.prob = prob    # 交叉概率

    def crossover(self, parent1, parent2, bounds):
        """执行 SBX 交叉"""
        # 实现代码...
        pass

class SinglePointCrossover(CrossoverOperator):
    """单点交叉"""
    def crossover(self, parent1, parent2):
        # 实现代码...
        pass

class ArithmeticCrossover(CrossoverOperator):
    """算术交叉"""
    def crossover(self, parent1, parent2, alpha=0.5):
        # 实现代码...
        pass
```

#### 2. `operators/mutation.py` - 变异算子

```python
"""
遗传算法变异算子

提供各种变异算子：
- 多项式变异（Polynomial Mutation）
- 高斯变异
- 均匀变异
"""

class MutationOperator(ABC):
    """变异算子基类"""
    @abstractmethod
    def mutate(self, individual, bounds):
        pass

class PolynomialMutation(MutationOperator):
    """多项式变异（NSGA-II 标准）"""
    def __init__(self, eta_m=20, prob=0.1):
        self.eta_m = eta_m
        self.prob = prob

    def mutate(self, individual, bounds):
        # 实现代码...
        pass

class GaussianMutation(MutationOperator):
    """高斯变异"""
    def mutate(self, individual, bounds, sigma=0.1):
        # 实现代码...
        pass
```

#### 3. `operators/selection.py` - 选择算子

```python
"""
遗传算法选择算子

提供各种选择算子：
- 锦标赛选择
- 轮盘赌选择
- 随机通用采样
"""

class SelectionOperator(ABC):
    """选择算子基类"""
    @abstractmethod
    def select(self, population, fitness, n_select):
        pass

class TournamentSelection(SelectionOperator):
    """锦标赛选择"""
    def __init__(self, tournament_size=3):
        self.tournament_size = tournament_size

    def select(self, population, fitness, n_select):
        # 实现代码...
        pass
```

#### 4. `operators/__init__.py` - 导出

```python
from .crossover import (
    CrossoverOperator,
    SBXCrossover,
    SinglePointCrossover,
    ArithmeticCrossover
)
from .mutation import (
    MutationOperator,
    PolynomialMutation,
    GaussianMutation
)
from .selection import (
    SelectionOperator,
    TournamentSelection
)

__all__ = [
    'CrossoverOperator', 'SBXCrossover', 'SinglePointCrossover', 'ArithmeticCrossover',
    'MutationOperator', 'PolynomialMutation', 'GaussianMutation',
    'SelectionOperator', 'TournamentSelection'
]
```

**预期结果**: ✅ `operators/` 模块完整可用

---

### 任务 2.2: 创建单元测试套件

**创建目录结构**:
```
tests/
├── __init__.py
├── test_bias/
│   ├── __init__.py
│   ├── test_nsga2_bias.py
│   ├── test_sa_bias.py
│   ├── test_de_bias.py
│   └── test_bias_combinations.py
├── test_solvers/
│   ├── __init__.py
│   ├── test_nsga2.py
│   ├── test_multi_agent.py
│   └── test_surrogate.py
├── test_utils/
│   ├── __init__.py
│   ├── test_visualization.py
│   └── test_parallel_evaluator.py
└── test_integration/
    ├── __init__.py
    └── test_bias_with_nsga2.py
```

**示例测试**:
```python
# tests/test_bias/test_nsga2_bias.py
import pytest
import numpy as np
from bias.algorithmic.nsga2 import NSGA2Bias
from bias.core.base import OptimizationContext

def test_nsga2_bias_initialization():
    """测试 NSGA-II 偏置初始化"""
    bias = NSGA2Bias(
        initial_weight=0.1,
        rank_weight=0.5,
        crowding_weight=0.3
    )
    assert bias.name == "nsga2"
    assert bias.initial_weight == 0.1

def test_nsga2_bias_compute():
    """测试 NSGA-II 偏置计算"""
    bias = NSGA2Bias(initial_weight=0.1)

    # 创建上下文
    context = OptimizationContext(
        generation=10,
        population=[np.array([0.5, 0.5])],
        metrics={
            'pareto_rank': 0,
            'crowding_distance': 1.0,
            'is_dominated': False
        }
    )

    # 计算偏置
    x = np.array([0.5, 0.5])
    bias_value = bias.compute(x, context)

    # 验证
    assert isinstance(bias_value, float)
    assert bias_value < 0  # 应该是负偏置（奖励）
```

**预期结果**: ✅ 基础测试覆盖率达到 60%+

---

### 任务 2.3: 完善文档

#### 2.3.1 创建快速入门指南

**文件**: `docs/quickstart.md`

```markdown
# NSGABlack 快速入门

## 安装

\`\`\`bash
pip install nsgablack
\`\`\`

## 5 分钟上手

### 示例 1: 使用偏置增强 NSGA-II（无需多智能体）

\`\`\`python
from nsgablack import NSGA2Optimizer
from nsgablack.bias import NSGA2Bias, SimulatedAnnealingBias

# 定义问题
def my_objective(x):
    return sum(x**2)

# 创建偏置增强的优化器
optimizer = NSGA2Optimizer(
    problem=my_objective,
    biases=[
        NSGA2Bias(initial_weight=0.1),
        SimulatedAnnealingBias(initial_weight=0.1)
    ]
)

# 优化
result = optimizer.optimize(max_generations=100)
print(f"最优解: {result.best_x}")
print(f"最优值: {result.best_f}")
\`\`\`

### 示例 2: 使用多智能体系统

\`\`\`python
from nsgablack import MultiAgentSolver

# 创建多智能体优化器
solver = MultiAgentSolver(
    problem=my_objective,
    n_agents=5,
    agent_roles=['explorer', 'exploiter', 'waiter', 'advisor', 'coordinator']
)

# 优化
result = solver.optimize(max_generations=100)
\`\`\`
```

#### 2.3.2 创建 API 参考文档

**使用 Sphinx 自动生成**:

\`\`\`bash
# 安装 Sphinx
pip install sphinx sphinx-rtd-theme

# 创建文档目录
cd docs
sphinx-quickstart

# 配置 autodoc
# 修改 conf.py 添加扩展
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
]

# 生成文档
make html
\`\`\`

**预期结果**: ✅ 完整的 API 文档和快速入门指南

---

## 🎯 阶段 3: 优化架构（第 6-7 天）

### 任务 3.1: 清理 `bias/` 目录

**问题**: 存在 `bias/algorithmic_biases/` 和 `bias/algorithmic/` 重复

**执行步骤**:
1. 对比两个目录：
   \`\`\`bash
   diff -r bias/algorithmic/ bias/algorithmic_biases/
   \`\`\`

2. 合并到 `bias/algorithmic/`
3. 删除 `bias/algorithmic_biases/`

**预期结果**: ✅ 只有一个 `bias/algorithmic/` 目录

---

### 任务 3.2: 统一工具函数

**问题**: `utils/` 中有些工具不常用，应该分离

**执行步骤**:
1. **核心工具**（保留在 `utils/`）:
   - `visualization.py`
   - `parallel_evaluator.py`
   - `experiment.py`
   - `fast_non_dominated_sort.py`
   - `numba_helpers.py`

2. **辅助工具**（移到 `utils/extras/`）:
   - `feature_selection.py`
   - `manifold_reduction.py`
   - `solver_extensions.py`

3. 更新导入：
   \`\`\`python
   # 核心工具
   from utils import visualization, parallel_evaluator

   # 辅助工具
   from utils.extras import feature_selection
   \`\`\`

**预期结果**: ✅ `utils/` 结构清晰

---

### 任务 3.3: 创建配置管理系统

**文件结构**:
```
config/
├── __init__.py
├── default_config.py    ← 默认配置
├── user_config.py       ← 用户配置模板
└── schema.py            ← 配置验证
```

**示例**:
```python
# config/default_config.py
DEFAULT_SOLVER_CONFIG = {
    'nsga2': {
        'pop_size': 100,
        'max_generations': 100,
        'crossover_prob': 0.9,
        'mutation_prob': 0.1
    },
    'multi_agent': {
        'total_population': 200,
        'n_roles': 5,
        'communication_interval': 5
    }
}

DEFAULT_BIAS_CONFIG = {
    'nsga2': {
        'initial_weight': 0.1,
        'rank_weight': 0.5,
        'crowding_weight': 0.5
    },
    'sa': {
        'initial_weight': 0.1,
        'initial_temperature': 100.0,
        'cooling_rate': 0.99
    }
}
```

**预期结果**: ✅ 统一的配置管理

---

## 📊 检查清单

### 代码清理

- [ ] 统一求解器基类（只保留 `core/base_solver.py`）
- [ ] 统一 NSGA-II 实现（核心 + 封装分离）
- [ ] 清理 `bias/` 目录重复
- [ ] 实现 `operators/` 模块
- [ ] 更新所有导入路径

### 测试

- [ ] 创建 `tests/` 目录结构
- [ ] 编写单元测试（至少 60% 覆盖率）
- [ ] 编写集成测试
- [ ] 设置 CI/CD（GitHub Actions）

### 文档

- [ ] 创建快速入门指南
- [ ] 创建 API 参考文档（Sphinx）
- [ ] 更新 README.md
- [ ] 创建架构文档

### 配置

- [ ] 创建配置管理系统
- [ ] 提供用户配置模板
- [ ] 添加配置验证

---

## 🚀 执行脚本

### 自动化检查脚本

创建 `scripts/check_consistency.py`:

```python
#!/usr/bin/env python
"""代码库一致性检查脚本"""

import os
import sys
from pathlib import Path

def check_duplicate_base_solvers():
    """检查是否有重复的求解器基类"""
    base_solver_1 = Path("core/base_solver.py")
    base_solver_2 = Path("solvers/base_solver.py")

    if base_solver_1.exists() and base_solver_2.exists():
        print("⚠️  发现重复的 base_solver.py")
        print(f"   - {base_solver_1}")
        print(f"   - {base_solver_2}")
        return False
    return True

def check_operators_implementation():
    """检查 operators/ 模块是否实现"""
    required_files = [
        "operators/crossover.py",
        "operators/mutation.py",
        "operators/selection.py"
    ]

    missing = [f for f in required_files if not Path(f).exists()]

    if missing:
        print("⚠️  operators/ 模块不完整，缺少:")
        for f in missing:
            print(f"   - {f}")
        return False
    return True

def check_tests_exist():
    """检查测试目录是否存在"""
    tests_dir = Path("tests")
    if not tests_dir.exists():
        print("⚠️  缺少 tests/ 目录")
        return False

    required_subdirs = ["test_bias", "test_solvers", "test_utils"]
    for subdir in required_subdirs:
        if not (tests_dir / subdir).exists():
            print(f"⚠️  缺少测试目录: tests/{subdir}")

    return len(list(tests_dir.rglob("test_*.py"))) > 0

def main():
    print("=" * 60)
    print("NSGABlack 代码库一致性检查")
    print("=" * 60)

    checks = [
        ("求解器基类", check_duplicate_base_solvers),
        ("Operators 模块", check_operators_implementation),
        ("测试套件", check_tests_exist),
    ]

    results = []
    for name, check_func in checks:
        print(f"\n检查 {name}...")
        result = check_func()
        results.append((name, result))
        if result:
            print(f"✅ {name} 检查通过")
        else:
            print(f"❌ {name} 检查失败")

    print("\n" + "=" * 60)
    print("检查总结:")
    print("=" * 60)

    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name}: {status}")

    all_passed = all(r for _, r in results)
    if all_passed:
        print("\n🎉 所有检查通过！")
        return 0
    else:
        print("\n⚠️  部分检查未通过，需要整理")
        return 1

if __name__ == "__main__":
    sys.exit(main())
```

**使用**:
```bash
python scripts/check_consistency.py
```

---

## 📝 总结

### 优先级排序

| 阶段 | 任务 | 优先级 | 时间 |
|------|------|--------|------|
| 1.1 | 统一求解器基类 | 🔴 高 | 2 小时 |
| 1.2 | 统一 NSGA-II 实现 | 🔴 高 | 3 小时 |
| 2.1 | 实现 operators/ | 🟠 中 | 1 天 |
| 2.2 | 创建测试套件 | 🟠 中 | 2 天 |
| 2.3 | 完善文档 | 🟡 低 | 1 天 |
| 3.1 | 清理 bias/ | 🟠 中 | 2 小时 |
| 3.2 | 统一工具函数 | 🟡 低 | 2 小时 |
| 3.3 | 配置管理 | 🟡 低 | 3 小时 |

### 总计

- **高优先级**: 5 小时
- **中优先级**: 3.5 天
- **低优先级**: 1 天

**总计**: 约 1 周（每天 5-6 小时）

---

**创建日期**: 2025-12-31
**执行状态**: 待开始
