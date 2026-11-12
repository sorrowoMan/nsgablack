"""Business invariants for the production Case's candidate operators."""
from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

import numpy as np
import pytest

from nsgablack.context_keys import KEY_MUTATION_SIGMA, KEY_VNS_K


path = Path(__file__).resolve().parents[1] / 'examples/cases/production_scheduling/cases/production_scheduling/pipeline/neighborhood_search.py'
spec = spec_from_file_location('production_schedule_neighborhood_test_module', path)
operators = module_from_spec(spec)
sys.modules[spec.name] = operators
spec.loader.exec_module(operators)


def geometry():
    return operators.ScheduleGeometry(
        np.array([[1, 0], [0, 1], [1, 1]], dtype=bool),
        np.array([[500, 100, 100, 100], [300, 100, 100, 100]], dtype=float),
        max_active=2, min_active=2, max_quantity=500, min_quantity=50)


def test_bounded_retry_preserves_feasibility_input_and_rng_replay():
    g = geometry()
    x = operators.ConstructiveScheduleInitializer(g, seed=12).initialize(None)
    original = x.copy()
    mover = operators.ScheduleNeighborhoodMutation(g, seed=33, attempts=4)
    state = mover.get_state()
    proposals = [mover.mutate(x) for _ in range(20)]
    assert all(operators.MinimalScheduleRepair(g).validate(y) for y in proposals)
    np.testing.assert_array_equal(x, original)
    mover.set_state(state)
    for expected in proposals:
        np.testing.assert_array_equal(mover.mutate(x), expected)
    with pytest.raises(ValueError, match="different business inputs"):
        operators.ScheduleNeighborhoodMutation(g).set_state(state)


def test_no_feasible_move_terminates_after_bounded_attempts(monkeypatch):
    mover = operators.ScheduleNeighborhoodMutation(geometry(), attempts=4)
    calls = []
    for name in ("_balance", "_fill", "_substitute"):
        monkeypatch.setattr(mover, name, lambda *args: calls.append(1))
    x = np.zeros(12)
    np.testing.assert_array_equal(mover.mutate(x), x)
    assert len(calls) == 4


def test_retry_stops_after_first_changed_proposal(monkeypatch):
    mover = operators.ScheduleNeighborhoodMutation(geometry(), attempts=4)
    calls = []
    def change(schedule, fraction):
        calls.append(1)
        schedule[0, 0] += 1
    for name in ("_balance", "_fill", "_substitute"):
        monkeypatch.setattr(mover, name, change)
    assert mover.mutate(np.zeros(12))[0] == 1
    assert len(calls) == 1


def test_feasible_integer_plan_is_fixed_point_and_soft_minima_are_preserved():
    g = geometry()
    repair = operators.MinimalScheduleRepair(g)
    # One active type and a 10-unit lot are permitted by the existing soft
    # minimum contract. Repair cannot silently turn those preferences hard.
    candidate = np.array([[10, 50, 0, 0], [0, 0, 100, 50], [0, 0, 0, 0]], dtype=float).ravel()
    original = candidate.copy()
    assert repair.validate(candidate)
    repaired = repair.repair(candidate)
    np.testing.assert_array_equal(repaired, original)
    np.testing.assert_array_equal(candidate, original)
    assert not np.shares_memory(candidate, repaired)


def test_repair_is_idempotent_without_stock_forgiveness_or_extra_slots():
    g = geometry()
    repair = operators.MinimalScheduleRepair(g)
    invalid = np.full(g.machines * g.days, 1000.7)
    once = repair.repair(invalid)
    assert repair.validate(once)
    assert np.min(g.balances(once.reshape(g.machines, g.days))) >= 0
    np.testing.assert_array_equal(repair.repair(once), once)
    assert np.max(np.sum(once.reshape(g.machines, g.days) > 0, axis=0)) <= 2


