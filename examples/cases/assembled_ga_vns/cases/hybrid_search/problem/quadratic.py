"""二维盒约束问题；原始目标与算法、偏好无关。"""
from __future__ import annotations

import numpy as np

from nsgablack.core import BlackBoxProblem
from nsgablack.units.contracts import candidate_array


class QuadraticProblem(BlackBoxProblem):
    """已知最优点 (2, -1)，原始最优目标为 0。"""

    optimum = (2.0, -1.0)

    def __init__(self):
        super().__init__(
            name="带盒约束的二维二次函数",
            dimension=2,
            objectives=["minimize"],
            bounds={"x0": (-4.0, 4.0), "x1": (-4.0, 4.0)},
        )

    def evaluate(self, candidate):
        x = candidate_array(candidate)
        return float((x[0] - 2.0) ** 2 + (x[1] + 1.0) ** 2)

    def evaluate_constraints(self, candidate):
        # 显式记录原始违反量；ProblemRepair 不替代可行性含义。
        x = np.asarray(candidate, dtype=float)
        return np.maximum(-4.0 - x, 0.0) + np.maximum(x - 4.0, 0.0)
