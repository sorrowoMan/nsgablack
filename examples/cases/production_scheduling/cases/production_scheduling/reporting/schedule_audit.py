"""Business-facing audit metrics for exported production schedules."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np


def compute_schedule_audit(problem: Any, schedule: np.ndarray, *, label: str = "") -> dict[str, Any]:
    """Compute stable, business-readable metrics for a decoded schedule.

    This report intentionally keeps raw optimization objectives separate from
    operational indicators. Objectives are useful for the solver; the audit is
    useful for deciding whether a plan is credible.
    """

    schedule_arr = np.asarray(schedule, dtype=float)
    if schedule_arr.ndim != 2:
        schedule_arr = schedule_arr.reshape(int(problem.machines), int(problem.days))

    daily_production = np.sum(schedule_arr, axis=0)
    daily_active = np.sum(schedule_arr > 0, axis=0)
    machine_production = np.sum(schedule_arr, axis=1)
    objective_vector = _safe_float_list(problem.evaluate(schedule_arr.reshape(-1)))
    constraint_vector = _safe_float_list(problem.evaluate_constraints(schedule_arr.reshape(-1)))
    positive_violations = [max(0.0, value) for value in constraint_vector]
    finite_violations = [value for value in positive_violations if np.isfinite(value)]
    max_violation = float(max([0.0] + finite_violations))

    sanity = {}
    if hasattr(problem, "sanity_check_schedule"):
        sanity = dict(problem.sanity_check_schedule(schedule_arr))

    stock = _material_flow(problem, schedule_arr)
    switches_total, switches_by_machine = _switching_metrics(schedule_arr)

    return {
        "schema": "production_scheduling.schedule_audit.v1",
        "label": str(label),
        "feasible": bool(max_violation <= 1e-9),
        "objectives": objective_vector,
        "constraints": constraint_vector,
        "max_positive_violation": max_violation,
        "production": {
            "total": float(np.sum(schedule_arr)),
            "daily_mean": float(np.mean(daily_production)) if daily_production.size else 0.0,
            "daily_min": float(np.min(daily_production)) if daily_production.size else 0.0,
            "daily_max": float(np.max(daily_production)) if daily_production.size else 0.0,
            "daily_std": float(np.std(daily_production)) if daily_production.size else 0.0,
            "daily_cv": _cv(daily_production),
            "idle_days": int(np.sum(daily_production <= 1e-9)),
        },
        "machine_usage": {
            "active_daily_mean": float(np.mean(daily_active)) if daily_active.size else 0.0,
            "active_daily_min": int(np.min(daily_active)) if daily_active.size else 0,
            "active_daily_max": int(np.max(daily_active)) if daily_active.size else 0,
            "machines_used": int(np.sum(machine_production > 1e-9)),
            "switches_total": int(switches_total),
            "switches_by_machine_top": switches_by_machine[:10],
        },
        "material_flow": stock,
        "sanity": sanity,
    }


def write_schedule_audit_report(problem: Any, schedule: np.ndarray, path: Path, *, label: str = "") -> Path:
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    payload = compute_schedule_audit(problem, schedule, label=label)
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return report_path


def _material_flow(problem: Any, schedule: np.ndarray) -> dict[str, Any]:
    supply = np.asarray(problem.data.supply_matrix, dtype=float)
    bom = np.asarray(getattr(problem, "_bom_float", problem.data.bom_matrix), dtype=float)
    current_stock = np.zeros(supply.shape[0], dtype=float)
    total_shortage_by_material = np.zeros(supply.shape[0], dtype=float)
    min_stock_by_material = np.full(supply.shape[0], np.inf, dtype=float)
    total_consumption_by_material = np.zeros(supply.shape[0], dtype=float)

    for day in range(schedule.shape[1]):
        current_stock += supply[:, day]
        consumption = schedule[:, day] @ bom
        total_consumption_by_material += consumption
        shortage = np.maximum(0.0, consumption - current_stock)
        total_shortage_by_material += shortage
        current_stock = current_stock - consumption
        min_stock_by_material = np.minimum(min_stock_by_material, current_stock)
        current_stock = np.maximum(0.0, current_stock)

    shortage_idx = np.argsort(-total_shortage_by_material)[:10]
    bottlenecks = [
        {
            "material_index": int(idx),
            "shortage": float(total_shortage_by_material[idx]),
            "consumption": float(total_consumption_by_material[idx]),
            "supply": float(np.sum(supply[idx])),
        }
        for idx in shortage_idx
        if float(total_shortage_by_material[idx]) > 1e-9
    ]
    return {
        "total_supply": float(np.sum(supply)),
        "total_consumption": float(np.sum(total_consumption_by_material)),
        "ending_stock_total": float(np.sum(current_stock)),
        "shortage_total": float(np.sum(total_shortage_by_material)),
        "materials_with_shortage": int(np.sum(total_shortage_by_material > 1e-9)),
        "min_stock_after_min": float(np.min(min_stock_by_material)) if min_stock_by_material.size else 0.0,
        "top_shortage_materials": bottlenecks,
    }


def _switching_metrics(schedule: np.ndarray) -> tuple[int, list[dict[str, int]]]:
    if schedule.shape[1] <= 1:
        return 0, []
    active = schedule > 0
    switches = np.sum(active[:, 1:] != active[:, :-1], axis=1)
    order = np.argsort(-switches)
    top = [
        {"machine_index": int(idx), "switches": int(switches[idx])}
        for idx in order[:10]
        if int(switches[idx]) > 0
    ]
    return int(np.sum(switches)), top


def _cv(values: np.ndarray) -> float:
    arr = np.asarray(values, dtype=float)
    mean = float(np.mean(arr)) if arr.size else 0.0
    if abs(mean) <= 1e-12:
        return 0.0
    return float(np.std(arr) / abs(mean))


def _safe_float_list(values: Any) -> list[float]:
    arr = np.asarray(values, dtype=float).reshape(-1)
    return [float(x) for x in arr]
