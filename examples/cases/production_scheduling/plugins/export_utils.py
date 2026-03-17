"""Export/report utilities for production_scheduling case."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
from typing import Callable, Optional

import numpy as np


def choose_pareto_solutions(problem, individuals: np.ndarray, objectives: np.ndarray):
    if individuals is None or len(individuals) == 0:
        return []
    penalties = []
    for ind in individuals:
        schedule = problem.decode_schedule(ind)
        penalties.append(problem._compute_penalty(schedule))
    penalties = np.asarray(penalties, dtype=float)

    idx_penalty = int(np.argmin(penalties))
    idx_prod = int(np.argmin(objectives[:, 0]))
    picks = []
    seen = set()
    for label, idx in (("penalty", idx_penalty), ("production", idx_prod)):
        if idx in seen:
            continue
        seen.add(idx)
        picks.append((label, individuals[idx], objectives[idx]))
    return picks


def crowding_distance(objectives: np.ndarray) -> np.ndarray:
    if objectives is None or len(objectives) == 0:
        return np.array([], dtype=float)
    n, m = objectives.shape
    distance = np.zeros(n, dtype=float)
    for obj_idx in range(m):
        order = np.argsort(objectives[:, obj_idx])
        distance[order[0]] = np.inf
        distance[order[-1]] = np.inf
        f_min = objectives[order[0], obj_idx]
        f_max = objectives[order[-1], obj_idx]
        if f_max - f_min <= 1e-12:
            continue
        for i in range(1, n - 1):
            prev_val = objectives[order[i - 1], obj_idx]
            next_val = objectives[order[i + 1], obj_idx]
            distance[order[i]] += (next_val - prev_val) / (f_max - f_min)
    return distance


def get_pareto_export_root(base: Optional[Path]) -> Path:
    if base is None:
        base_dir = default_export_dir()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        root = base_dir / f"integrated_result_pareto_{ts}"
    elif base.suffix:
        root = base.with_name(f"{base.stem}_pareto")
    else:
        root = base
    root.mkdir(parents=True, exist_ok=True)
    return root


def get_summary_path(root: Path) -> Path:
    return root / "pareto_summary.csv"


def export_pareto_batch(
    problem,
    individuals: np.ndarray,
    objectives: np.ndarray,
    base_export: Optional[Path],
    mode: str,
    limit: int,
    *,
    project_schedule_material_feasible: Callable[[object, np.ndarray], np.ndarray],
) -> int:
    if individuals is None or len(individuals) == 0:
        return 0
    total = len(individuals)
    if limit <= 0:
        limit = total
    else:
        limit = max(1, min(int(limit), total))

    export_root = get_pareto_export_root(base_export)
    ext = ".xlsx"
    if base_export is not None and base_export.suffix:
        ext = base_export.suffix

    if mode == "crowding":
        crowd = crowding_distance(objectives)
        order = np.argsort(-crowd)
    elif mode == "production":
        order = np.argsort(objectives[:, 0])
    else:
        order = np.arange(total)

    selected = order[:limit]
    rows = []
    for rank, idx in enumerate(selected, start=1):
        label = f"pareto{rank:02d}"
        schedule = problem.decode_schedule(individuals[idx])
        schedule = project_schedule_material_feasible(problem, schedule)
        obj_vals = problem.evaluate(schedule.reshape(-1))
        summary = problem.summarize_schedule(schedule)
        export_path = export_root / f"{label}{ext}"
        export_schedule(export_path, schedule)
        row = {"label": label, "file": str(export_path)}
        for j, value in enumerate(obj_vals):
            row[f"obj{j}"] = float(value)
        row.update(summary)
        rows.append(row)

    if rows:
        import pandas as pd

        summary_path = get_summary_path(export_root)
        df = pd.DataFrame(rows)
        df.to_csv(summary_path, index=False)
    return len(rows)


def default_export_path(prefix: str = "integrated_result", label: Optional[str] = None) -> Path:
    base_dir = default_export_dir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    if label:
        return base_dir / f"{prefix}_{label}_{ts}.xlsx"
    return base_dir / f"{prefix}_{ts}.xlsx"


def default_export_dir() -> Path:
    """Centralize run exports to avoid cluttering `examples/cases` root."""
    base_dir = Path(__file__).resolve().parents[2] / "runs" / "production_schedule" / "exports"
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


def get_export_path(base: Optional[Path], label: str, supply_tag: Optional[str] = None) -> Path:
    suffix = f"_{supply_tag}" if supply_tag else ""
    if base is None:
        p = default_export_path(label=label)
        if suffix:
            return p.with_name(f"{p.stem}{suffix}{p.suffix}")
        return p
    if base.suffix:
        return base.with_name(f"{base.stem}_{label}{suffix}{base.suffix}")
    p = default_export_path(label=label)
    name = f"{p.stem}{suffix}{p.suffix}" if suffix else p.name
    return base / name


def supply_tag_from_path(path: Optional[Path | str]) -> Optional[str]:
    if path is None:
        return None
    try:
        stem = Path(path).stem
    except (TypeError, ValueError):
        return None
    tag = re.sub(r"[^A-Za-z0-9_-]+", "_", str(stem)).strip("_")
    if not tag:
        return None
    return f"src-{tag[:28]}"


def write_export_summary(
    *,
    export_path: Path,
    label: str,
    supply_path: str,
    feasible: bool,
    constraints: list[float],
    total_output: float,
    days: int,
) -> None:
    summary_path = export_path.with_suffix(".summary.json")
    payload = {
        "label": str(label),
        "export_file": str(export_path),
        "supply_path": str(supply_path),
        "feasible": bool(feasible),
        "constraints": [float(x) for x in constraints],
        "max_violation": float(max([0.0] + [max(0.0, float(v)) for v in constraints])),
        "total_output": float(total_output),
        "days": int(days),
    }
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def export_schedule(path: Path, schedule: np.ndarray) -> None:
    import pandas as pd

    schedule = np.asarray(schedule, dtype=float)
    schedule = np.clip(np.floor(schedule), 0, None).astype(int)
    machines, days = schedule.shape

    data = {
        "Day_Index": list(range(days)),
        "Date": [f"Day{day + 1}" for day in range(days)],
    }
    for m in range(machines):
        data[f"Machine{m}"] = schedule[m, :].tolist()

    df = pd.DataFrame(data)
    if path.suffix.lower() == ".xlsx":
        df.to_excel(path, index=False, sheet_name="production_plan")
    else:
        df.to_csv(path, index=False)


def extract_pareto(solver_or_result) -> tuple[Optional[np.ndarray], Optional[np.ndarray]]:
    """Normalize Pareto outputs from solver runtime or result dict."""
    if isinstance(solver_or_result, dict):
        pareto = solver_or_result.get("pareto_solutions")
        if isinstance(pareto, dict) and "individuals" in pareto:
            individuals = np.asarray(pareto["individuals"], dtype=float)
            objectives = np.asarray(pareto["objectives"], dtype=float)
            return individuals, objectives
        return None, None

    pareto_x = getattr(solver_or_result, "pareto_solutions", None)
    pareto_f = getattr(solver_or_result, "pareto_objectives", None)
    if pareto_x is None or pareto_f is None:
        return None, None
    return np.asarray(pareto_x, dtype=float), np.asarray(pareto_f, dtype=float)
