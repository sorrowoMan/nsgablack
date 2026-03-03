# 组件开发超细教程（逐行 + 对照框架）

这份文档是给新手的“照抄可跑版”。
目标不是讲概念，而是让你**按步骤写出能运行的组件**。

---

## A. 先定规则（避免一开始就乱）

1. 每次只改一个层：
   - 先 `problem`
   - 再 `pipeline`
   - 再 `bias` / `plugin`
   - 最后（可选）`adapter`
2. 每次改完只跑三条命令：
   - `python build_solver.py`
   - `python -m nsgablack project doctor --path . --build`
   - `python -m nsgablack run_inspector --entry build_solver.py:build_solver`
3. 任何组件都必须写 `context_*` 契约字段（就算是空元组）。

---

## B. Problem：逐行写法（你可以直接复制）

文件：`problem/my_problem.py`

```python
from __future__ import annotations
# 作用：允许现代类型注解语法（兼容运行时解析）

import numpy as np
# 作用：统一数值类型和向量计算

from nsgablack.core.base import BlackBoxProblem
# 作用：框架的问题基类，solver 通过这个协议调用 evaluate/evaluate_constraints


class MyProblem(BlackBoxProblem):
    # 作用：定义“优化目标是什么”

    def __init__(self, dimension: int = 8) -> None:
        # 作用：定义变量维度、边界、目标名称
        bounds = {f"x{i}": [-5.0, 5.0] for i in range(dimension)}
        # 作用：每个决策变量范围；solver/pipeline 会基于这个约束搜索空间

        super().__init__(
            name="MyProblem",                 # 日志里看到的问题名
            dimension=dimension,              # 决策变量维度
            bounds=bounds,                    # 变量边界
            objectives=["obj_0", "obj_1"],    # 目标标签（显示用）
        )

    def evaluate(self, x: np.ndarray) -> np.ndarray:
        # 作用：核心目标函数，必须返回 np.ndarray
        arr = np.asarray(x, dtype=float).reshape(-1)
        # 强制转 float 一维向量，避免后续 shape 错误

        f1 = float(np.sum(arr ** 2))
        f2 = float(np.sum(np.abs(arr)))
        # 你可以替换成自己的业务目标

        return np.array([f1, f2], dtype=float)
        # 注意：这里必须返回“目标向量”

    def evaluate_constraints(self, x: np.ndarray) -> np.ndarray:
        # 作用：硬约束违背向量；无约束时返回空数组
        _ = x
        return np.zeros(0, dtype=float)
```

### 这段代码如何与框架匹配

- `EvolutionSolver.run()` 会反复调用 `problem.evaluate(x)`
- 若定义了约束，会读 `evaluate_constraints(x)`
- Inspector 的问题卡片会显示这个类

---

## C. Pipeline：逐行写法

文件：`pipeline/my_pipeline.py`

```python
from __future__ import annotations

from nsgablack.representation import (
    RepresentationPipeline,  # 管线容器
    UniformInitializer,      # 初始解生成
    GaussianMutation,        # 连续变量变异
    ClipRepair,              # 硬边界修复
)


def build_pipeline() -> RepresentationPipeline:
    # 作用：返回一个完整的“初始化-变异-修复”组合
    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=-5.0, high=5.0),
        mutator=GaussianMutation(sigma=0.25, low=-5.0, high=5.0),
        repair=ClipRepair(low=-5.0, high=5.0),
        encoder=None,
    )

    # 契约声明：这个示例不依赖额外 context 字段
    pipeline.context_requires = ()
    pipeline.context_provides = ()
    pipeline.context_mutates = ()
    pipeline.context_cache = ()
    pipeline.context_notes = "Basic continuous pipeline."
    return pipeline
```

### 匹配点

- `solver.set_representation_pipeline(pipeline)` 后，solver 在生命周期里调用它
- `repair` 负责硬可行性（你之前强调的“硬约束放管线”就是这里）

---

## D. Bias：逐行写法

文件：`bias/my_bias.py`

```python
from __future__ import annotations

import numpy as np

from nsgablack.bias.core.base import BiasBase, OptimizationContext
from nsgablack.bias import BiasModule


class TowardOriginBias(BiasBase):
    # 这5组字段是“契约声明”
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Penalize distance to origin as soft preference.",)

    # metrics 依赖声明（没有就留空）
    requires_metrics = ()
    metrics_fallback = "none"
    missing_metrics_policy = "warn"

    def __init__(self, weight: float = 0.1) -> None:
        super().__init__(
            name="toward_origin",
            weight=weight,
            description="Prefer smaller norm",
        )

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        _ = context
        return float(np.linalg.norm(np.asarray(x, dtype=float)))
        # 返回“偏好值”，由 BiasModule 参与总评分


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

### 匹配点

- `BiasBase.compute` 是偏置的核心入口
- `BiasModule.add(...)` 把偏置挂到求解流程

---

## E. Plugin：逐行写法

文件：`plugins/my_plugin.py`

```python
from __future__ import annotations

