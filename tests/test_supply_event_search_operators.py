"""Domain search preserves per-event moves without a short-gap cap preference."""

from __future__ import annotations

import importlib
from pathlib import Path
import random

import numpy as np
import pytest

from blackbase.project import case_import_context
from nsgablack.context_keys import KEY_PROBLEM


PROJECT = Path(__file__).resolve().parents[1] / "examples/cases/supply_adjustment_nested"


@pytest.fixture
def components():
    with case_import_context(PROJECT, "supply_adjustment_nested"):
        problem_type = importlib.import_module("problem").SupplyEventShiftProblem
        operators = importlib.import_module("pipeline.event_operators")
        main = importlib.import_module("pipeline.main")
    return problem_type, operators, main


def make_problem(components, *, cap=3, quantities=(20, 40, 60, 80)):
    supply = np.zeros((len(quantities), 31))
    supply[:, 0] = np.arange(len(quantities)) + 100
    supply[0, 1] = 11
    supply[:, 30] = quantities
    return components[0](base_supply=supply, bom_matrix=np.ones((1, len(quantities))),
                         production_case_dir=PROJECT, max_moved_events=cap)


def assert_legal_and_conserved(problem, candidate):
    shifts = problem.decode_shifts(candidate)
    np.testing.assert_array_equal(candidate, shifts)
    assert np.count_nonzero(shifts) <= (problem.max_moved_events or problem.dimension)
    adjusted = problem.apply_shifts(shifts)
    np.testing.assert_array_equal(adjusted[:, 0], problem.base_supply[:, 0])
    np.testing.assert_allclose(adjusted.sum(axis=1), problem.base_supply.sum(axis=1))
    assert np.min(adjusted) >= 0


def test_cap_keeps_legal_sparse_values_and_whole_events(components):
    problem = make_problem(components)
    candidate = np.array([0, 1, 0, 12, 25])
    assert_legal_and_conserved(problem, candidate)
    shifted = problem.apply_shifts(candidate)
    assert shifted[2, 18] == 60
    assert shifted[3, 5] == 80
    assert shifted[2, 30] == shifted[3, 30] == 0


def test_cap_is_deterministic_idempotent_and_quantity_independent(components, monkeypatch):
    problem = make_problem(components, cap=2)
    other = make_problem(components, cap=2, quantities=(8000, 6, 700, 2))
    candidate = np.array([0, 1, 7, 17, 29])
    original = candidate.copy()

    def forbidden_rng(*args, **kwargs):
        raise AssertionError("repair must not consume RNG")

    monkeypatch.setattr(np.random, "default_rng", forbidden_rng)
    monkeypatch.setattr(np.random, "choice", forbidden_rng)
    monkeypatch.setattr(random, "sample", forbidden_rng)
    first = problem.decode_shifts(candidate)
    np.testing.assert_array_equal(first, problem.decode_shifts(candidate))
    np.testing.assert_array_equal(first, problem.decode_shifts(first))
    np.testing.assert_array_equal(first, other.decode_shifts(candidate))
    np.testing.assert_array_equal(candidate, original)
    assert np.count_nonzero(first) == 2
    assert np.all((first == 0) | (first == candidate))


def test_cap_does_not_systematically_keep_the_shortest_or_longest_gap(components):
    problem = make_problem(components, cap=1, quantities=tuple(range(1, 13)))
    rng = np.random.default_rng(1704)
    kept_gaps = set()
    for _ in range(160):
        candidate = np.r_[0, rng.permutation(np.arange(1, 13))]
        projected = problem.decode_shifts(candidate)
        kept_gaps.add(int(projected.max()))
    # The former minimum-gap ranking always returned 1; a maximum-gap ranking
    # would always return 12. A fixed corpus covers both extremes and the middle.
    assert kept_gaps == set(range(1, 13))


def test_initializer_samples_sparse_independent_multi_day_events(components):
    problem = make_problem(components)
    initializer = components[1].SupplyEventInitializer(seed=91)
    counts, days = set(), set()
    saw_different_days = False
    for _ in range(160):
        candidate = initializer.initialize(problem)
        assert_legal_and_conserved(problem, candidate)
        assert candidate[0] == 0
        moved = candidate[candidate > 0]
        counts.add(len(moved))
        days.update(int(day) for day in moved)
        saw_different_days |= len(set(moved)) > 1
    assert counts == {0, 1, 2, 3}
    assert 1 in days and 29 in days and saw_different_days


