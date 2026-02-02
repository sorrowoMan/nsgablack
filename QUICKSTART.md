# nsgablack 快速开始指南

<div align="center">

**5 分钟上手 - 从安装到第一个优化结果**

</div>

---

## 目录

- [安装](#安装)
- [5 分钟快速体验](#5-分钟快速体验)
- [常见使用场景](#常见使用场景)
- [进阶使用](#进阶使用)
- [故障排除](#故障排除)

---

## 安装

### 1. 克隆项目

```bash
git clone https://github.com/sorrowoMan/nsgablack.git
cd nsgablack
```

### 2. 安装依赖

```bash
# 核心依赖（必需）
pip install -r requirements-core.txt

# 标准依赖（推荐）
pip install -r requirements.txt

# 开发依赖（可选）
pip install -r requirements-dev.txt
```

### 3. 验证安装

```bash
python -c "from nsgablack.core import BlackBoxSolverNSGAII; print('安装成功!')"
```

---

## 5 分钟快速体验

### 可选：运行前做一次 Run Inspector 审查（很“老土”，但极其有用）

```bash
python -m nsgablack run_inspector --entry examples/end_to_end_workflow_demo.py:build_solver
```

### 示例 1：最简单的多目标优化

```python
from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.solver import BlackBoxSolverNSGAII
import numpy as np

# 定义一个简单问题
class SimpleMultiObjective(BlackBoxProblem):
    def __init__(self):
        super().__init__(
            name="SimpleMO",
            dimension=2,
            objectives=["f1", "f2"],
            bounds=[(-5, 5), (-5, 5)],
        )

    def evaluate(self, x):
        f1 = float(np.sum(x ** 2))
        f2 = float(np.sum((x - 2) ** 2))
        return np.array([f1, f2])

problem = SimpleMultiObjective()

# 求解
solver = BlackBoxSolverNSGAII(problem)
result = solver.run(return_dict=True)

# 输出结果
pareto = result.get("pareto_solutions", {})
count = len(pareto.get("individuals", [])) if isinstance(pareto, dict) else 0
print(f"找到 {count} 个 Pareto 解")
```

**预期输出**：
```
找到 100 个 Pareto 最优解
运行时间: 3.45 秒
```

### 示例 2：自定义问题

```python
from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.solver import BlackBoxSolverNSGAII
import numpy as np

# 定义自己的问题
class MyProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(
            name="SimpleProblem",
            dimension=2,
            bounds={"x1": [0, 10], "x2": [0, 10]}
        )

    def evaluate(self, x):
        # 两个目标：最小化到原点和到 (10,10) 的距离
        f1 = x[0]**2 + x[1]**2
        f2 = (x[0]-10)**2 + (x[1]-10)**2
        return [f1, f2]

# 求解
problem = MyProblem()
solver = BlackBoxSolverNSGAII(problem)
solver.pop_size = 50
solver.max_generations = 100
result = solver.run()
```

---

## 常见使用场景

...（保持原文）

---

## 进阶使用

...（保持原文）

---

## 故障排除

...（保持原文）