from typing import Any, Dict

from nsgablack.plugins.base import Plugin
from nsgablack.utils.context.context_keys import KEY_GENERATION

KEY_PROJECT_HIT = "project.my_plugin.hit_count"
# 自定义字段建议加 project. 前缀，避免污染公共字段


class MyPlugin(Plugin):
    # 契约：这个插件会读 generation，写 project.my_plugin.hit_count
    context_requires = (KEY_GENERATION,)
    context_provides = (KEY_PROJECT_HIT,)
    context_mutates = (KEY_PROJECT_HIT,)
    context_cache = ()
    context_notes = ("Count generation hits and expose context key.",)

    def __init__(self, interval: int = 5, verbose: bool = True) -> None:
        super().__init__(name="my_plugin")
        # name 是插件唯一标识，Inspector/日志里会用到
        self.interval = max(1, int(interval))
        self.verbose = bool(verbose)
        self.hit = 0

    def on_solver_init(self, solver) -> None:
        # 生命周期：一次 run 开始时触发
        _ = solver
        self.hit = 0

    def on_generation_end(self, generation: int) -> None:
        # 生命周期：每代结束时触发
        generation = int(generation)
        if generation % self.interval != 0:
            return None
        self.hit += 1
        if self.verbose:
            print(f"[my_plugin] gen={generation} hit={self.hit}")
        return None

    def on_context_build(self, context: Dict[str, Any]) -> Dict[str, Any]:
        # 生命周期：构建 context 快照时触发（Inspector 可见）
        context[KEY_PROJECT_HIT] = int(self.hit)
        return context
```

### 匹配点

- `PluginManager` 会自动调度这些钩子
- `on_context_build` 写入的 key 能在 Inspector 的 Context 里看到

---

## F. Adapter：逐行写法（进阶）

文件：`adapter/my_adapter.py`

```python
from __future__ import annotations

from typing import Any, Dict, Sequence

import numpy as np

from nsgablack.adapters.algorithm_adapter import AlgorithmAdapter


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
        # propose：产出候选解
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
        # update：消费评估结果并更新内部状态
        _ = (solver, candidates, objectives, violations, context)
        return None
```

---

## G. 装配：`build_solver.py` 必改点

只做装配，不写业务逻辑：

```python
from problem.my_problem import MyProblem
from pipeline.my_pipeline import build_pipeline
from bias.my_bias import build_bias_module
from plugins.my_plugin import MyPlugin

problem = MyProblem(dimension=8)
pipeline = build_pipeline()
bias_module = build_bias_module(enable_bias=True)

solver = EvolutionSolver(problem, bias_module=bias_module)
solver.set_representation_pipeline(pipeline)
solver.add_plugin(MyPlugin(interval=5))
```

---

## H. 注册到 Catalog（推荐）

在 `project_registry.py` 里加 `CatalogEntry`，核心字段最少要有：

- `key / title / kind / import_path / summary`
- `context_requires/provides/mutates/cache/notes`
- `use_when / minimal_wiring / required_companions / config_keys / example_entry`

这样你在 Inspector 的 Catalog 里才能搜到自己的组件。

---

## I. 逐步验收清单（每次改完都走）

### 1) 语法验收

- 文件能 import，不报错

### 2) 运行验收

```powershell
python build_solver.py
```

- 能跑到结束
- 若有插件日志，能看到输出

### 3) 契约验收

```powershell
python -m nsgablack project doctor --path . --build
```

- errors = 0
- warnings 尽量 0

### 4) 可视化验收

```powershell
python -m nsgablack run_inspector --entry build_solver.py:build_solver
```

- Details 能看到组件
- Context 能看到你声明/写入的 key

---

## J. 新手最容易错的 12 件事

1. `evaluate` 返回 list，不是 `np.ndarray`
2. `evaluate_constraints` 返回 `None`
3. 插件没继承 `Plugin`
4. 组件写了但没在 `build_solver.py` 挂载
5. `context_*` 声明和实际写入不一致
6. 自定义 key 不加 `project.` 前缀
7. `import_path` 写错（Catalog 查不到）
8. 在 `build_solver.py` 里写太多业务逻辑（应只装配）
9. 把硬约束写到 bias（应优先在 pipeline repair）
10. 插件用全局随机（应使用本地 RNG 机制）
11. Adapter 没实现 `propose` / 签名不对
12. 改了代码但不跑 doctor 和 inspector

---

## K. 一次完整练习（30 分钟）

你可以按这个顺序做一遍：

1. 复制 `plugins/template_plugin.py` -> `plugins/counter_plugin.py`
2. 改类名为 `CounterPlugin`
3. 改 key 为 `project.counter.value`
4. 在 `build_solver.py` 接入 `solver.add_plugin(CounterPlugin(interval=3))`
5. 跑三条命令（build_solver / doctor / run_inspector）
6. 在 Inspector 确认 key 出现在 Context 页

做完这轮，你就真正掌握组件开发闭环了。
