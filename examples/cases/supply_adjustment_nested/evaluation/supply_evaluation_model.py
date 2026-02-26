from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import numpy as np


@dataclass
class SupplyInnerConfig:
    materials: int = 10
    machines: int = 6
    days: int = 14
    seed: int = 42
    max_active_machines_per_day: int = 4


class SupplyPlanEvaluationModel:
    """Inner evaluation model.

    Outer layer optimizes supply scaling factors.
    Inner model simulates a production scheduler/backend and returns metrics.
    """

    context_requires = ()
    context_provides = ("inner_metrics",)
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "Evaluate supply plan by running inner production simulation backend.",
    )

    def __init__(self, cfg: SupplyInnerConfig | None = None) -> None:
        self.cfg = cfg or SupplyInnerConfig()
        rng = np.random.default_rng(self.cfg.seed)
        self.base_supply = rng.integers(40, 120, size=(self.cfg.materials, self.cfg.days)).astype(float)
        # material usage per unit production (sparse)
        req = rng.uniform(0.0, 1.0, size=(self.cfg.machines, self.cfg.materials))
        req[req < 0.75] = 0.0
        req[req >= 0.75] = rng.uniform(0.2, 1.4, size=np.count_nonzero(req >= 0.75))
        self.machine_material_req = req
        self.machine_daily_cap = rng.integers(8, 20, size=self.cfg.machines).astype(float)
        self.daily_target_output = float(np.sum(self.machine_daily_cap) * 0.55)
        self.total_supply_budget = float(np.sum(self.base_supply) * 1.18)

    def evaluate_supply(self, scales: np.ndarray) -> Dict[str, float]:
        """Run inner backend and return normalized metrics."""
        scales = np.asarray(scales, dtype=float).reshape(self.cfg.days)
        supply = self.base_supply * scales.reshape(1, -1)
        return self._run_greedy_backend(supply)

    def _run_greedy_backend(self, supply: np.ndarray) -> Dict[str, float]:
        stock = np.zeros(self.cfg.materials, dtype=float)
        total_output = 0.0
        shortage = 0.0
        machine_excess = 0.0

        for day in range(self.cfg.days):
            stock += supply[:, day]
            day_output = 0.0
            active = 0
            priorities = np.argsort(-self.machine_daily_cap)
            for m in priorities:
                req = self.machine_material_req[m]
                req_mask = req > 0.0
                if not np.any(req_mask):
                    continue
                feasible = float(np.min(stock[req_mask] / np.maximum(req[req_mask], 1e-12)))
                prod = max(0.0, min(float(self.machine_daily_cap[m]), feasible))
                if prod > 1e-9:
                    active += 1
                    stock -= req * prod
                    day_output += prod
            total_output += day_output
            shortage += max(0.0, self.daily_target_output - day_output)
            machine_excess += max(0.0, active - self.cfg.max_active_machines_per_day)

        total_supply_used = float(np.sum(supply))
        budget_violation = max(0.0, total_supply_used - self.total_supply_budget)

        return {
            "total_output": float(total_output),
            "shortage": float(shortage),
            "machine_excess": float(machine_excess),
            "budget_violation": float(budget_violation),
            "total_supply_used": float(total_supply_used),
        }
