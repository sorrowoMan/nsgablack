# 07. 嵌套编排标准规范

**嵌套编排的本质**：外层 Solver 的 `Problem.evaluate()` 短路调用内层 `build_solver()`。两层都是完整的标准脚手架，层间只传递 JSON-compatible 数据和 ResourceContext。

---

## 1. 创建嵌套项目

```powershell
python -m nsgablack project new nested_hyperopt
cd nested_hyperopt
python -m nsgablack project add-case outer_search --type solver
python -m nsgablack project add-case inner_trainer --type trainer
```

生成的三层结构：

```text
nested_hyperopt/
  project_config.py          ← 编排：外层运行后触发内层
  run_project.py             ← 【正式入口 — 从这里启动！】
  cases/
    outer_search/            ← 外层 nsgablack Solver
      build_solver.py
      problem/               ← hyperopt_problem.py（evaluate 中调用内层）
      pipeline/              ← 超参向量 encode/decode
      adapter/               ← NSGA2 / RandomSearch
    inner_trainer/           ← 内层 mlblack Trainer
      build_solver.py        ← canonical 入口（build_trainer.py 别名可用）
      problem/               ← training_problem.py
      pipeline/              ← data + model encode/decode
      adapter/               ← GradientDescent
```

> **关键**：内外层结构完全一致。`outer_search` 是 solver，`inner_trainer` 是 trainer——但在目录形态上没有任何区别。

---

## 2. 内层先行：独立开发并验证

先让内层能独立跑通，不与外层耦合。

### 2.1 内层 build_solver()

`cases/inner_trainer/build_solver.py`：

```python
"""Inner trainer — independently runnable."""
import numpy as np
from mlblack.core.trainer import ComposableTrainer
from mlblack.adapters.gradient_descent import GradientDescentAdapter
from problem.training_problem import RegressionProblem
from pipeline.model_rep import MLPRepresentation


def build_solver(
    hyperparams: dict | None = None,
    data: tuple | None = None,
    resource_context: dict | None = None,
    budget: int = 100,
):
    """Canonical entry. Called by outer solver or standalone."""
    hp = hyperparams or {}
    lr = hp.get("learning_rate", 0.01)
    hidden = hp.get("hidden_dim", 64)
    n_layers = hp.get("num_layers", 2)

    # Default synthetic data if standalone
    if data is None:
        X = np.random.randn(200, 10)
        y = np.random.randn(200)
        data = (X, y)

    problem = RegressionProblem(data)
    representation = MLPRepresentation(
        input_dim=data[0].shape[1],
        hidden_dims=[hidden] * n_layers,
    )
    adapter = GradientDescentAdapter(learning_rate=lr)

    trainer = ComposableTrainer(
        problem=problem,
        representation=representation,
        adapter=adapter,
        run_name="inner_trainer",
    )

    if resource_context:
        trainer.set_resource_context(resource_context)

    trainer.set_max_steps(budget)
    return trainer
```

### 2.2 独立验证内层

```powershell
cd cases/inner_trainer
python run_solver.py --check
# → [check] assembly ok | problem=RegressionProblem | ...
python run_solver.py
# → 训练完成，输出 best_score
```

内层完全自包含，不需要外层就能跑。这保证嵌套时问题一定出在外层的短路调用，而非内层自身。

---

## 3. 外层：Problem.evaluate() 短路调用内层

### 3.1 外层 Problem

`cases/outer_search/problem/hyperopt_problem.py`：

```python
"""Outer problem: optimize hyperparams by calling inner trainer."""
import sys
import os
import numpy as np

# Bootstrap path so inner case is importable
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT = os.path.dirname(os.path.dirname(_HERE))
if _PROJECT not in sys.path:
    sys.path.insert(0, _PROJECT)

from cases.inner_trainer.build_solver import build_solver as build_inner


class HyperoptProblem:
    """Search hyperparams to minimize validation loss."""
    name = "hyperopt"
    dimension = 3
    objectives = ("val_loss",)

    def __init__(self, data_path=None, inner_budget=50):
        # Shared data loaded once
        self.X, self.y = self._load_data(data_path)
        self.inner_budget = inner_budget

    def _load_data(self, path):
        X = np.random.randn(200, 10)
        y = np.random.randn(200)
        return X, y

    def evaluate(self, x):
        """Decode hyperparams, run inner trainer, return val_loss."""
        x = np.asarray(x, dtype=float).ravel()
        hyperparams = self._decode(x)

        try:
            trainer = build_inner(
                hyperparams=hyperparams,
                data=(self.X, self.y),
                budget=self.inner_budget,
            )
            result = trainer.fit(max_steps=self.inner_budget)
            val_loss = float(result.best_score or 1e10)
            return np.array([val_loss], dtype=float)
        except Exception:
            return np.array([1e10], dtype=float)  # penalty for failed eval

    def evaluate_constraints(self, x):
        return np.zeros(0, dtype=float)

    @staticmethod
    def _decode(x):
        return {
            "learning_rate": 10 ** float(x[0]),  # x[0] ∈ [-5, -1]
            "hidden_dim": int(np.clip(x[1], 16, 256)),
            "num_layers": int(np.clip(x[2], 1, 5)),
        }
```

