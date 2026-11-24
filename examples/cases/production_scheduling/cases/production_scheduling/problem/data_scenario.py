"""Explicit in-memory production data supplied at the canonical assembly boundary."""

from __future__ import annotations

import hashlib
from typing import Mapping

import numpy as np

from refactor_data import ProductionData


def build_scenario_data(scenario: Mapping, *, machines: int, materials: int, days: int) -> ProductionData:
    if not isinstance(scenario, Mapping):
        raise TypeError("production scenario must be a mapping")
    if set(scenario).difference({"schema", "bom_matrix", "supply_matrix", "machine_weights"}):
        raise ValueError("production scenario contains unsupported fields")
    if scenario.get("schema") != "production_scheduling.scenario/v1":
        raise ValueError("unsupported production scenario schema")
    bom = np.asarray(scenario["bom_matrix"], dtype=float)
    supply = np.asarray(scenario["supply_matrix"], dtype=float)
    weights = np.asarray(scenario.get("machine_weights", np.ones(machines)), dtype=float)
    if bom.shape != (machines, materials) or supply.shape != (materials, days):
        raise ValueError("production scenario matrix shape disagrees with declared dimensions")
    if weights.shape != (machines,):
        raise ValueError("production scenario machine_weights shape disagrees with machines")
    if not all(np.all(np.isfinite(value)) for value in (bom, supply, weights)):
        raise ValueError("production scenario values must be finite")
    if np.any(supply < 0) or np.any(weights < 0) or np.any((bom != 0) & (bom != 1)):
        raise ValueError("production scenario requires nonnegative supply/weights and a binary BOM")
    return ProductionData(
        machines=machines, materials=materials, days=days,
        bom_matrix=np.array(bom, dtype=bool, copy=True),
        supply_matrix=np.array(supply, dtype=float, copy=True),
        machine_weights=np.array(weights, dtype=float, copy=True),
        bom_path=None, supply_path=None,
    )


def scenario_cache_key(scenario: Mapping | None) -> str | None:
    if scenario is None:
        return None
    digest = hashlib.sha256()
    digest.update(str(scenario.get("schema")).encode("utf-8"))
    digest.update(repr(sorted(scenario.keys())).encode("utf-8"))
    for name in ("bom_matrix", "supply_matrix", "machine_weights"):
        value = scenario.get(name)
        digest.update(name.encode("ascii") + b"\0")
        if value is not None:
            array = np.asarray(value, dtype="<f8")
            digest.update(str(array.shape).encode("ascii") + b"\0" + array.tobytes(order="C"))
    return digest.hexdigest()
