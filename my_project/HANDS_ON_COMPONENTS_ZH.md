# 手把手组件开发（逐行版）

这份文档面向**第一次写 NSGABlack 组件**的同学。  
目标是：你不需要先读完整框架源码，也能把一个组件从 0 写到可运行。

---

## 0. 先理解一件事：组件在框架里的位置

- `problem/`：定义“什么是好解”（目标函数、约束）
- `pipeline/`：定义“解怎么产生、怎么变、怎么修复”
- `bias/`：定义“偏好”（软引导，不是硬约束）
- `adapter/`：定义“搜索流程”（propose/update）
- `plugins/`：定义“工程能力”（日志、缓存、重试、监控等）

一句话：  
**Problem 决定目标，Pipeline 决定可行性，Bias 决定倾向，Adapter 决定搜索机制，Plugin 决定工程体验。**

---

## 1) 写 Problem（逐行）

文件建议：`problem/my_problem.py`

```python
from __future__ import annotations
import numpy as np
from nsgablack.core.base import BlackBoxProblem


class MyProblem(BlackBoxProblem):
    def __init__(self, dimension: int = 8) -> None:
        # 每个变量的上下界：x0..x7 都在 [-5, 5]
        bounds = {f"x{i}": [-5.0, 5.0] for i in range(dimension)}
        super().__init__(
            name="MyProblem",                 # 问题名称（用于日志/结果）
            dimension=dimension,              # 决策变量维度
            bounds=bounds,                    # 变量边界
            objectives=["obj_0", "obj_1"],    # 目标名称（仅标签）
        )

    def evaluate(self, x: np.ndarray) -> np.ndarray:
        # 约定：输入 x，输出 numpy 向量 [f1, f2, ...]
        arr = np.asarray(x, dtype=float).reshape(-1)
        f1 = float(np.sum(arr ** 2))
        f2 = float(np.sum(np.abs(arr)))
        return np.array([f1, f2], dtype=float)

    def evaluate_constraints(self, x: np.ndarray) -> np.ndarray:
        # 约定：返回约束违背向量。无约束时返回空数组。
        _ = x
        return np.zeros(0, dtype=float)
```

这段代码和框架匹配点：

- `BlackBoxSolverNSGAII` 会调用 `problem.evaluate(x)`
- 有约束场景下会读取 `evaluate_constraints(x)`

---

## 2) 写 Pipeline（逐行）

文件建议：`pipeline/my_pipeline.py`

```python
from __future__ import annotations
from nsgablack.representation import (
    RepresentationPipeline,
    UniformInitializer,
    GaussianMutation,
    ClipRepair,
)


def build_pipeline() -> RepresentationPipeline:
    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=-5.0, high=5.0),         # 初始解生成
        mutator=GaussianMutation(sigma=0.25, low=-5.0, high=5.0),   # 变异
        repair=ClipRepair(low=-5.0, high=5.0),                      # 修复到边界
        encoder=None,
    )

    # 契约：这条 pipeline 不读/不写额外 context 字段
    pipeline.context_requires = ()
    pipeline.context_provides = ()
    pipeline.context_mutates = ()
    pipeline.context_cache = ()
    pipeline.context_notes = "Basic continuous pipeline."
    return pipeline
```

和框架匹配点：

- solver 会通过 `set_representation_pipeline(...)` 挂载它
- 在初始化/变异后自动调用 initializer/mutator/repair

---

## 3) 写 Bias（逐行）

文件建议：`bias/my_bias.py`

```python
from __future__ import annotations
import numpy as np
from nsgablack.bias.core.base import BiasBase, OptimizationContext
from nsgablack.bias import BiasModule


class TowardOriginBias(BiasBase):
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Penalize distance to origin as soft preference.",)
    requires_metrics = ()
    metrics_fallback = "none"
    missing_metrics_policy = "warn"

    def __init__(self, weight: float = 0.1) -> None:
        super().__init__("toward_origin", weight=weight, description="Prefer smaller norm")

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        _ = context
        # 偏置值越大通常表示“越不喜欢”，具体看组合策略
        return float(np.linalg.norm(np.asarray(x, dtype=float)))


def build_bias_module(enable_bias: bool = True) -> BiasModule:
    module = BiasModule()
    if enable_bias:
        module.add(TowardOriginBias(weight=0.1))
    module.context_requires = ()
    module.context_provides = ()
    module.context_mutates = ()
    module.context_cache = ()
    module.context_notes = "Bias assembly for demo."
    return module
```

