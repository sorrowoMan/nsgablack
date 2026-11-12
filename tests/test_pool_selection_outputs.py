"""One survivor decision can also publish exact named candidate collections."""
from functools import partial

import numpy as np
import pytest

from nsgablack.adapters import NSGA2Adapter, NSGA3Adapter, SPEA2Adapter, partition
from nsgablack.adapters.change_pool import ChangePool
from .test_ga_pool_workflow import make_ga, keep_first, keep_last, assert_manifest


def first_objective(pool):
    return pool.objectives[:, 0]


def retain_old_with_elite_and_reserve(pool):
    members, remaining = partition(pool, by=keep_first)
    return members, {"elite": members.top(1, key=first_objective), "reserve": remaining}


def retain_new_with_elite(pool):
    members = pool.take(range(len(pool) - 4, len(pool)))
    return members, {"elite": members.take((0,)), "reserve": pool.take(())}


def repeated_auxiliary_members(pool):
    return keep_first(pool), {"elite": pool.take((0, 0, 1, 0)), "reserve": pool.take(())}


def output_to_name(pool, *, name):
    return keep_first(pool), {name: pool.take((0,))}


def failing_user_choose(pool):
    raise TypeError("internal selection calculation failed")


def bad_selection_output(pool, *, case):
    members = keep_first(pool)
    if case == "name-empty":
        return members, {"": members}
    if case == "name-blank":
        return members, {"   ": members}
    if case == "name-number":
        return members, {17: members}
    if case == "mapping-list":
        return members, [("reserve", members)]
    if case == "mapping-none":
        return members, None
    if case == "value-refs":
        return members, {"reserve": members.refs}
    if case == "value-array":
        return members, {"reserve": members.values}
    if case == "main-indices":
        return (0, 1, 2, 3), {"reserve": members}
    if case == "main-count":
        return members.take((0, 1, 2)), {"reserve": members}
    if case == "main-repeat":
        return members.take((0, 0, 1, 2)), {"reserve": members}
    if case == "aux-new-root":
        return members, {"reserve": pool._scope.read(pool.refs[:1])}
    if case == "main-new-root":
        return pool._scope.read(members.refs), {"reserve": members}
    if case == "aux-foreign-scope":
        other = ChangePool(pool._scope._pool, accepted_refs=pool.refs)
        return members, {"reserve": other.read(pool.refs[:1])}
    raise AssertionError("unknown test case")


@pytest.mark.parametrize("cls", [NSGA2Adapter, NSGA3Adapter, SPEA2Adapter])
def test_one_choose_keeps_algorithm_members_and_archives_only_its_selected_elite(cls, monkeypatch):
    solver, adapter = make_ga(cls, selector=retain_old_with_elite_and_reserve, maintenance=None)
    calls = []
    operation = adapter.get_bound_selector()
    choose = operation.select

    def record(request, *, rng):
        pool = request.pool
        result = choose(request, rng=rng)
        calls.append((pool.refs, result[0].refs,
                      {name: value.refs for name, value in result[1].items()}))
        return result

    # Instrument the bridge, leaving the bound function identity unchanged.
    monkeypatch.setattr(operation, "select", record)
    assert solver.step().committed
    parents = adapter.get_population_solution_refs(solver)
    first_reserve = solver.solution_pool.subpool_descriptor("reserve")
    assert solver.solution_pool.subpool_refs("reserve") == ()
    assert solver.step().committed

    assert len(calls) == 2
    offered, selected, auxiliary = calls[-1]
    assert offered[:4] == selected == parents
    assert adapter.get_population_solution_refs(solver) == parents
    elite = solver.solution_pool.subpool_refs("elite")
    reserve = solver.solution_pool.subpool_refs("reserve")
    assert elite == auxiliary["elite"] == parents[:1]
    assert reserve == auxiliary["reserve"] == offered[4:]
    assert set(elite).issubset(selected)
    assert set(reserve).isdisjoint(selected)
    # These children dominate the deliberately retained old members. The named
    # elite is derived from the actual survivor choice, not another archive rank.
    old_f = np.asarray(solver.solution_pool.read_raw_feedback(parents)[0])
    new_f = np.asarray(solver.solution_pool.read_raw_feedback(reserve)[0])
    assert np.max(new_f[:, 0]) < np.min(old_f[:, 0])
    assert solver.evaluation_count == len(solver.problem.calls) == 8
    descriptor = solver.solution_pool.subpool_descriptor("reserve")
    assert solver.solution_pool.subpool_metadata("reserve")["kind"] == "candidate_collection"
    assert descriptor["view_id"] == first_reserve["view_id"]
    assert descriptor["revision"] == first_reserve["revision"] + 1
    assert_manifest(solver)


