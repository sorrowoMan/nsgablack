# 02. 组件配置与多 Solver/Trainer 编排

本章覆盖：（1）每个组件层怎么配置和装配，（2）多 solver / 多 trainer 怎么在 `project_config.py` 中编排并运行。

---

## 1. 组件配置：Spec → Registry → Builder → Mount

标准装配链条：

```text
Spec (参数) → Registry (注册) → Builder (构造) → Mount (挂载到 solver)
```

每个组件层都遵循同一模式。以下用 Problem 为例。

### 1.1 Problem 配置

**`problem/my_problem.py`** — 定义 Problem 类：

```python
import numpy as np

class MyProblem:
    """Minimize f1 = sum(x^2), f2 = sum((x-1)^2)."""
    name = "my_problem"
    dimension = 2
    objectives = ("f1", "f2")

    def __init__(self, penalty: float = 1.0):
        self.xl = np.array([-5.0, -5.0])
        self.xu = np.array([5.0, 5.0])
        self.penalty = float(penalty)

    def evaluate(self, x):
        x = np.asarray(x, dtype=float).ravel()
        return np.array([float(np.sum(x**2)), float(np.sum((x-1)**2))], dtype=float)

    def evaluate_constraints(self, x):
        return np.zeros(0, dtype=float)
```

**`problem/config.py`** — 注册到 Registry：

```python
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass(frozen=True)
class ProblemSpec:
    key: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProblemRegistry:
    registry: tuple = ()


def get_problem_registry():
    return ProblemRegistry(registry=(
        ProblemSpec(key="my_problem", params={"penalty": 1.0}),
    ))


_PROBLEM_BUILDERS: Dict[str, Any] = {}

def register_problem_builder(key, builder):
    _PROBLEM_BUILDERS[key] = builder

def build_problem(registry, key):
    spec = next(s for s in registry.registry if s.key == key)
    return _PROBLEM_BUILDERS[key](spec.params)

# --- builtin registration ---
def _register():
    from problem.my_problem import MyProblem
    register_problem_builder("my_problem", lambda p: MyProblem(**p))
_register()
```

### 1.2 Pipeline 配置

Pipeline 是统一管线入口：encode/decode/init/mutate/repair + data。

```python
from nsgablack.representation import RepresentationPipeline, UniformInitializer, GaussianMutation, ClipRepair

def build_my_pipeline(low=-5.0, high=5.0, sigma=0.25):
    return RepresentationPipeline(
        initializer=UniformInitializer(low=low, high=high),
        mutator=GaussianMutation(sigma=sigma, low=low, high=high),
        repair=ClipRepair(low=low, high=high),
    )
```

### 1.3 Adapter 配置

```python
from nsgablack.adapters import NSGA2Adapter, RandomSearchAdapter


def get_adapter_registry():
    return {
        "nsga2": lambda: NSGA2Adapter(pop_size=50),
        "random": lambda: RandomSearchAdapter(n_points=100),
    }


def build_adapter(registry, key="nsga2"):
    return registry[key]()
```

### 1.4 Plugin 配置

使用统一的 10 钩子超集体系。

```python
from nsgablack.plugins.base import Plugin

class MyTracePlugin(Plugin):
    """Log best objective each generation."""

    def __init__(self, name="my_trace"):
        super().__init__(name=name)

    def on_generation_end(self, generation: int):
        snapshot = self.get_population_snapshot()
        if snapshot is not None and len(snapshot[1]) > 0:
            best_obj = float(snapshot[1].min(axis=0).sum())
            print(f"  Gen {generation}: best={best_obj:.4f}")
```

### 1.5 完整装配

```python
def build_solver():
    from problem.config import get_problem_registry, build_problem
    from pipeline.my_pipeline import build_my_pipeline
    from adapter.config import get_adapter_registry, build_adapter
    from nsgablack.core import ComposableSolver

    problem = build_problem(get_problem_registry(), "my_problem")
    pipeline = build_my_pipeline()
    adapter = build_adapter(get_adapter_registry(), "nsga2")

    solver = ComposableSolver(
        problem=problem,
        representation_pipeline=pipeline,
        adapter=adapter,
    )
    solver.add_plugin(MyTracePlugin())
    return solver
```

---

## 2. 多 Solver 编排

### 2.1 添加多个 case

```powershell
python -m nsgablack project add-case solver_a --type solver
python -m nsgablack project add-case solver_b --type solver
```

每个 case 有自己独立的 `build_solver.py`。

### 2.2 并行编排

`project_config.py`：

```python
STAGES = [
    {
        "name": "stage_parallel",
        "cases": ["solver_a", "solver_b"],
        "policy": "run_all_in_parallel",
    },
]
GROUPS = {"default": {"stages": ["stage_parallel"]}}
```

### 2.3 串行编排（阶段依赖）

```python
STAGES = [
    {
        "name": "stage_1",
        "cases": ["solver_a"],
        "policy": "run_all_in_parallel",
    },
    {
        "name": "stage_2",
        "cases": ["solver_b"],
        "policy": "run_all_in_parallel",
        "dependencies": {
            "solver_b": {
                "artifacts": {"best_solution": "stage_1.solver_a.best_x"}
            }
        },
    },
]
GROUPS = {"default": {"stages": ["stage_1", "stage_2"]}}
```

下游 solver 通过 `SnapshotStore` 读取上游 artifact。顶层 `run_project.py` 管理 artifact 在 stage 间的传递。

### 2.4 从项目根运行

```powershell
python run_project.py                    # 按 default group 运行
python run_project.py --group my_group  # 按指定 group 运行
```

---

## 3. 多 Trainer 编排

Trainer 就是 Solver，编排操作完全一样：

```powershell
python -m nsgablack project add-case trainer_a --type trainer
python -m nsgablack project add-case trainer_b --type trainer
```

```python
STAGES = [
    {
        "name": "train_all",
        "cases": ["trainer_a", "trainer_b"],  # solver 和 trainer 并列
        "policy": "run_all_in_parallel",
    },
]
```

编排层不区分 solver 和 trainer。外层只看到 `build_solver()` 接口。

---

## 4. 编排入口总览

```text
project_config.py          ← 声明 STAGES / GROUPS
     │
run_project.py             ← 执行引擎
     │
     ├─ 读取配置
     ├─ 发现 cases/*/build_solver.py
     ├─ 按 stage 顺序执行
     │   ├─ policy: run_all_in_parallel → 并行
     │   └─ dependencies → 传递 artifact
     └─ solver + trainer 同等待遇
```

## 5. 验证清单

- [ ] 每个 case 独立：`cd cases/<name> && python run_solver.py --check`
- [ ] `project_config.py` 的 `case_name` 与目录名一致
- [ ] `python run_project.py` 按预期顺序执行
- [ ] Artifact 依赖路径格式：`stage_name.case_name.key`
