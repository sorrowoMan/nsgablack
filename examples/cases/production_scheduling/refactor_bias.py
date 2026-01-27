# -*- coding: utf-8 -*-
"""Bias module builder for production scheduling."""

from __future__ import annotations

from typing import Dict, Optional

import sys
from pathlib import Path

import numpy as np

def _ensure_importable() -> None:
    try:
        import nsgablack  # noqa: F401
        return
    except Exception:
        pass
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))


_ensure_importable()

from nsgablack.bias import BiasModule, CallableBias


CONSTRAINT_INDEX = {
    "material_shortage": 0,
    "excess_machines": 1,
    "shortage_machines": 2,
    "below_min_production": 3,
    "above_max_production": 4,
}


def _reshape_schedule(problem, x: np.ndarray) -> np.ndarray:
    return np.asarray(x, dtype=float).reshape(int(problem.machines), int(problem.days))


def _constraints_value(constraints, key: str) -> Optional[float]:
    # `constraints` is a sequence (typically list[float]) from evaluate_constraints_safe(...)
    try:
        idx = int(CONSTRAINT_INDEX[key])
    except Exception:
        return None
    try:
        if constraints is not None and len(constraints) > idx:
            return float(constraints[idx])
    except Exception:
        return None
    return None


class _PenaltyFromConstraints:
    def __init__(self, idx: int, *, key: str):
        self.idx = int(idx)
        self.key = str(key)

    def __call__(self, x, constraints, context_dict):  # noqa: ARG002
        try:
            if constraints is not None and len(constraints) > self.idx:
                return {"penalty": float(constraints[self.idx])}
        except Exception:
            pass
        # If constraints are missing, treat as 0 (do not block the run).
        return {"penalty": 0.0}


class _UtilizationReward:
    def __init__(self, *, machines: int, days: int, max_machines_per_day: int):
        self.machines = int(machines)
        self.days = int(days)
        self.max_machines_per_day = int(max_machines_per_day)

    def __call__(self, x, constraints, context_dict):  # noqa: ARG002
        sched = np.asarray(x, dtype=float).reshape(self.machines, self.days)
        daily_active = np.sum(sched > 0, axis=0)
        target = float(self.max_machines_per_day)
        utilization = float(np.mean(daily_active / max(target, 1.0)))
        return {"reward": utilization}


class _SmoothnessPenalty:
    def __init__(self, *, machines: int, days: int):
        self.machines = int(machines)
        self.days = int(days)

    def __call__(self, x, constraints, context_dict):  # noqa: ARG002
        sched = np.asarray(x, dtype=float).reshape(self.machines, self.days)
        daily_production = np.sum(sched, axis=0)
        if daily_production.size <= 1:
            return {"penalty": 0.0}
        changes = np.abs(np.diff(daily_production))
        penalty = float(np.mean(changes) / (np.mean(daily_production) + 1e-6))
        return {"penalty": penalty}


class _VariancePenalty:
    """
    Penalize day-to-day imbalance using coefficient of variation (std/mean).

    This is usually a stronger "stability" signal than mean absolute diff when
    some days are extremely high/low.
    """

    def __init__(self, *, machines: int, days: int):
        self.machines = int(machines)
        self.days = int(days)

    def __call__(self, x, constraints, context_dict):  # noqa: ARG002
        sched = np.asarray(x, dtype=float).reshape(self.machines, self.days)
        daily_production = np.sum(sched, axis=0)
        mean = float(np.mean(daily_production))
        if not np.isfinite(mean) or mean <= 1e-6:
            return {"penalty": 0.0}
        std = float(np.std(daily_production))
        return {"penalty": std / mean}


class _CoverageReward:
    def __init__(self, *, machines: int, days: int, feasible_mask: np.ndarray):
        self.machines = int(machines)
        self.days = int(days)
        self.feasible_mask = np.asarray(feasible_mask, dtype=bool).reshape(self.machines)

    def __call__(self, x, constraints, context_dict):  # noqa: ARG002
        sched = np.asarray(x, dtype=float).reshape(self.machines, self.days)
        active_any = np.sum(sched, axis=1) > 0
        feasible_count = int(np.sum(self.feasible_mask))
        if feasible_count <= 0:
            return {"reward": 0.0}
        coverage = float(np.sum(active_any & self.feasible_mask)) / float(feasible_count)
        return {"reward": coverage}


def build_production_bias_module(problem, weights: Optional[Dict[str, float]] = None) -> BiasModule:
    module = BiasModule()
    weights = weights or {}

    shortage_weight = weights.get("shortage_penalty", 0.02)
    excess_weight = weights.get("excess_machine_penalty", 0.01)
    utilization_weight = weights.get("utilization_reward", 0.02)
    smooth_weight = weights.get("smoothness_penalty", 0.01)
    variance_weight = weights.get("variance_penalty", 0.0)
    coverage_weight = weights.get("coverage_reward", 0.02)

    material_total = np.sum(problem.data.supply_matrix, axis=1)
    feasible_mask = np.zeros(int(problem.machines), dtype=bool)
    for m in range(int(problem.machines)):
        req = np.where(problem.data.bom_matrix[m])[0]
        if req.size == 0:
            feasible_mask[m] = True
            continue
        feasible_mask[m] = np.min(material_total[req]) > 0

    if shortage_weight > 0:
        module.add(
            CallableBias(
                name="material_shortage",
                func=_PenaltyFromConstraints(CONSTRAINT_INDEX["material_shortage"], key="material_shortage"),
                weight=float(shortage_weight),
                mode="penalty",
            )
        )
    if excess_weight > 0:
        module.add(
            CallableBias(
                name="excess_machines",
                func=_PenaltyFromConstraints(CONSTRAINT_INDEX["excess_machines"], key="excess_machines"),
                weight=float(excess_weight),
                mode="penalty",
            )
        )
    if utilization_weight > 0:
        module.add(
            CallableBias(
                name="utilization_reward",
                func=_UtilizationReward(
                    machines=int(problem.machines),
                    days=int(problem.days),
                    max_machines_per_day=int(problem.constraints.max_machines_per_day),
                ),
                weight=float(utilization_weight),
                mode="reward",
            )
        )
    if smooth_weight > 0:
        module.add(
            CallableBias(
                name="smoothness_penalty",
                func=_SmoothnessPenalty(machines=int(problem.machines), days=int(problem.days)),
                weight=float(smooth_weight),
                mode="penalty",
            )
        )
    if variance_weight > 0:
        module.add(
            CallableBias(
                name="variance_penalty",
                func=_VariancePenalty(machines=int(problem.machines), days=int(problem.days)),
                weight=float(variance_weight),
                mode="penalty",
            )
        )
    if coverage_weight > 0:
        module.add(
            CallableBias(
                name="coverage_reward",
                func=_CoverageReward(machines=int(problem.machines), days=int(problem.days), feasible_mask=feasible_mask),
                weight=float(coverage_weight),
                mode="reward",
            )
        )
    return module
