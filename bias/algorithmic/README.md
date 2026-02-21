# bias/algorithmic

用途：仅保留“标量偏好型”算法偏置（探索/收敛/多样性/信号驱动）。
边界：不放完整搜索流程，不放种群级选择淘汰机制。
迁移：NSGA/NSGA-III/SPEA2/DE/Pattern/GD 已迁到 `core/adapters/*`（适配器侧）。
MOEA-D 与 SA 使用现有主适配器实现（`core/adapters/moead.py`、`core/adapters/simulated_annealing.py`）。

Purpose: scalar preference biases only (exploration, convergence, diversity, signal-driven).
Boundary: no full search loop / no population-level selection mechanism here.
Moved: NSGA/NSGA-III/SPEA2/DE/Pattern/GD now live under `core/adapters/*` (adapter side).
MOEA-D and SA use the existing main adapters (`core/adapters/moead.py`, `core/adapters/simulated_annealing.py`).
