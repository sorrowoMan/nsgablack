"""Material-feasibility projection used by the schedule pipeline and exports."""

from __future__ import annotations

import numpy as np


def project_schedule_material_feasible(problem, schedule: np.ndarray) -> np.ndarray:
    """Project a schedule onto day-by-day material availability."""

    projected = np.asarray(schedule, dtype=float).copy()
    projected = np.clip(
        projected,
        0.0,
        float(problem.constraints.max_production_per_machine),
    )
    machines, days = projected.shape
    if machines != int(problem.machines) or days != int(problem.days):
        return projected
    bom = np.asarray(problem.data.bom_matrix, dtype=float)
    supply = np.asarray(problem.data.supply_matrix, dtype=float)
    current_stock = np.zeros(int(problem.materials), dtype=float)
    for day in range(days):
        current_stock += supply[:, day]
        day_production = projected[:, day].copy()
        for machine in np.argsort(-day_production):
            quantity = float(day_production[machine])
            if quantity <= 0.0:
                continue
            requirements = bom[machine, :]
            required = requirements > 0
            if not np.any(required):
                continue
            feasible = float(
                np.min(
                    current_stock[required]
                    / np.maximum(requirements[required], 1e-12)
                )
            )
            if feasible < quantity:
                day_production[machine] = max(0.0, feasible)
            current_stock = np.maximum(
                0.0,
                current_stock
                - requirements * float(day_production[machine]),
            )
        projected[:, day] = day_production
    return projected


__all__ = ["project_schedule_material_feasible"]