def test_mutator_can_add_remove_change_date_and_swap_members_at_capacity(components):
    problem = make_problem(components)
    mutator = components[1].SupplyEventMutation(problem, seed=381)
    for parent in (np.array([0, 2, 14, 0, 0]), np.array([0, 2, 14, 20, 0])):
        original = parent.copy()
        observed = set()
        for _ in range(160):
            child = mutator.mutate(parent)
            assert_legal_and_conserved(problem, child)
            np.testing.assert_array_equal(parent, original)
            before, after = parent > 0, child > 0
            delta = np.count_nonzero(after) - np.count_nonzero(before)
            if delta > 0:
                observed.add("add")
            elif delta < 0:
                observed.add("remove")
            elif np.array_equal(before, after):
                observed.add("date")
            else:
                observed.add("swap")
            assert np.count_nonzero(parent != child) in (1, 2)
        expected = {"date", "remove", "swap"}
        if np.count_nonzero(parent) < problem.max_moved_events:
            expected.add("add")
        assert observed == expected


def test_date_mutation_can_reach_both_near_and_full_range_days(components):
    problem = make_problem(components, cap=1, quantities=(100,))
    mutator = components[1].SupplyEventMutation(problem, seed=881)
    days = {int(mutator.mutate([0, 15])[1]) for _ in range(300)}
    assert {0, 1, 14, 16, 29} <= days


def test_pipeline_seed_replay_is_independent_of_global_rng(components):
    problem = make_problem(components)
    pipeline = components[2].build_pipeline(problem)
    numpy_state, python_state = np.random.get_state(), random.getstate()

    def replay():
        pipeline.set_random_seed(424242)
        output = []
        for _ in range(8):
            parent = pipeline.init({KEY_PROBLEM: problem})
            child = pipeline.repair(pipeline.mutate(parent))
            output.append((parent.copy(), child.copy()))
        return output

    first, second = replay(), replay()
    for (parent1, child1), (parent2, child2) in zip(first, second):
        np.testing.assert_array_equal(parent1, parent2)
        np.testing.assert_array_equal(child1, child2)
    current = np.random.get_state()
    assert current[0] == numpy_state[0] and current[2:] == numpy_state[2:]
    np.testing.assert_array_equal(current[1], numpy_state[1])
    assert random.getstate() == python_state


def test_mutation_leaves_crossover_draft_repair_to_the_pipeline(components):
    problem = make_problem(components, cap=2)
    pipeline = components[2].build_pipeline(problem)
    pipeline.set_random_seed(19)
    draft = np.array([0, 1.25, 2.25, 3.25, 4.25])
    proposal = pipeline.mutate(draft)
    assert np.count_nonzero(proposal != draft) <= 2
    assert np.any(proposal != np.rint(proposal))
    repaired = pipeline.repair(proposal)
    assert_legal_and_conserved(problem, repaired)
    np.testing.assert_array_equal(draft, [0, 1.25, 2.25, 3.25, 4.25])


def test_fixed_candidate_path_and_empty_event_geometry_still_work(components):
    problem = make_problem(components)
    candidate = np.array([0, 2, 7, 0, 0])
    pipeline = components[2].build_pipeline(problem, candidate=candidate)
    candidate[:] = 0
    np.testing.assert_array_equal(pipeline.init({KEY_PROBLEM: problem}), [0, 2, 7, 0, 0])
    pipeline.initializer.set_candidate([0, 0, 0, 0, 25])
    np.testing.assert_array_equal(pipeline.init({KEY_PROBLEM: problem}), [0, 0, 0, 0, 25])
    empty = components[0](base_supply=np.array([[100]]), bom_matrix=np.ones((1, 1)),
                          production_case_dir=PROJECT)
    empty_pipeline = components[2].build_pipeline(empty)
    assert empty_pipeline.init({KEY_PROBLEM: empty}).shape == (0,)
    assert empty_pipeline.mutate(np.empty(0)).shape == (0,)


def test_local_step_days_and_legacy_sigma_alias_are_explicit(components):
    problem = make_problem(components)
    build = components[2].build_pipeline
    assert build(problem, local_step_days=3).mutator.local_step_days == 3
    assert build(problem, mutation_sigma=2.0).mutator.local_step_days == 2
    with pytest.raises(ValueError, match="integer-day alias"):
        build(problem, mutation_sigma=.5)
    with pytest.raises(ValueError, match="not both"):
        build(problem, local_step_days=1, mutation_sigma=2)
    with pytest.raises(ValueError, match="positive integer"):
        build(problem, local_step_days=1.5)
