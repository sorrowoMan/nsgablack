# -*- coding: utf-8 -*-
"""Data loading utilities for the refactored production scheduling app."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence, TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:  # pragma: no cover
    import pandas as pd

DEFAULT_MACHINE_WEIGHTS = np.array(
    [
        0.7,
        0.2,
        0.6,
        0.6,
        0.4,
        0.8,
        0.9,
        0.7,
        0.3,
        0.6,
        0.6,
        0.9,
        0.9,
        0.4,
        0.5,
        0.8,
        0.3,
        0.2,
        0.6,
        0.9,
        0.7,
        0.3,
    ],
    dtype=float,
)


DEFAULT_BOM_CANDIDATES = (
    # Recommended canonical names (Windows-friendly)
    "machine_material_mapping.csv",
    "BOM.csv",
    "BOM.xlsx",
    # Optional alternates / historical names
    "machine_material_mapping.xlsx",
)

DEFAULT_SUPPLY_CANDIDATES = (
    "SUPPLY.xlsx",
    # Recommended canonical names (Windows-friendly)
     "SUPPLY_adjusted_from_l1_20260226_174006.xlsx",
    
    "SUPPLY_adjusted_from_l1_20260226_174006.xlsx",
    "SUPPLY_adjusted_from_l1_20260226_155747.xlsx",
    "SUPPLY_adjusted_from_l1_20260226_153518.xlsx",
    "SUPPLY_adjusted_from_l1_20260225_173227.xlsx",
    
    "Adjusted_Supply_Plan_Rescheduled copy 4.xlsx",
    "SUPPLY_adjusted_from_l1_20260225_173227.xlsx",
    
    # Optional alternates / historical names
    
    "Adjusted_Supply_Plan_Optimized_20260107_212045.xlsx",
    "Adjusted_Supply_Plan_Optimized_20260107_021442.xlsx",
    "Adjusted_Supply_Plan_Enhanced.xlsx",
)


@dataclass
class ProductionData:
    machines: int
    materials: int
    days: int
    bom_matrix: np.ndarray
    supply_matrix: np.ndarray
    machine_weights: np.ndarray
    bom_path: Optional[Path] = None
    supply_path: Optional[Path] = None

    def estimate_theoretical_max(self) -> int:
        total_supply = float(np.sum(self.supply_matrix))
        total_material_types = float(np.sum(self.bom_matrix))
        if self.machines <= 0 or total_material_types <= 0:
            return 0
        avg_materials_per_product = total_material_types / float(self.machines)
        return int(total_supply / max(avg_materials_per_product, 1e-6))


def _resolve_existing(base_dir: Path, candidates: Sequence[str]) -> Optional[Path]:
    for name in candidates:
        path = base_dir / name
        if path.exists():
            return path
    return None


def _read_csv_with_fallback(path: Path) -> pd.DataFrame:
    import pandas as pd

    encodings = ("utf-8-sig", "utf-8", "gbk", "gb2312")
    last_error = None
    for enc in encodings:
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception as exc:
            last_error = exc
    raise last_error


def _read_table(path: Path) -> pd.DataFrame:
    import pandas as pd

    if path.suffix.lower() == ".csv":
        return _read_csv_with_fallback(path)
    return pd.read_excel(path)


def _normalize_id(value: object, max_count: int) -> Optional[int]:
    if value is None:
        return None
    try:
        idx = int(value)
    except (TypeError, ValueError):
        return None
    # Prefer 1-based IDs first (common in BOM/SUPPLY tables), then fallback to 0-based.
    if 1 <= idx <= max_count:
        return idx - 1
    if 0 <= idx < max_count:
        return idx
    return None


def _normalize_id_with_base(value: object, max_count: int, base: int) -> Optional[int]:
    if value is None:
        return None
    try:
        idx = int(value)
    except (TypeError, ValueError):
        return None
    if base == 0:
        return idx if 0 <= idx < max_count else None
    return (idx - 1) if 1 <= idx <= max_count else None


def load_bom_matrix(path: Path, machines: int, materials: int) -> np.ndarray:
    import pandas as pd

    df = _read_table(path)
    bom_matrix = np.zeros((machines, materials), dtype=bool)
    # Detect ID base per column to avoid mixed-table off-by-one shifts.
    # BOM in this project often uses machine=0-based, material=1-based.
    machine_vals = pd.to_numeric(df.iloc[:, 0], errors="coerce").dropna().astype(int)
    material_vals = pd.to_numeric(df.iloc[:, 1], errors="coerce").dropna().astype(int)
    machine_base = 0 if (machine_vals == 0).any() else 1
    material_base = 0 if (material_vals == 0).any() else 1

    for row in df.itertuples(index=False):
        if len(row) < 2:
            continue
        machine_id = _normalize_id_with_base(row[0], machines, machine_base)
        material_id = _normalize_id_with_base(row[1], materials, material_base)
        if machine_id is None or material_id is None:
            continue

        has_requirement = True
        if len(row) > 2:
            tail = row[2:]
            has_requirement = any(
                (val is not None) and (not (isinstance(val, float) and np.isnan(val))) and (val > 0)
                for val in tail
            )
        if has_requirement:
            bom_matrix[machine_id, material_id] = True

    return bom_matrix


def load_supply_matrix(path: Path, materials: int, days: int) -> np.ndarray:
    df = _read_table(path)
    supply_matrix = np.zeros((materials, days), dtype=float)

    for row in df.itertuples(index=False):
        if len(row) == 0:
            continue
        material_id = _normalize_id(row[0], materials)
        if material_id is None:
            continue

        for day in range(days):
            col_idx = day + 1
            if col_idx >= len(row):
                break
            value = row[col_idx]
            if value is None or (isinstance(value, float) and np.isnan(value)):
                continue
            supply_matrix[material_id, day] = float(value)

    return supply_matrix


def load_production_data(
    base_dir: Optional[Path] = None,
    bom_path: Optional[Path] = None,
    supply_path: Optional[Path] = None,
    machine_weights: Optional[Sequence[float]] = None,
    machines: int = 22,
    materials: int = 156,
    days: int = 31,
    fallback: bool = True,
) -> ProductionData:
    if base_dir is None:
        base_dir = Path(__file__).resolve().parent

    if bom_path is None:
        bom_path = _resolve_existing(base_dir, DEFAULT_BOM_CANDIDATES)
    if supply_path is None:
        supply_path = _resolve_existing(base_dir, DEFAULT_SUPPLY_CANDIDATES)

    if bom_path is None or supply_path is None:
        if not fallback:
            raise FileNotFoundError("BOM or supply file not found.")
        return _create_fallback_data(machines, materials, days)

    try:
        bom_matrix = load_bom_matrix(bom_path, machines, materials)
        supply_matrix = load_supply_matrix(supply_path, materials, days)
        weights = _resolve_machine_weights(machine_weights, machines)
        return ProductionData(
            machines=machines,
            materials=materials,
            days=days,
            bom_matrix=bom_matrix,
            supply_matrix=supply_matrix,
            machine_weights=weights,
            bom_path=bom_path,
            supply_path=supply_path,
        )
    except Exception:
        if not fallback:
            raise
        return _create_fallback_data(machines, materials, days)


def _create_fallback_data(machines: int, materials: int, days: int) -> ProductionData:
    rng = np.random.default_rng()
    bom_matrix = np.zeros((machines, materials), dtype=bool)
    for machine in range(machines):
        if materials <= 0:
            continue
        upper = max(1, min(int(materials), 30))
        lower = max(1, min(10, upper))
        num_materials = int(rng.integers(lower, upper + 1))
        num_materials = min(num_materials, int(materials))
        material_indices = rng.choice(int(materials), size=num_materials, replace=False)
        bom_matrix[machine, material_indices] = True

    supply_matrix = np.zeros((materials, days), dtype=float)
    for material in range(materials):
        supply_matrix[material, 0] = int(rng.integers(5000, 20001))
        for day in range(1, days):
            base_supply = int(rng.integers(100, 1001))
            if day % 7 == 1:
                base_supply *= 3
            supply_matrix[material, day] = base_supply

    return ProductionData(
        machines=machines,
        materials=materials,
        days=days,
        bom_matrix=bom_matrix,
        supply_matrix=supply_matrix,
        machine_weights=_resolve_machine_weights(None, machines),
        bom_path=None,
        supply_path=None,
    )


def _resolve_machine_weights(
    machine_weights: Optional[Sequence[float]],
    machines: int,
) -> np.ndarray:
    if machine_weights is not None:
        weights = np.asarray(machine_weights, dtype=float)
        if weights.size == machines:
            return weights
    if DEFAULT_MACHINE_WEIGHTS.size == machines:
        return DEFAULT_MACHINE_WEIGHTS.copy()
    return np.ones(machines, dtype=float)
