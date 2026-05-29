# 01. 创建标准项目并跑通第一版

本章目标：从零创建一个可运行的 `nsgablack` 标准项目。每一步都给出可执行命令和可运行的代码。

**关键原则**：项目的正式运行入口在顶层 `run_project.py`，不在 case 内的 `run_solver.py`。Case 内的 `run_solver.py --check` 只是独立调试入口。

---

## 1. 创建项目

```powershell
python -m nsgablack project new my_project
cd my_project
```

生成的结构：

```text
my_project/
  README.md               # 项目说明
  START_HERE.md           # 快速入门
  project_config.py       # 编排配置（STAGES / GROUPS）
  run_project.py          # 【正式运行入口】
  _bootstrap.py           # 路径引导
  cases/
    README.md
```

> `_bootstrap.py` 负责确保项目根和框架包在 `sys.path` 中。每个入口脚本都应该在开头调用它。

## 2. 添加第一个 case

```powershell
python -m nsgablack project add-case my_solver --type solver
```

`--type solver` 和 `--type trainer` 生成完全相同的目录结构。差异仅在 catalog 注册的 `kind` 字段。

生成的 case 结构：

```text
cases/my_solver/
  build_solver.py         # canonical 装配入口（你在这里写装配逻辑）
  build_trainer.py        # 别名: from .build_solver import build_solver as build_trainer
  run_solver.py           # 独立调试 CLI（--check 验证装配，不加参数运行求解）
  run_trainer.py          # 别名: from .run_solver import main
  config.py               # 组件注册聚合
  problem/                # Problem 定义
  pipeline/               # encode/decode/init/mutate/repair + data
  adapter/                # 搜索策略配置
  bias/                   # 软引导
  plugins/                # 生命周期能力（替代 legacy capabilities/）
  evaluation/             # 评估运行时
  runtime/                # L0 资源
  solver/                 # Solver 核心配置
```

## 3. 第一次检查 — 只验证装配，不跑优化

```powershell
cd cases/my_solver
python run_solver.py --check
```

输出应该类似：

```text
[check] assembly ok | problem=None | pipeline=None | adapter=None
```

此时 `build_solver()` 返回 `None`（模板的占位实现）。这是正常的——我们先确认骨架正确。

再跑 doctor：

```powershell
python -m nsgablack project doctor --path . --build --strict --format problem
```

> 如果 doctor 报 `missing-file: build_solver.py`，说明你不在 case 目录内。Doctor 在项目根和 case 目录内行为不同——项目根检查 `cases/` 结构，case 内检查标准脚手架。

## 4. 定义第一个 Problem

编辑 `cases/my_solver/problem/__init__.py`（或新建 `my_problem.py`）：

```python
"""My first multi-objective problem."""
import numpy as np


class MyProblem:
    """Minimize f1 = sum(x^2), f2 = sum((x-1)^2), s.t. x in [-5, 5]."""
    name = "my_problem"
    dimension = 2
    objectives = ("f1", "f2")

    def __init__(self):
        self.xl = np.array([-5.0, -5.0])
        self.xu = np.array([5.0, 5.0])

    def evaluate(self, x):
        x = np.asarray(x, dtype=float).ravel()
        f1 = float(np.sum(x ** 2))
        f2 = float(np.sum((x - 1.0) ** 2))
        return np.array([f1, f2], dtype=float)

    def evaluate_constraints(self, x):
        return np.zeros(0, dtype=float)
```

## 5. 装配 build_solver()

编辑 `cases/my_solver/build_solver.py`：

```python
"""My first solver assembly."""
import numpy as np
from nsgablack.core import ComposableSolver
from nsgablack.adapters import NSGA2Adapter
from nsgablack.representation import RepresentationPipeline, UniformInitializer, GaussianMutation, ClipRepair
from problem import MyProblem


def build_solver():
    problem = MyProblem()

    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=-5.0, high=5.0),
        mutator=GaussianMutation(sigma=0.25, low=-5.0, high=5.0),
        repair=ClipRepair(low=-5.0, high=5.0),
    )

    adapter = NSGA2Adapter(pop_size=50)

    solver = ComposableSolver(
        problem=problem,
        representation_pipeline=pipeline,
        adapter=adapter,
    )
    return solver
```

## 6. 再次检查装配

```powershell
python run_solver.py --check
```

输出应该变为：

```text
[check] assembly ok | problem=MyProblem | pipeline=RepresentationPipeline | adapter=NSGA2Adapter
```

## 7. 配置项目编排

回到项目根，编辑 `project_config.py`：

```python
"""Project orchestration: single solver, single stage."""
from typing import Dict, Any, List

STAGES: List[Dict[str, Any]] = [
    {
        "name": "solve",
        "cases": ["my_solver"],
        "policy": "run_all_in_parallel",
    },
]

GROUPS: Dict[str, Any] = {
    "default": {"stages": ["solve"]},
}
```

`run_project.py` 已经能读取这些配置并自动发现和运行 case。不需要修改 `run_project.py`。

## 8. 第一次正式运行

**从项目根目录运行**（不是 case 目录！）：

```powershell
cd ../..    # 回到 my_project/
python run_project.py
```

输出类似：

```text
Running project group: default
  Preparing case: my_solver for stage: solve
    Running solver for my_solver...
Project run finished.
```

## 9. 独立调试单个 case

如果需要单独调试某个 case（不通过顶层编排）：

```powershell
cd cases/my_solver
python run_solver.py
```

这会绕过 `project_config.py` 的编排，直接运行这个 case 的求解器。**这只用于调试**，正式运行始终从项目根启动。

## 10. 运行入口层级总结

```text
正式运行:  my_project/run_project.py          ← 唯一正式入口
             │
             ├─ 读取 project_config.py (STAGES/GROUPS)
             ├─ 发现 cases/*/build_solver.py
             ├─ 按 stage 顺序执行
             └─ 通过 SnapshotStore 传递 artifact

调试运行:  cases/my_solver/run_solver.py      ← 仅独立调试
             │
             └─ 直接调用 build_solver() → solver.run()
```

## 11. 第一版完成标准

- [x] `python run_solver.py --check` 显示 problem/pipeline/adapter 已挂载
- [x] `python -m nsgablack project doctor --path . --strict` 无 error
- [x] 从项目根 `python run_project.py` 能启动
- [x] 理解三层结构：Project → Case → Scaffold

## 12. 常见错误

| 现象 | 原因 | 处理 |
|---|---|---|
| `ModuleNotFoundError: No module named 'problem'` | 从错误的目录运行 | `cd` 到 case 目录，或确认 `_bootstrap.py` 已执行 |
| Doctor 报 `missing-file: build_solver.py` | 在项目根跑了 case 级 doctor | `cd` 到 case 目录再跑 doctor |
| `run_project.py` 只打印 "Project run finished (simulation)" | 模板的 `run_project.py` 是占位实现 | 确认 STAGES 中的 `case_name` 与目录名一致 |
| 外层运行没输出 | `run_project.py` 里 solver 的 `solve()` 被注释了 | 取消注释或补上真正的运行逻辑 |
