"""Selection may reuse stock reads only before that day's allocations start."""
import importlib.util
from pathlib import Path
import sys
import numpy as np
import pytest


@pytest.fixture
def repair_types(monkeypatch):
    path = Path(__file__).resolve().parents[1] / "examples/cases/production_scheduling/cases/production_scheduling/pipeline/schedule_pipeline.py"
    spec = importlib.util.spec_from_file_location("repair_availability_test", path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


def legacy_selector(repair):
    cap = float(repair.base_repair.max_production_per_machine)
    def select(stock, requirements):
        return lambda m: cap if requirements[m].size == 0 else float(np.min(stock[requirements[m]]))
    return select


def compare(repair, candidate):
    state = np.random.get_state()
    original = repair._selection_availability
    native = repair.repair(candidate)
    native_rng = np.random.get_state()
    np.random.set_state(state)
    repair._selection_availability = legacy_selector(repair)
    try:
        legacy = repair.repair(candidate)
    finally:
        repair._selection_availability = original
    legacy_rng = np.random.get_state()
    np.testing.assert_array_equal(native, legacy)
    assert native_rng[0] == legacy_rng[0] and native_rng[2:] == legacy_rng[2:]
    np.testing.assert_array_equal(native_rng[1], legacy_rng[1])
    return native


@pytest.mark.parametrize("seed", [1, 17, 42])
@pytest.mark.parametrize("density,supply_scale", [(0., 0.), (.3, 2.), (.9, 30.), (1., 400.)])
def test_repair_keeps_exact_schedule_and_rng_with_sparse_dense_and_scarce_stock(repair_types, seed, density, supply_scale):
    rng = np.random.default_rng(seed)
    machines, days, materials = 5, 7, 8
    bom = rng.random((machines, materials)) < density
    supply = rng.integers(0, 5, (materials, days)).astype(float) * supply_scale
    base = repair_types.ProductionScheduleRepair(machines, days, 2, 3, 20, 100)
    repair = repair_types.SupplyAwareScheduleRepair(machines, days, 20, bom, supply, base)
    candidate = rng.integers(0, 200, machines*days).astype(float)
    compare(repair, candidate)
    # A new call must observe changed input/configuration, not a previous day's cache.
    repair.supply_matrix[:, 1:] += 3
    repair.bom_matrix[0] = ~repair.bom_matrix[0]
    compare(repair, candidate[::-1])


def test_scarce_stock_selection_reduces_actual_minimum_kernel_calls(repair_types, monkeypatch):
    machines, days, materials = 5, 7, 8
    base = repair_types.ProductionScheduleRepair(machines, days, 2, 3, 100, 300)
    repair = repair_types.SupplyAwareScheduleRepair(machines, days, 100,
        np.ones((machines, materials), dtype=bool), np.zeros((materials, days)), base)
    original_min = np.min
    calls = []
    def counted(*args, **kwargs):
        calls.append(1)
        return original_min(*args, **kwargs)
    monkeypatch.setattr(np, "min", counted)
    candidate = np.zeros(machines*days)
    native = repair.repair(candidate)
    native_calls = len(calls)
    calls.clear()
    repair._selection_availability = legacy_selector(repair)
    legacy = repair.repair(candidate)
    assert native_calls < len(calls)
    np.testing.assert_array_equal(native, legacy)
