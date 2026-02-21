# -*- coding: utf-8 -*-
"""问题模板：复制后改文件名和类名即可开始建模。"""

from __future__ import annotations

import numpy as np

from nsgablack.core.base import BlackBoxProblem


class ProblemTemplate(BlackBoxProblem):
    """最小可运行的问题模板。"""

    def __init__(self, dimension: int = 8) -> None:
        # 变量边界：这里默认每个维度都在 [-5, 5]
        bounds = {f"x{i}": [-5.0, 5.0] for i in range(dimension)}
        super().__init__(
            name="ProblemTemplate",
            dimension=dimension,
            bounds=bounds,
            objectives=["obj_0", "obj_1"],
        )

    def evaluate(self, x: np.ndarray) -> np.ndarray:
        # 目标函数示例：f1=平方和，f2=绝对值和
        arr = np.asarray(x, dtype=float).reshape(-1)
        obj_0 = float(np.sum(arr ** 2))
        obj_1 = float(np.sum(np.abs(arr)))
        return np.array([obj_0, obj_1], dtype=float)

    def evaluate_constraints(self, x: np.ndarray) -> np.ndarray:
        # 约束示例：默认无硬约束，返回空向量
        _ = x
        return np.zeros(0, dtype=float)
