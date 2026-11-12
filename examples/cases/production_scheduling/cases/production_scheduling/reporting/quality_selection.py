"""Read-only audit and explicit selection of delivered production schedules.

Use the same multi-objective Problem for every algorithm, including schedules
found by a single-objective baseline.  Selection scores are report views: they
never replace Problem objectives, Solver feedback, or Pool evidence.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from .schedule_audit import compute_schedule_audit


def evaluate_schedule_quality(
    problem: Any,
    schedule: np.ndarray,
    *,
    label: str = "",
    integer_export: bool = False,
    feasibility_tolerance: float = 1e-9,
) -> dict[str, Any]:
    """Audit a detached schedule under the caller's unchanged raw Problem.

    ``integer_export=True`` explicitly applies the existing CSV export's floor
    rule and re-evaluates that integer schedule.  The input is never repaired,
    updated in place, or assigned another candidate identity.  An independent
    cumulative-stock check catches borrowing from future arrivals.
    """
    if type(integer_export) is not bool:
        raise TypeError("integer_export must be an explicit boolean")
    tolerance = float(feasibility_tolerance)
    if not np.isfinite(tolerance) or tolerance < 0:
        raise ValueError("feasibility_tolerance must be finite and nonnegative")
    shape = (int(problem.machines), int(problem.days))
    source = np.asarray(schedule, dtype=float)
    if source.shape not in {shape, (shape[0] * shape[1],)}:
        raise ValueError("schedule must match the original Problem's machine/day shape")
    values = np.array(source.reshape(shape), dtype=float, copy=True)
    if not np.all(np.isfinite(values)) or np.any(values < 0):
        raise ValueError("schedule quantities must be finite and nonnegative")
    original_total = float(np.sum(values))
    if integer_export:
        values = np.floor(values)
    audit = compute_schedule_audit(problem, values, label=label)
    objectives = np.asarray(audit["objectives"], dtype=float)
    constraints = np.asarray(audit["constraints"], dtype=float)
    if objectives.ndim != 1 or objectives.size not in (1, 4, 5):
        raise ValueError("quality audit supports the original one/four/five-objective Problem")
    if not np.all(np.isfinite(objectives)) or not np.all(np.isfinite(constraints)):
        raise ValueError("raw objectives and constraints must be finite")

    bom = np.asarray(problem.data.bom_matrix, dtype=float)
    supply = np.asarray(problem.data.supply_matrix, dtype=float)
    if bom.shape != (shape[0], int(problem.materials)) or supply.shape != (int(problem.materials), shape[1]):
        raise ValueError("BOM and supply shapes must match the original Problem")
    if not np.all(np.isfinite(bom)) or not np.all(np.isfinite(supply)):
        raise ValueError("BOM and supply must be finite")
    cumulative_stock = np.cumsum(supply - bom.T @ values, axis=1)
    min_stock = float(np.min(cumulative_stock))
    raw_feasible = bool(np.all(constraints <= tolerance))
    stock_feasible = min_stock >= -tolerance
    daily_active = np.sum(values > 0, axis=0)
    rules = problem.constraints
    below = np.where((values > 0) & (values < rules.min_production_per_machine),
                     rules.min_production_per_machine - values, 0.0)
    return {
        "schema": "production_scheduling.quality/v1",
        "label": str(label),
        "schedule_shape": list(shape),
        "evaluation_view": "integer_export" if integer_export else "as_supplied",
        "integer_schedule": bool(np.array_equal(values, np.floor(values))),
        "input_total": original_total,
        "floor_output_delta": original_total - float(np.sum(values)),
        "raw_objectives": objectives.tolist(),
        "raw_objective_count": int(objectives.size),
        "raw_constraints": constraints.tolist(),
        "raw_hard_feasible": raw_feasible,
        "independent_stock_feasible": stock_feasible,
        "min_cumulative_stock": min_stock,
        "hard_feasible": raw_feasible and stock_feasible,
        "soft_deviations": {
            "days_below_minimum_active": int(np.sum(daily_active < rules.min_machines_per_day)),
            "active_count_shortfall": float(np.maximum(0, rules.min_machines_per_day - daily_active).sum()),
            "positive_cells_below_minimum_production": int(np.sum(below > 0)),
            "minimum_production_shortfall": float(below.sum()),
            "maximum_production_excess": float(np.maximum(0, values - rules.max_production_per_machine).sum()),
            "minimum_active_is_soft": bool(rules.soft_min_machines),
            "minimum_production_is_soft": bool(rules.soft_min_production),
            "maximum_production_is_soft": bool(rules.soft_max_production),
        },
        "audit": audit,
    }


def select_schedule_quality(
    reports: Sequence[Mapping[str, Any]],
    *,
    policy: str = "pareto",
    minimum_output_fraction: float = 0.0,
    weights: Sequence[float] | None = None,
    normalization_bounds: Sequence[Sequence[float]] | None = None,
) -> dict[str, Any]:
    """Return original positions using a declared report-selection policy.

    Default ``pareto`` returns every hard-feasible non-dominated raw-objective
    position, making no unconfirmed choice for the user. ``production`` and
    ``stability`` explicitly prioritize total quantity or daily CV. ``balanced``
    uses weighted minimax regret over normalized *original* objective axes.
    Bounds and weights are included in the result; use fixed shared bounds to
    compare policies across experiment cohorts.  These are presentation scores.

    ``minimum_output_fraction`` is an explicit floor relative to the largest
    feasible output in this supplied cohort.  It is not a Problem constraint.
    """
    if policy not in {"pareto", "production", "stability", "balanced"}:
        raise ValueError("unknown schedule selection policy")
    if policy != "balanced" and (weights is not None or normalization_bounds is not None):
        raise ValueError("normalization bounds and weights belong to the explicit balanced policy")
    fraction = float(minimum_output_fraction)
    if not np.isfinite(fraction) or not 0 <= fraction <= 1:
        raise ValueError("minimum_output_fraction must be in [0, 1]")
    rows = list(reports)
    vectors, quantities, cvs, feasible = [], [], [], []
    dimensions = None
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping) or type(row.get("hard_feasible")) is not bool:
            raise ValueError("reports must be evaluated schedule quality records")
        vector = np.asarray(row.get("raw_objectives"), dtype=float)
        if vector.ndim != 1 or vector.size not in (1, 4, 5) or not np.all(np.isfinite(vector)):
            raise ValueError("raw objective vectors must be finite and have one/four/five axes")
        if dimensions is not None and dimensions != vector.size:
            raise ValueError("all reports must use the same original objective axes")
        dimensions = int(vector.size)
        production = row.get("audit", {}).get("production", {})
        quantity, cv = float(production.get("total", np.nan)), float(production.get("daily_cv", np.nan))
        if not np.isfinite(quantity) or not np.isfinite(cv) or quantity < 0 or cv < 0:
            raise ValueError("production quantity and CV must be finite and nonnegative")
        vectors.append(vector)
        quantities.append(quantity)
        cvs.append(cv)
        if row["hard_feasible"]:
            feasible.append(index)
    floor = max((quantities[i] for i in feasible), default=0.0) * fraction
    eligible = [i for i in feasible if quantities[i] >= floor]
    frontier = [i for i in eligible if not any(
        j != i and np.all(vectors[j] <= vectors[i]) and np.any(vectors[j] < vectors[i])
        for j in eligible)]
    result = {
        "schema": "production_scheduling.quality_selection/v1", "policy": policy,
        "feasible_indices": feasible, "eligible_indices": eligible,
        "non_dominated_indices": frontier, "selected_indices": list(frontier),
        "minimum_output_fraction": fraction, "minimum_output": floor,
        "objective_directions": "all original axes minimized", "scores": [],
        "normalization_bounds": None, "ideal_point": None, "nadir_point": None,
        "objective_scales": None, "weights": None,
        "scope": "supplied schedule reports; no Solver or Pool state is changed",
    }
    if not frontier:
        return result
    if policy == "production":
        result["selected_indices"] = [min(frontier, key=lambda i: (-quantities[i], cvs[i], i))]
    elif policy == "stability":
        result["selected_indices"] = [min(frontier, key=lambda i: (cvs[i], -quantities[i], i))]
    elif policy == "balanced":
        if dimensions == 1:
            raise ValueError("balanced comparison requires the same original four/five-objective audit Problem for all algorithms")
        matrix = np.stack([vectors[i] for i in frontier])
        if normalization_bounds is None:
            low, high = np.min(matrix, axis=0), np.max(matrix, axis=0)
            bounds_source = "supplied hard-feasible Pareto frontier"
        else:
            bounds = np.asarray(normalization_bounds, dtype=float)
            if bounds.shape != (dimensions, 2) or not np.all(np.isfinite(bounds)) or np.any(bounds[:, 1] < bounds[:, 0]):
                raise ValueError("normalization_bounds must contain finite [minimum, maximum] per original axis")
            low, high = bounds[:, 0], bounds[:, 1]
            bounds_source = "explicit shared reference"
            constant = high == low
            if np.any(matrix[:, constant] != low[constant]):
                raise ValueError("constant reference axes cannot hide varying raw objectives")
        weight = np.ones(dimensions) if weights is None else np.asarray(weights, dtype=float)
        if weight.shape != (dimensions,) or not np.all(np.isfinite(weight)) or np.any(weight < 0) or not np.any(weight > 0):
            raise ValueError("weights must match original axes, be finite and nonnegative, with positive total")
        weight = weight / weight.sum()
        width = high - low
        active = width > 0
        scores = []
        for i in frontier:
            normalized = np.zeros(dimensions)
            normalized[active] = (vectors[i][active] - low[active]) / width[active]
            weighted = normalized * weight
            scores.append({"index": i, "weighted_worst_regret": float(np.max(weighted)),
                           "weighted_mean_regret": float(np.sum(weighted)),
                           "normalized_objectives": normalized.tolist()})
        winner = min(scores, key=lambda row: (row["weighted_worst_regret"], row["weighted_mean_regret"], row["index"]))
        result.update(selected_indices=[winner["index"]], scores=scores,
                      normalization_bounds=np.stack((low, high), axis=1).tolist(),
                      normalization_source=bounds_source, ideal_point=low.tolist(),
                      nadir_point=high.tolist(), objective_scales=width.tolist(),
                      weights=weight.tolist())
    return result


__all__ = ["evaluate_schedule_quality", "select_schedule_quality"]