def test_existing_named_result_replaces_exactly_and_keeps_collection_identity():
    solver, adapter = make_ga(selector=retain_new_with_elite, maintenance=None)
    assert solver.step().committed
    before = solver.solution_pool.subpool_descriptor("elite")
    old = solver.solution_pool.subpool_refs("elite")
    assert solver.step().committed
    members = adapter.get_population_solution_refs(solver)
    assert solver.solution_pool.subpool_refs("elite") == members[:1]
    assert set(old).isdisjoint(members)
    after = solver.solution_pool.subpool_descriptor("elite")
    assert after["view_id"] == before["view_id"]
    assert after["revision"] == before["revision"] + 1
    assert solver.solution_pool.subpool_refs("reserve") == ()
    assert_manifest(solver)


def test_auxiliary_collection_preserves_explicit_repeated_coordinates_and_empty_result():
    solver, adapter = make_ga(selector=repeated_auxiliary_members, maintenance=None)
    assert solver.step().committed
    members = adapter.get_population_solution_refs(solver)
    assert solver.solution_pool.subpool_refs("elite") == (members[0], members[0], members[1], members[0])
    assert solver.solution_pool.has_subpool("reserve")
    assert solver.solution_pool.subpool_refs("reserve") == ()
    assert_manifest(solver)


@pytest.mark.parametrize("case", [
    "name-empty", "name-blank", "name-number", "mapping-list", "mapping-none",
    "value-refs", "value-array", "main-indices", "main-count", "main-repeat",
    "aux-new-root", "main-new-root", "aux-foreign-scope",
])
def test_invalid_primary_or_named_result_does_not_publish_partial_collections(case):
    solver, adapter = make_ga(selector=partial(bad_selection_output, case=case), maintenance=None)
    before = solver.solution_pool.subpool_descriptor("elite")
    with pytest.raises((TypeError, ValueError)):
        solver.step()
    assert solver.solution_pool.subpool_descriptor("elite") == before
    assert solver.solution_pool.subpool_refs("elite") == ()
    assert not solver.solution_pool.has_subpool("reserve")
    assert solver.evaluation_count == len(solver.problem.calls) == 4


def test_named_views_are_detached_before_scope_ends_and_publish_only_at_commit(monkeypatch):
    solver, adapter = make_ga(selector=retain_old_with_elite_and_reserve, maintenance=None)
    operation = adapter.get_bound_selector()
    choose = operation.select
    retained = []

    def record(request, *, rng):
        pool = request.pool
        result = choose(request, rng=rng)
        assert not solver.solution_pool.has_subpool("reserve")
        assert solver.solution_pool.subpool_refs("elite") == ()
        retained.extend((pool, result[0], *result[1].values()))
        return result

    monkeypatch.setattr(operation, "select", record)
    assert solver.step().committed
    assert solver.solution_pool.has_subpool("reserve")
    assert len(solver.solution_pool.subpool_refs("elite")) == 1
    for view in retained:
        with pytest.raises(RuntimeError, match="ended"):
            view.values


def test_old_pool_only_return_remains_a_survivor_rule_without_named_outputs():
    solver, adapter = make_ga(selector=keep_last, maintenance=None)
    assert solver.step().committed
    old = adapter.get_population_solution_refs(solver)
    assert solver.step().committed
    assert set(adapter.get_population_solution_refs(solver)).isdisjoint(old)
    assert solver.solution_pool.subpool_refs("elite") == ()
    assert not solver.solution_pool.has_subpool("reserve")


def test_named_selection_cannot_replace_an_algorithm_owned_view():
    solver, adapter = make_ga(selector=keep_first, maintenance=None)
    assert solver.step().committed
    members = adapter.get_population_solution_refs(solver)
    solver.solution_pool.publish_subpool_view("algorithm-owned", members, created_by=("owner",))
    descriptor = solver.solution_pool.subpool_descriptor("algorithm-owned")
    adapter.set_selector(partial(output_to_name, name="algorithm-owned"))
    with pytest.raises(ValueError, match="ordinary candidate_collection"):
        solver.step()
    assert solver.solution_pool.subpool_descriptor("algorithm-owned") == descriptor
    assert solver.solution_pool.subpool_refs("algorithm-owned") == members
    assert adapter.get_population_solution_refs(solver) == members


def test_selector_typeerror_is_not_retried_and_cannot_publish_named_results(monkeypatch):
    solver, adapter = make_ga(selector=failing_user_choose, maintenance=None)
    calls = []
    operation = adapter.get_bound_selector()
    choose = operation.select

    def fail(request, *, rng):
        calls.append(request.pool.refs)
        return choose(request, rng=rng)

    monkeypatch.setattr(operation, "select", fail)
    with pytest.raises(TypeError, match="internal selection calculation failed"):
        solver.step()
    assert len(calls) == 1
    assert solver.solution_pool.subpool_refs("elite") == ()
    assert not solver.solution_pool.has_subpool("reserve")