和框架匹配点：

- solver 在评估阶段会调用 bias module
- bias 是“软偏好”，不是硬约束

---

## 4) 写 Plugin（逐行）

文件建议：`plugins/my_plugin.py`

```python
from __future__ import annotations
from typing import Any, Dict
from nsgablack.plugins.base import Plugin
from nsgablack.utils.context.context_keys import KEY_GENERATION

KEY_PROJECT_HIT = "project.my_plugin.hit_count"


class MyPlugin(Plugin):
    context_requires = (KEY_GENERATION,)
    context_provides = (KEY_PROJECT_HIT,)
    context_mutates = (KEY_PROJECT_HIT,)
    context_cache = ()
    context_notes = ("Count generation hits and expose context key.",)

    def __init__(self, interval: int = 5, verbose: bool = True) -> None:
        super().__init__(name="my_plugin")
        self.interval = max(1, int(interval))
        self.verbose = bool(verbose)
        self.hit = 0

    def on_solver_init(self, solver) -> None:
        self.hit = 0

    def on_generation_end(self, generation: int) -> None:
        generation = int(generation)
        if generation % self.interval != 0:
            return None
        self.hit += 1
        if self.verbose:
            print(f"[my_plugin] gen={generation} hit={self.hit}")
        return None

    def on_context_build(self, context: Dict[str, Any]) -> Dict[str, Any]:
        context[KEY_PROJECT_HIT] = int(self.hit)
        return context
```

和框架匹配点：

- `on_generation_end`：每代末调用
- `on_context_build`：context 构建时调用（Inspector 可见）

---

## 5)（可选）写 Adapter（逐行）

文件建议：`adapter/my_adapter.py`

```python
from __future__ import annotations
from typing import Any, Dict, Sequence
import numpy as np
from nsgablack.core.adapters.algorithm_adapter import AlgorithmAdapter


class MyAdapter(AlgorithmAdapter):
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Demo adapter with propose/update.",)

    def __init__(self, n: int = 8) -> None:
        super().__init__(name="my_adapter")
        self.n = max(1, int(n))

    def propose(self, solver: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        _ = context
        rng = self.create_local_rng(solver)
        d = int(getattr(getattr(solver, "problem", None), "dimension", 1))
        return [rng.uniform(-1.0, 1.0, size=(d,)) for _ in range(self.n)]

    def update(
        self,
        solver: Any,
        candidates: Sequence[np.ndarray],
        objectives: np.ndarray,
        violations: np.ndarray,
        context: Dict[str, Any],
    ) -> None:
        _ = (solver, candidates, objectives, violations, context)
        return None
```

---

## 6) 在 `build_solver.py` 装配

```python
from problem.my_problem import MyProblem
from pipeline.my_pipeline import build_pipeline
from bias.my_bias import build_bias_module
from plugins.my_plugin import MyPlugin

problem = MyProblem(dimension=8)
pipeline = build_pipeline()
bias_module = build_bias_module(enable_bias=True)

solver = BlackBoxSolverNSGAII(problem, bias_module=bias_module)
solver.set_representation_pipeline(pipeline)
solver.add_plugin(MyPlugin(interval=5))
```

---

## 7) 最小验证命令（固定三条）

在 `my_project/` 下执行：

```powershell
python build_solver.py
python -m nsgablack project doctor --path . --build
python -m nsgablack run_inspector --entry build_solver.py:build_solver
```

通过标准：

- 能跑完，不报错
- doctor 无 error
- Inspector 里能看到你的组件和 context 字段

---

## 8) 常见错误（最容易踩）

- `evaluate()` 返回 Python list，不是 `np.ndarray`
- `evaluate_constraints()` 返回 `None`（应返回数组）
- 插件类没继承 `Plugin`
- 插件 `context_*` 声明和实际写入不一致
- 写了组件但没在 `build_solver.py` 挂载

---

## 9) 推荐你现在就做的练习

1. 从 `plugins/template_plugin.py` 复制成 `plugins/counter_plugin.py`
2. 把 key 改成 `project.counter.value`
3. 在 `build_solver.py` 接入
4. 跑三条验证命令

做完这一步，你就已经完成“第一个完整自定义组件闭环”。

