"""Audit metrics for event-level supply adjustment plans."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np


def compute_supply_adjustment_audit(
    problem: Any,
    x: np.ndarray,
    *,
    objectives: np.ndarray | None = None,
    label: str = "",
) -> dict[str, Any]:
    shifts = problem.decode_shifts(np.asarray(x, dtype=float))
    adjusted = problem.apply_shifts(shifts)
    base = np.asarray(problem.base_supply, dtype=float)
    moved_idx = np.flatnonzero(shifts > 0)

    moved_quantity = 0.0
    moved_quantity_days = 0.0
    moved_days_values: list[int] = []
    touched_materials: set[int] = set()
    from_days: dict[int, int] = {}
    to_days: dict[int, int] = {}
    for event_index in moved_idx:
        ev = problem.events[int(event_index)]
        shift = int(shifts[int(event_index)])
        moved_days_values.append(shift)
        moved_quantity += float(ev.quantity)
        moved_quantity_days += float(ev.quantity) * float(shift)
        touched_materials.add(int(ev.material_idx))
        from_days[int(ev.day)] = from_days.get(int(ev.day), 0) + 1
        to_day = int(ev.day - shift)
        to_days[to_day] = to_days.get(to_day, 0) + 1

    day_totals_before = np.sum(base, axis=0)
    day_totals_after = np.sum(adjusted, axis=0)
    material_totals_before = np.sum(base, axis=1)
    material_totals_after = np.sum(adjusted, axis=1)
    conservation_error = float(np.max(np.abs(material_totals_after - material_totals_before))) if base.size else 0.0

    decoded_constraints = []
    if hasattr(problem, "evaluate_constraints"):
        decoded_constraints = _safe_float_list(problem.evaluate_constraints(np.asarray(x, dtype=float)))

    return {
        "schema": "supply_adjustment_nested.supply_adjustment_audit.v1",
        "label": str(label),
        "dimension": int(problem.dimension),
        "objectives": [] if objectives is None else _safe_float_list(objectives),
        "constraints": decoded_constraints,
        "max_positive_violation": float(max([0.0] + [max(0.0, v) for v in decoded_constraints])),
        "move_summary": {
            "moved_events": int(moved_idx.size),
            "moved_days_total": int(np.sum(shifts)),
            "moved_days_max": int(np.max(shifts)) if shifts.size else 0,
            "max_moved_days": int(np.max(shifts)) if shifts.size else 0,
            "avg_moved_days": float(np.mean(moved_days_values)) if moved_days_values else 0.0,
            "median_moved_days": float(np.median(moved_days_values)) if moved_days_values else 0.0,
            "events_le_7_days": int(sum(1 for v in moved_days_values if int(v) <= 7)),
            "events_le_14_days": int(sum(1 for v in moved_days_values if int(v) <= 14)),
            "events_le_21_days": int(sum(1 for v in moved_days_values if int(v) <= 21)),
            "events_gt_21_days": int(sum(1 for v in moved_days_values if int(v) > 21)),
            "moved_quantity": float(moved_quantity),
            "moved_quantity_days": float(moved_quantity_days),
            "avg_moved_quantity_days": float(moved_quantity_days / max(1, int(moved_idx.size))),
            "touched_materials": int(len(touched_materials)),
            "max_moved_events": None if problem.max_moved_events is None else int(problem.max_moved_events),
        },
        "supply_conservation": {
            "total_before": float(np.sum(base)),
            "total_after": float(np.sum(adjusted)),
            "material_total_max_abs_delta": conservation_error,
            "day0_delta": float(day_totals_after[0] - day_totals_before[0]) if day_totals_before.size else 0.0,
        },
        "timing_profile": {
            "from_day_event_counts": _sorted_int_dict(from_days),
            "to_day_event_counts": _sorted_int_dict(to_days),
            "daily_supply_before": _safe_float_list(day_totals_before),
            "daily_supply_after": _safe_float_list(day_totals_after),
            "daily_supply_delta": _safe_float_list(day_totals_after - day_totals_before),
        },
    }


def write_supply_adjustment_audit_report(
    problem: Any,
    x: np.ndarray,
    path: Path,
    *,
    objectives: np.ndarray | None = None,
    label: str = "",
) -> Path:
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    payload = compute_supply_adjustment_audit(problem, x, objectives=objectives, label=label)
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return report_path


def _sorted_int_dict(values: dict[int, int]) -> dict[str, int]:
    return {str(k): int(values[k]) for k in sorted(values)}


def _safe_float_list(values: Any) -> list[float]:
    arr = np.asarray(values, dtype=float).reshape(-1)
    return [float(x) for x in arr]
