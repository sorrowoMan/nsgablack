"""逐笔供料事件的稀疏初始化与局部变化；不评价产量、不替代问题修复。"""

from __future__ import annotations

import math

import numpy as np

from nsgablack.representation.base import RepresentationComponentContract


def _event_geometry(problem):
    """Read the Problem-owned event order, today boundary and movement cap."""
    limits = np.asarray([event.day - 1 for event in problem.events], dtype=np.int64)
    eligible = np.flatnonzero(limits > 0)
    cap = len(eligible) if problem.max_moved_events is None else min(
        len(eligible), int(problem.max_moved_events)
    )
    return limits, eligible, cap


class _SeededEventOperator(RepresentationComponentContract):
    context_requires = context_optional = context_provides = context_mutates = context_cache = ()

    def set_random_seed(self, seed):
        self._rng = np.random.default_rng(seed)


class SupplyEventInitializer(_SeededEventOperator):
    """先选移动笔数和事件，再为每笔独立抽合法非零提前天数。"""

    policy = "supply_event_initializer/sparse-uniform-v1"

    def __init__(self, *, seed=None):
        self.set_random_seed(seed)

    def initialize(self, problem, context=None):
        limits, eligible, cap = _event_geometry(problem)
        candidate = np.zeros(len(limits), dtype=float)
        count = int(self._rng.integers(cap + 1))
        if count:
            selected = self._rng.choice(eligible, size=count, replace=False)
            candidate[selected] = self._rng.integers(1, limits[selected] + 1)
        return candidate


class SupplyEventMutation(_SeededEventOperator):
    """一次局部改期／新增／删除／交换，不给所有零坐标叠加噪声。

    已合法的父方案保持合法；交叉产生的浮点或超容量草稿仍由正式
    SupplyShiftRepair 处理。这里不隐式修复未选中的其它坐标。
    """

    policy = "supply_event_mutation/membership-and-date-v1"

    def __init__(self, problem, *, local_step_days=1, full_range_probability=.5, seed=None):
        if type(local_step_days) is not int or local_step_days < 1:
            raise ValueError("local_step_days must be a positive integer")
        if not math.isfinite(full_range_probability) or not 0 <= full_range_probability <= 1:
            raise ValueError("full_range_probability must be in [0, 1]")
        self.problem = problem
        self.local_step_days = local_step_days
        self.full_range_probability = float(full_range_probability)
        self.set_random_seed(seed)

    def _different_day(self, previous, maximum):
        if self._rng.random() < self.full_range_probability:
            if previous == int(previous) and 1 <= previous <= maximum:
                day = int(self._rng.integers(1, maximum))
                return day + int(day >= previous)
            return int(self._rng.integers(1, maximum + 1))
        lower = max(1, int(math.floor(previous)) - self.local_step_days)
        upper = min(maximum, int(math.ceil(previous)) + self.local_step_days)
        options = [day for day in range(lower, upper + 1) if day != previous]
        if options:
            return int(self._rng.choice(options))
        # An out-of-range crossover draft can have no local integer neighbor.
        return int(self._rng.integers(1, maximum + 1))

    def mutate(self, candidate, context=None):
        limits, eligible, cap = _event_geometry(self.problem)
        output = np.array(candidate, dtype=float, copy=True)
        if output.shape != limits.shape or not np.all(np.isfinite(output)):
            raise ValueError("supply mutation requires one finite event vector")
        active = eligible[output[eligible] > 0]
        inactive = eligible[output[eligible] <= 0]
        changeable = active[(limits[active] > 1) | (output[active] != 1)]
        actions = []
        if len(changeable):
            actions.append("change_day")
        if len(active) < cap and len(inactive):
            actions.append("add")
        if len(active):
            actions.append("remove")
        if len(active) and len(inactive):
            actions.append("swap")
        if not actions:
            return output
        action = str(self._rng.choice(actions))
        if action == "change_day":
            index = int(self._rng.choice(changeable))
            output[index] = self._different_day(output[index], int(limits[index]))
        elif action == "add":
            index = int(self._rng.choice(inactive))
            output[index] = int(self._rng.integers(1, int(limits[index]) + 1))
        elif action == "remove":
            output[int(self._rng.choice(active))] = 0
        else:
            source, target = int(self._rng.choice(active)), int(self._rng.choice(inactive))
            output[source] = 0
            output[target] = int(self._rng.integers(1, int(limits[target]) + 1))
        return output


__all__ = ["SupplyEventInitializer", "SupplyEventMutation"]