### 3.2 外层 build_solver()

`cases/outer_search/build_solver.py`：

```python
"""Outer solver — searches hyperparams via NSGA2."""
import numpy as np
from nsgablack.core import ComposableSolver
from nsgablack.adapters import NSGA2Adapter
from nsgablack.representation import RepresentationPipeline, UniformInitializer, GaussianMutation, ClipRepair
from problem.hyperopt_problem import HyperoptProblem


def build_solver():
    problem = HyperoptProblem(inner_budget=30)

    # Encode: [log10(lr), hidden_dim, n_layers] as float vector
    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(
            low=np.array([-5.0, 16.0, 1.0]),
            high=np.array([-1.0, 256.0, 5.0]),
        ),
        mutator=GaussianMutation(sigma=0.15),
        repair=ClipRepair(
            low=np.array([-5.0, 16.0, 1.0]),
            high=np.array([-1.0, 256.0, 5.0]),
        ),
    )

    adapter = NSGA2Adapter(pop_size=20)

    solver = ComposableSolver(
        problem=problem,
        representation_pipeline=pipeline,
        adapter=adapter,
    )
    solver.set_max_generations(10)
    return solver
```

---

## 4. 项目编排配置

`project_config.py`：

```python
STAGES = [
    {
        "name": "hyperopt",
        "cases": ["outer_search"],
        "policy": "run_all_in_parallel",
    },
]
GROUPS = {"default": {"stages": ["hyperopt"]}}
```

> 内层 `inner_trainer` 不直接出现在 STAGES 中——它被外层 `Problem.evaluate()` 隐式调用。如果内层也需要独立运行（比如数据预处理阶段），可以加一个前置 stage。

---

## 5. 运行

```powershell
# 从项目根启动！（不是 case 目录）
python run_project.py
```

执行流：

```text
run_project.py
  → 发现 outer_search
  → build_solver() → ComposableSolver
  → solver.run()
    → adapter.propose() 产出超参候选
    → problem.evaluate(x)
        → build_inner(hyperparams=...)
        → trainer.fit(max_steps=30)
        → 返回 val_loss
    → adapter.update(feedback)
    → ...循环直到 max_generations
```

## 6. ResourceContext 传递

外层通过 `ResourceContext` 向内层授权资源：

```python
# 在 outer/problem/hyperopt_problem.py 的 evaluate() 中：
resource_ctx = getattr(self, "resource_context", None)
trainer = build_inner(
    hyperparams=hyperparams,
    data=(self.X, self.y),
    budget=self.inner_budget,
    resource_context=resource_ctx,
)
```

内层消费：

```python
# 在 inner/build_solver.py 中：
if resource_context:
    trainer.set_resource_context(resource_context)
```

优先级：外层 ResourceLease > 注入的 ResourceContext > 内层默认值。

---

## 7. 多内层场景

一个外层同时调用多个内层：

```python
class EnsembleHyperoptProblem:
    def evaluate(self, x):
        hyperparams = self._decode(x)
        losses = []
        for model_type in ("mlp", "tree", "symbolic"):
            trainer = build_inner(model_type=model_type, hyperparams=hyperparams)
            result = trainer.fit()
            losses.append(float(result.best_score or 1e10))
        return np.array([np.mean(losses)], dtype=float)
```

内层可以是任意类型：mlblack Trainer、另一个 nsgablack Solver、甚至第三方系统。只要它有一个 `build_solver()` 入口。

---

## 8. 检查清单

- [ ] 内层独立可运行：`cd cases/inner_trainer && python run_solver.py --check`
- [ ] 外层独立可运行：`cd cases/outer_search && python run_solver.py --check`
- [ ] 内层和外层的 import 不相互依赖
- [ ] 外层 Problem.evaluate() 中调用的 `build_inner()` 路径正确
- [ ] ResourceContext 从外层显式传入内层
- [ ] 从项目根 `python run_project.py` 启动成功

## 9. 常见错误

| 现象 | 原因 | 修复 |
|---|---|---|
| `ImportError: cases.inner_trainer` | sys.path 没加项目根 | 在 outer problem 开头执行 path bootstrap |
| 内层跑很慢，外层评估卡住 | inner_budget 太大 | 减小 budget，加入 early stopping |
| 内层失败但外层不报错 | evaluate() 吞掉了异常 | 至少打印异常信息，或返回 penalty value |
| ResourceContext 在内层不生效 | 外层没传 | 在 evaluate() 中显式传递 resource_context |