def test_constructor_and_neighbor_batches_preserve_real_inventory_constraints():
    g = geometry()
    initializer = operators.ConstructiveScheduleInitializer(g, seed=12)
    mutator = operators.ScheduleNeighborhoodMutation(g, seed=33)
    repair = operators.MinimalScheduleRepair(g)
    current = initializer.initialize(None)
    assert repair.validate(current)
    assert np.sum(current) > 0
    for _ in range(40):
        original = current.copy()
        proposed = mutator.mutate(current, {KEY_VNS_K: 3, KEY_MUTATION_SIGMA: 0.5})
        np.testing.assert_array_equal(current, original)
        assert repair.validate(proposed)
        np.testing.assert_array_equal(proposed, repair.repair(proposed))
        current = proposed


def test_rng_restore_replays_the_same_next_proposal_without_reinitializing():
    g = geometry()
    initializer = operators.ConstructiveScheduleInitializer(g, seed=41)
    initial_state = initializer.get_state()
    first = initializer.initialize(None)
    initializer.set_state(initial_state)
    np.testing.assert_array_equal(first, initializer.initialize(None))
    mutator = operators.ScheduleNeighborhoodMutation(g, seed=100)
    state = mutator.get_state()
    proposal = mutator.mutate(first)
    mutator.set_state(state)
    np.testing.assert_array_equal(proposal, mutator.mutate(first))
    wrong_geometry = operators.ScheduleGeometry(g.bom, g.supply + 1, 2, 2, 500, 50)
    with pytest.raises(ValueError, match='different business inputs'):
        operators.ScheduleNeighborhoodMutation(wrong_geometry).set_state(state)


def test_moving_production_before_material_arrival_is_rejected_by_neighborhood():
    g = operators.ScheduleGeometry(np.array([[True]]), np.array([[0, 0, 500]], dtype=float),
                                   max_active=1, min_active=1, max_quantity=500, min_quantity=50)
    candidate = np.array([0, 0, 400], dtype=float)
    mutator = operators.ScheduleNeighborhoodMutation(g, seed=5)
    # Earlier daily totals are lower, but their prefix stocks have no supply.
    for _ in range(10):
        schedule = candidate.reshape(1, 3).copy()
        mutator._balance(schedule, 1.0)
        np.testing.assert_array_equal(schedule.ravel(), candidate)


def test_balance_changes_days_conserves_output_and_improves_variance():
    g = operators.ScheduleGeometry(np.array([[True]]), np.array([[500, 0, 0]], dtype=float),
                                   max_active=1, min_active=1, max_quantity=500, min_quantity=50)
    schedule = np.array([[0, 0, 400]], dtype=float)
    before = schedule.copy()
    mutator = operators.ScheduleNeighborhoodMutation(g, seed=5)
    mutator._balance(schedule, 1.0)
    assert schedule.sum() == before.sum()
    assert np.var(schedule.sum(axis=0)) < np.var(before.sum(axis=0))
    assert operators.MinimalScheduleRepair(g).validate(schedule.ravel())


def test_coverage_is_a_constructive_move_and_does_not_harden_repair():
    g = geometry()
    schedule = np.array([[100, 100, 100, 100], [0, 0, 0, 0], [0, 0, 0, 0]], dtype=float)
    original = schedule.copy()
    repair = operators.MinimalScheduleRepair(g)
    # A feasible under-covered plan remains untouched by repair.
    np.testing.assert_array_equal(repair.repair(schedule.ravel()), original.ravel())
    mutator = operators.ScheduleNeighborhoodMutation(g, seed=5)
    mutator._coverage(schedule)
    assert np.min(np.sum(schedule > 0, axis=0)) == 2
    assert repair.validate(schedule.ravel())


def test_balance_does_not_create_fragments_when_preserving_the_donor_lot():
    g = operators.ScheduleGeometry(np.array([[True]]), np.array([[60, 0, 0]], dtype=float),
                                   max_active=1, min_active=1, max_quantity=500, min_quantity=50)
    schedule = np.array([[0, 0, 60]], dtype=float)
    mutator = operators.ScheduleNeighborhoodMutation(g, seed=7)
    for _ in range(3):
        mutator._balance(schedule, 1.0)
    assert np.all((schedule == 0) | (schedule >= 50))
