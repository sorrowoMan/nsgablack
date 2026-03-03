# Adapter 组件（逐行批注版）

目标：写“完整算法过程控制”组件（propose + update）。

---

## 文件位置
`adapter/my_adapter.py`

## 直接可复制模板（每行解释）
```python
from __future__ import annotations  # 现代注解

import numpy as np  # 数值计算

from nsgablack.adapters.algorithm_adapter import AlgorithmAdapter  # 适配器基类
from nsgablack.utils.context.context_keys import (  # 统一 context key
    KEY_POPULATION,
    KEY_OBJECTIVES,
    KEY_GENERATION,
    KEY_BEST_X,
    KEY_BEST_OBJECTIVE,
)


class MySearchAdapter(AlgorithmAdapter):  # 你的算法入口适配器
    name = "my_search_adapter"  # 组件名称

    context_requires = (KEY_POPULATION, KEY_OBJECTIVES, KEY_GENERATION)  # 声明依赖字段
    context_provides = (KEY_BEST_X, KEY_BEST_OBJECTIVE)  # 声明产出字段
    context_mutates = ()  # 不直接修改共享字段
    context_cache = ()  # 不写缓存
    context_notes = ("Local search around current best with context output.",)  # 说明

    def __init__(self, step_sigma: float = 0.1):  # 参数
        super().__init__()  # 父类初始化
        self.step_sigma = float(step_sigma)  # 步长
        self._last_best_x = None  # 内部状态：最近最佳解
        self._last_best_obj = None  # 内部状态：最近最佳目标

    def propose(self, solver, context):  # 核心1：给出新候选
        _ = solver  # 当前 propose 示例不直接读 solver
        pop = np.asarray(context[KEY_POPULATION], dtype=float)  # 当前种群
        objs = np.asarray(context[KEY_OBJECTIVES], dtype=float)  # 当前目标
        if pop.size == 0:  # 防御空种群
            raise ValueError("population is empty")  # 明确报错
        best_idx = int(np.argmin(objs[:, 0]))  # 示例：按第一个目标找最好
        center = pop[best_idx]  # 作为局部搜索中心
        self._last_best_x = center.copy()  # 存一份
        self._last_best_obj = float(objs[best_idx, 0])  # 存一份
        rng = np.random.default_rng()  # 局部 RNG
        candidate = center + rng.normal(0.0, self.step_sigma, size=center.shape)  # 局部扰动
        return candidate  # 返回候选解

    def update(self, solver, context):  # 核心2：根据评估结果更新并回写 context
        _ = context  # 当前示例用 solver projection 就够
        projection = solver.get_runtime_context_projection() or {}  # 当前运行态快照
        current_best = projection.get(KEY_BEST_OBJECTIVE, None)  # 框架当前 best
        merged_best = self._last_best_obj if current_best is None else min(float(current_best), float(self._last_best_obj))  # 合并 best
        return {  # 返回 context 增量，由框架统一合并
            KEY_BEST_X: self._last_best_x,  # 输出 best_x
            KEY_BEST_OBJECTIVE: merged_best,  # 输出 best_objective
        }
```

---

## build_solver 接线
```python
from adapter.my_adapter import MySearchAdapter  # 导入 adapter

solver.set_adapter(MySearchAdapter(step_sigma=0.1))  # 设置主 adapter
```

---

## 最关键边界
- adapter：完整过程（候选生成、状态推进、策略更新）
- bias：只给偏好信号，不做流程
- pipeline：只管“解怎么生成/变异/修复”

---

## 最容易犯错
- 在 adapter 里直接改 `solver.population`（不推荐）
- 契约写了依赖字段，但代码里没读/读错 key
- 使用全局 `np.random.seed()` 导致组件间随机性互相污染
