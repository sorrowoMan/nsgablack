# 09. 自定义 Adapter（nsgablack 详细实战）

本章目标：从空 Case 出发，写一个最小可运行的自定义 Adapter，并能通过 `--check` + doctor。

## 0. 先明确 Adapter 边界

Adapter 负责“搜索策略语义”，核心只有两件事：

1. `propose(...)` 生成候选
2. `update(...)` 消费反馈并更新内部状态

Adapter 不负责：

- 全局编排（Project substrate 负责）
- 全局资源发放（Project L0 负责）
- 运行能力（Plugin 负责）

---

## 1. 创建 case 与 adapter 文件

```powershell
python -m nsgablack project new demo_adapter_nsga
cd demo_adapter_nsga
python -m nsgablack project add-case my_solver --type solver --framework nsgablack
python -m nsgablack project add-component --case my_solver --kind adapter --name my_adapter
```

生成文件：

```text
cases/my_solver/adapter/my_adapter.py
```

---

## 2. 写最小可运行 Adapter

下面是可运行骨架（重点是接口形状和状态结构）：

```python
from __future__ import annotations

import numpy as np


class MyAdapter:
    def __init__(self, population_size: int = 16, sigma: float = 0.1, seed: int = 42):
        self.population_size = int(population_size)
        self.sigma = float(sigma)
        self.rng = np.random.default_rng(int(seed))
        self._population = None
        self._objectives = None
        self._violations = None

    def propose(self, control, context):
        # 首次：从 control.problem.dimension 构造初始群体
        if self._population is None:
            dim = int(getattr(control.problem, "dimension", 8))
            self._population = self.rng.normal(0.0, 1.0, size=(self.population_size, dim))
            return self._population

        # 后续：围绕当前群体做高斯扰动
        noise = self.rng.normal(0.0, self.sigma, size=self._population.shape)
        return self._population + noise

    def update(self, control, candidates, feedback, context):
        objectives, violations = feedback
        # 最小策略：保留本代候选并记录反馈
        self._population = np.asarray(candidates, dtype=float)
        self._objectives = np.asarray(objectives, dtype=float)
        self._violations = np.asarray(violations, dtype=float).reshape(-1)

    # --- 推荐实现：checkpoint 友好 ---
    def get_state(self):
        return {
            "population": None if self._population is None else self._population.tolist(),
            "objectives": None if self._objectives is None else self._objectives.tolist(),
            "violations": None if self._violations is None else self._violations.tolist(),
            "sigma": self.sigma,
        }

    def set_state(self, state):
        payload = dict(state or {})
        self.sigma = float(payload.get("sigma", self.sigma))
        pop = payload.get("population")
        obj = payload.get("objectives")
        vio = payload.get("violations")
        self._population = None if pop is None else np.asarray(pop, dtype=float)
        self._objectives = None if obj is None else np.asarray(obj, dtype=float)
        self._violations = None if vio is None else np.asarray(vio, dtype=float).reshape(-1)
```

---

## 3. 在 `build_solver.py` 挂载 Adapter

核心是：

```python
solver = ...
solver.set_adapter(MyAdapter(...))
```

示意（你自己的 `build_solver.py` 按本 Case 风格写）：

```python
from .adapter.my_adapter import MyAdapter

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    del config, resource_context, component_overrides
    solver = make_solver_somehow()
    solver.set_adapter(MyAdapter(population_size=24, sigma=0.05))
    return solver
```

---

## 4. 三种常见 Adapter 进阶形态

### 4.1 单策略（最稳）

- 一个 propose
- 一个 update
- 适合基线与回归测试

### 4.2 多策略 router（阶段切换）

结合 context key：

```text
phase=explore -> 大步长策略
phase=exploit -> 小步长策略
```

### 4.3 多策略并行（候选融合）

- 多个策略分别 propose
- 合并后统一 evaluate/update
- 注意返回 shape 与追踪来源字段

---

## 5. 验证步骤（必须跑）

```powershell
python run_project.py --check --build-check
python -m nsgablack project doctor --path . --build --strict --format problem
```

建议额外做一次短跑（小迭代）确保 propose/update 真执行。

---

## 6. 常见坑

1. `propose` 返回 list of object / shape 不稳  
   修复：统一返回 `np.ndarray` 或 solver 可消费的固定结构。

2. `update` 不记录 population，下一代 propose 无法延续  
   修复：保存 `_population`。

3. 在 adapter 里直接写大对象进 context  
   修复：大对象走 snapshot/ref；context 只留轻量字段。

4. adapter 里偷偷做资源申请  
   修复：只消费 `resource_context`，不申请全局资源。
