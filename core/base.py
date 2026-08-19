"""Black-box problem base class for nsgablack.

Inherits the unified ProblemBase from blackbase and adds nsgablack-specific
features (bounds, constraints, evaluation counting, multi-objective support).
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Dict, Optional, Sequence

import numpy as np

from blackbase.abc import ProblemBase


class BlackBoxProblem(ProblemBase):
    """黑箱问题基类

    约定：
    - ``evaluate(candidate)`` 返回目标值（标量或 ndarray）
    - ``evaluate_constraints(candidate)`` 返回约束违背度数组 g(candidate) >= 0
      （<=0 视为满足约束，>0 为违反约束的程度）。
    """

    def __init__(self, name="黑箱问题", dimension=2, bounds=None, objectives=None):
        self.name = name
        self.dimension = dimension
        self.evaluation_count = 0
        self.variables = [f'x{i}' for i in range(dimension)]
        self.objectives = list(objectives) if objectives is not None else None
        if bounds is None:
            self.bounds = {var: [-5, 5] for var in self.variables}
        else:
            self.bounds = bounds

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        # 自动为子类 evaluate 增加计数器（不要求子类改动）。
        orig = cls.__dict__.get("evaluate")
        if orig is None:
            return
        if getattr(orig, "__nsgablack_evaluation_wrapped__", False):
            return

        @wraps(orig)
        def _wrapped_evaluate(self, candidate, *args, **kwargs):
            try:
                self.evaluation_count += 1
            except Exception:
                # 保底：不让计数器影响评估流程
                pass
            return orig(self, candidate, *args, **kwargs)

        _wrapped_evaluate.__nsgablack_evaluation_wrapped__ = True
        setattr(cls, "evaluate", _wrapped_evaluate)

    def evaluate(self, candidate, context=None):
        raise NotImplementedError("子类必须实现evaluate方法")

    # ---- 约束相关统一接口 ----
    def evaluate_constraints(self, candidate):
        """返回约束违背度数组。

        约定：g(candidate) <= 0 表示满足约束，g(candidate) > 0 表示违反约束的程度。
        默认无约束，返回全零；子类可按需重写。
        支持单点 (d,) 或批量 (n,d) 输入。
        """
        if hasattr(candidate, "shape") and len(candidate.shape) > 1:
            # 批量输入：返回 (n, 0) 形状，方便后续 sum(axis=1)
            n = candidate.shape[0]
            return np.zeros((n, 0), dtype=float)
        # 单点：返回长度 0 的一维向量
        return np.zeros(0, dtype=float)

    def is_valid(self, candidate):
        """Check bounds and constraints for a candidate solution."""
        arr = np.asarray(candidate, dtype=float)
        if arr.ndim == 0:
            return False
        if arr.ndim > 1:
            return np.array([self.is_valid(row) for row in arr], dtype=bool)

        if arr.shape[0] != self.dimension:
            return False

        bounds = self.bounds
        if isinstance(bounds, dict):
            keys = list(self.variables) if hasattr(self, "variables") else list(bounds.keys())
            try:
                pairs = [bounds[key] for key in keys]
            except KeyError:
                # If user-defined bounds keys do not match default variables (x0..),
                # fall back to bounds insertion order.
                pairs = [bounds[key] for key in list(bounds.keys())]
        else:
            pairs = bounds

        for idx, (low, high) in enumerate(pairs):
            if arr[idx] < low or arr[idx] > high:
                return False

        try:
            cons = self.evaluate_constraints(arr)
            cons_arr = np.asarray(cons, dtype=float).flatten()
            if cons_arr.size > 0 and np.any(cons_arr > 0):
                return False
        except Exception:
            return False

        return True

    def get_num_objectives(self):
        if self.objectives is not None:
            return len(self.objectives)
        return 1

    def is_multiobjective(self):
        return self.get_num_objectives() > 1
