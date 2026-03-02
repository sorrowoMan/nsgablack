# Case B（TSP）- Adapter 逐行批注

下面给一份 TSP 可直接用的 adapter 结构（过程控制在 adapter，非 bias）。

```python
from nsgablack.core.adapters.algorithm_adapter import AlgorithmAdapter  # adapter 基类
import numpy as np  # 数值工具


class TSP2OptAdapter(AlgorithmAdapter):  # 2-opt 局部搜索适配器
    name = "tsp_2opt_adapter"  # 组件名

    context_requires = ("population_ref", "objectives_ref")  # 依赖快照引用
    context_provides = ("edge_archive",)  # 提供边档案给 bias/plugin 用
    context_mutates = ("edge_archive",)  # 更新边档案
    context_cache = ()  # 不缓存
    context_notes = ("Apply 2-opt style local improvement from current best route.",)  # 说明

    def __init__(self, n_candidates: int = 16):  # 每步候选数
        super().__init__(name=self.name)  # 父类初始化
        self.n_candidates = max(2, int(n_candidates))  # 候选下限
        self._edge_archive = []  # 内部边档案

    def propose(self, solver, context):  # 生成候选
        key = context.get("population_ref") or context.get("snapshot_key")  # 取快照 key
        data = solver.read_snapshot(key) or {}  # 快照数据
        pop = np.asarray(data.get("population", []), dtype=int)  # 当前种群
        objs = np.asarray(data.get("objectives", []), dtype=float)  # 当前目标
        if pop.ndim == 1:
            pop = pop.reshape(1, -1) if pop.size > 0 else pop.reshape(0, 0)
        if objs.ndim == 1:
            objs = objs.reshape(-1, 1) if objs.size > 0 else objs.reshape(0, 0)
        if pop.size == 0 or objs.size == 0:
            return []
        best_idx = int(np.argmin(objs[:, 0]))  # 选当前最优个体
        best = pop[best_idx].copy()  # 最优路径
        rng = self.create_local_rng(solver)  # 局部 RNG
        out = []  # 候选列表
        n = best.size  # 城市数
        for _ in range(self.n_candidates):  # 生成多条候选
            i, j = sorted(rng.choice(n, size=2, replace=False).tolist())  # 随机选两点
            cand = best.copy()  # 从 best 复制
            cand[i:j] = cand[i:j][::-1]  # 2-opt 反转片段
            out.append(cand)  # 追加候选
        return out  # 返回候选列表

    def update(self, solver, context):  # 更新阶段
        _ = solver  # 当前示例不直接读 solver
        key = context.get("population_ref") or context.get("snapshot_key")  # 取快照 key
        data = solver.read_snapshot(key) or {}  # 快照数据
        pop = np.asarray(data.get("population", []), dtype=int)  # 最新种群
        objs = np.asarray(data.get("objectives", []), dtype=float)  # 最新目标
        if pop.ndim == 1:
            pop = pop.reshape(1, -1) if pop.size > 0 else pop.reshape(0, 0)
        if objs.ndim == 1:
            objs = objs.reshape(-1, 1) if objs.size > 0 else objs.reshape(0, 0)
        if pop.size == 0 or objs.size == 0:
            return {"edge_archive": list(self._edge_archive)}
        best_idx = int(np.argmin(objs[:, 0]))  # 找最优
        route = pop[best_idx]  # 最优路径
        edges = {(int(route[i]), int(route[(i + 1) % route.size])) for i in range(route.size)}  # 边集合
        self._edge_archive.append(edges)  # 存档
        self._edge_archive = self._edge_archive[-50:]  # 保留最近 50 条，防止无限增长
        return {"edge_archive": list(self._edge_archive)}  # 回写到 context
```

## 重点
- 2-opt 的“过程逻辑”在 adapter 中最自然。
- adapter 输出 `edge_archive` 后，bias/plugin 可以直接复用，形成联动闭环。
- 种群/目标通过 `population_ref/objectives_ref` 走快照读取，避免大对象进 context。
