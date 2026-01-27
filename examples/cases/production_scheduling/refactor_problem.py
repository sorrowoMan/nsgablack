# -*- coding: utf-8 -*-
"""Problem definition for pipeline-first production scheduling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

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

from nsgablack.core.base import BlackBoxProblem

from refactor_data import ProductionData


@dataclass
class ProductionConstraints:
    max_machines_per_day: int = 8
    min_machines_per_day: int = 0
    min_production_per_machine: int = 100
    max_production_per_machine: int = 3000
    shortage_unit_penalty: float = 1.0
    include_penalty_objective: bool = True
    penalty_objective_scale: float = 0.001
    soft_min_machines: bool = True
    soft_min_production: bool = True
    soft_max_production: bool = True


class ProductionSchedulingProblem(BlackBoxProblem):
    def __init__(
        self,
        data: ProductionData,
        constraints: ProductionConstraints,
        name: str = "ProductionScheduling",
    ):
        self.data = data
        self.constraints = constraints
        self.machines = data.machines
        self.materials = data.materials
        self.days = data.days
        self.machine_weights = getattr(data, "machine_weights", np.ones(data.machines, dtype=float))
        self.include_penalty_objective = constraints.include_penalty_objective
        self.penalty_objective_scale = constraints.penalty_objective_scale
        self.matrix_shape = (self.machines, self.days)
        self._bom_float = data.bom_matrix.astype(np.float32)
        dimension = self.machines * self.days

        bounds = {f"x{i}": [0, constraints.max_production_per_machine] for i in range(dimension)}
        # Keep a local alias for code paths that expect var_bounds.
        self.var_bounds = bounds
        objectives = [f"f{i}" for i in range(self.get_num_objectives())]
        super().__init__(name=name, dimension=dimension, bounds=bounds, objectives=objectives)

    def get_num_objectives(self) -> int:
        return 5 if self.include_penalty_objective else 4

    def decode_schedule(self, x: np.ndarray) -> np.ndarray:
        vec = np.asarray(x, dtype=float).reshape(self.machines, self.days)
        return vec

    def _compute_material_shortage(self, schedule: np.ndarray) -> float:
        current_stock = np.zeros(self.materials, dtype=np.float32)
        total_shortage = 0.0
        for day in range(self.days):
            current_stock += self.data.supply_matrix[:, day]
            consumption = schedule[:, day].astype(np.float32) @ self._bom_float
            shortage = np.maximum(0.0, consumption - current_stock)
            total_shortage += float(np.sum(shortage))
            current_stock = np.maximum(0.0, current_stock - consumption)
        return total_shortage

    def _constraint_components(self, schedule: np.ndarray) -> Dict[str, float]:
        daily_active = np.sum(schedule > 0, axis=0)
        max_machines = self.constraints.max_machines_per_day
        min_machines = self.constraints.min_machines_per_day

        excess_machines = np.maximum(0, daily_active - max_machines).sum()
        shortage_machines = np.maximum(0, min_machines - daily_active).sum() if min_machines > 0 else 0.0

        min_prod = self.constraints.min_production_per_machine
        max_prod = self.constraints.max_production_per_machine
        below_min = np.where((schedule > 0) & (schedule < min_prod), (min_prod - schedule), 0.0).sum()
        above_max = np.maximum(0.0, schedule - max_prod).sum()

        material_shortage = self._compute_material_shortage(schedule)
        return {
            "material_shortage": float(material_shortage),
            "excess_machines": float(excess_machines),
            "shortage_machines": float(shortage_machines),
            "below_min_production": float(below_min),
            "above_max_production": float(above_max),
        }

    def evaluate_constraints(self, x: np.ndarray) -> np.ndarray:
        schedule = self.decode_schedule(x)
        comps = self._constraint_components(schedule)
        shortage_machines = 0.0 if self.constraints.soft_min_machines else comps["shortage_machines"]
        below_min = 0.0 if self.constraints.soft_min_production else comps["below_min_production"]
        above_max = 0.0 if self.constraints.soft_max_production else comps["above_max_production"]
        return np.array(
            [
                comps["material_shortage"],
                comps["excess_machines"],
                shortage_machines,
                below_min,
                above_max,
            ],
            dtype=float,
        )

    def evaluate(self, x: np.ndarray) -> np.ndarray:
        schedule = self.decode_schedule(x)

        total_production = float(np.sum(schedule))
        daily_production = np.sum(schedule, axis=0)
        daily_active = np.sum(schedule > 0, axis=0)

        comps = self._constraint_components(schedule)
        penalty = self._compute_penalty(
            schedule,
            comps=comps,
            daily_active=daily_active,
            daily_production=daily_production,
        )

        mean_prod = np.mean(daily_production) + 1e-6
        production_variance = np.var(daily_production) / (mean_prod**2)

        max_machines = float(self.constraints.max_machines_per_day)
        fullness_penalty = np.mean(np.abs(daily_active - max_machines)) / (max_machines + 1e-6)

        if self.days > 1:
            production_changes = np.abs(np.diff(daily_production))
            smooth_penalty = np.mean(production_changes) / mean_prod
        else:
            smooth_penalty = 0.0
        idle_ratio = np.mean(daily_production <= 1e-6)
        if self.days > 1:
            active_bmd = schedule > 0
            switches_bm = (active_bmd[:, 1:] != active_bmd[:, :-1]).sum(axis=1)
            continuity_penalty = np.mean(switches_bm) / float(max(1, self.days - 1))
        else:
            continuity_penalty = 0.0

        smooth_metric = smooth_penalty + 1.5 * idle_ratio + 1.5 * continuity_penalty
        if self.include_penalty_objective:
            objectives = np.array(
                [
                    -total_production,
                    penalty * float(self.penalty_objective_scale),
                    production_variance,
                    fullness_penalty,
                    smooth_metric,
                ],
                dtype=float,
            )
        else:
            objectives = np.array(
                [
                    -total_production,
                    production_variance,
                    fullness_penalty,
                    smooth_metric,
                ],
                dtype=float,
            )
        return objectives

    def _compute_penalty(
        self,
        schedule: np.ndarray,
        *,
        comps: Optional[Dict[str, float]] = None,
        daily_active: Optional[np.ndarray] = None,
        daily_production: Optional[np.ndarray] = None,
    ) -> float:
        if comps is None:
            comps = self._constraint_components(schedule)
        if daily_active is None:
            daily_active = np.sum(schedule > 0, axis=0)
        if daily_production is None:
            daily_production = np.sum(schedule, axis=0)

        penalty = comps["material_shortage"] * self.constraints.shortage_unit_penalty
        penalty += comps["excess_machines"] * 10000.0
        penalty += comps["shortage_machines"] * 8000.0
        penalty += comps["below_min_production"] * 1.0
        penalty += comps["above_max_production"] * 1.0

        max_machines = float(self.constraints.max_machines_per_day)
        min_machines = float(self.constraints.min_machines_per_day or max_machines)
        shortage_penalty = np.sum(np.clip(max_machines - daily_active, 0, None)) * 80000.0
        days_under_penalty = np.sum(daily_active < max_machines) * 250000.0
        min_target_penalty = np.sum(daily_active < min_machines) * 300000.0
        zero_prod_penalty = np.sum(daily_production <= 1e-6) * 200000.0
        penalty += shortage_penalty + days_under_penalty + min_target_penalty + zero_prod_penalty
        return float(penalty)

    def summarize_schedule(self, schedule: np.ndarray) -> Dict[str, float]:
        comps = self._constraint_components(schedule)
        daily_active = np.sum(schedule > 0, axis=0)
        daily_production = np.sum(schedule, axis=0)
        penalty = self._compute_penalty(
            schedule,
            comps=comps,
            daily_active=daily_active,
            daily_production=daily_production,
        )
        return {
            "total_production": float(np.sum(schedule)),
            "avg_daily_production": float(np.mean(daily_production)),
            "avg_daily_active": float(np.mean(daily_active)),
            "material_shortage": comps["material_shortage"],
            "excess_machines": comps["excess_machines"],
            "penalty_score": penalty,
        }
