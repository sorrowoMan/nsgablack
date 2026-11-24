"""Partition current occurrences, then return views in the caller's coordinates."""
from functools import partial

import numpy as np
import pytest

from nsgablack.adapters import partition
from nsgablack.adapters.change_pool import ChangePool
from nsgablack.adapters.selection_pool import offered_pool, pool_selection_indices
from .test_pool_survivor_selection import make_control, put


def choose_first(pool):
    return pool.take((0,))


def choose_last(pool):
    return pool.take((len(pool) - 1,))


def choose_random_two(pool, *, rng):
    return pool.sample(2, rng=rng)


async def asynchronous_choose(pool):
    return pool


def generator_choose(pool):
    yield pool


class SynchronousChoose:
    def __init__(self):
        self.calls = 0

    def __call__(self, pool):
        self.calls += 1
        return pool.take((1,))


class AsynchronousChoose:
    async def __call__(self, pool):
        return pool


class GeneratorChoose:
    def __call__(self, pool):
        yield pool


def test_repeated_reference_complement_removes_only_the_selected_occurrence():
    control = make_control()
    x, y = put(control, (1., 2.), tokens=("x", "y"))
    scope = ChangePool(control.solution_pool)
    source = scope.read((x, y, x))
    selected, remaining = partition(source, by=choose_first)
    assert selected.refs == (x,) and remaining.refs == (y, x)
    assert source.difference(selected).refs == (y,)  # Identity difference stays distinct.
    assert source.refs == (x, y, x)
    assert len(selected) + len(remaining) == len(source)
    assert scope.used_refs == ()


def test_repeated_old_root_position_is_rebased_at_this_selection_boundary():
    control = make_control()
    x, y = put(control, (1., 2.), tokens=("x", "y"))
    scope = ChangePool(control.solution_pool)
    original = scope.read((x, y))
    source = original.take((0, 1, 0))
    selected, remaining = partition(source, by=choose_last)
    assert selected.refs == (x,) and remaining.refs == (x, y)
    assert pool_selection_indices(original, selected) == (0,)
    assert pool_selection_indices(original, remaining) == (0, 1)


def test_selected_order_follows_choose_and_complement_keeps_current_source_order():
    control = make_control()
    refs = put(control)
    scope = ChangePool(control.solution_pool)
    source = scope.read(refs)
    selected, remaining = partition(source, by=lambda pool: pool.take((2, 0)))
    assert selected.refs == (refs[2], refs[0])
    assert remaining.refs == refs[1:2]
    assert selected.concat(remaining).refs != source.refs
    assert pool_selection_indices(source, selected) == (2, 0)


def test_sort_before_partition_preserves_caller_survivor_coordinates_and_feedback():
    control = make_control()
    refs = put(control)
    with offered_pool(control, refs, objectives=[[2.], [3.], [1.]], violations=[0.] * 3) as source:
        sorted_source = source.sort(lambda pool: pool.objectives[:, 0])
        selected, remaining = partition(sorted_source, by=choose_first)
        assert pool_selection_indices(source, selected) == (2,)
        assert pool_selection_indices(source, remaining) == (0, 1)
        np.testing.assert_array_equal(selected.objectives, [[1.]])
        np.testing.assert_array_equal(remaining.objectives, [[2.], [3.]])


def test_nested_partition_and_groups_project_back_one_boundary_at_a_time():
    control = make_control()
    refs = put(control)
    scope = ChangePool(control.solution_pool)
    source = scope.read(refs)

    def choose(pool):
        parts = []
        for group in pool.groups(2):
            selected, _ = partition(group, by=choose_last)
            parts.append(selected)
        return parts[0].concat(*parts[1:])

    selected, remaining = partition(source, by=choose)
    assert selected.refs == (refs[1], refs[2])
    assert remaining.refs == refs[:1]
    assert pool_selection_indices(source, selected) == (1, 2)


def test_rebased_distinct_local_occurrences_cannot_forge_distinct_outer_survivor_slots():
    control = make_control()
    x, y = put(control, (1., 2.), tokens=("x", "y"))
    with offered_pool(control, (x, y), objectives=[[1.], [2.]], violations=[0., 0.]) as original:
        source = original.take((0, 1, 0))
        selected, remaining = partition(source, by=lambda pool: pool.take((0, 2)))
        assert selected.refs == (x, x) and remaining.refs == (y,)
        with pytest.raises(ValueError, match="repeat"):
            pool_selection_indices(original, selected)


@pytest.mark.parametrize("return_kind", ("old", "fresh_read", "foreign", "indices"))
def test_choose_must_return_a_derivative_of_this_temporary_root_and_scope(return_kind):
    control = make_control()
    refs = put(control)
    scope = ChangePool(control.solution_pool)
    source = scope.read(refs)
    foreign = ChangePool(control.solution_pool).read(refs)

    def choose(pool):
        if return_kind == "old":
            return source.take((0,))
        if return_kind == "fresh_read":
            return pool._scope.read(pool.refs[:1])
        if return_kind == "foreign":
            return foreign.take((0,))
        return (0,)

    with pytest.raises((TypeError, ValueError), match="Pool|root|scope|selection|partition"):
        partition(source, by=choose)
    assert source.refs == refs  # Failure cannot close the caller's scope.


def test_repeated_local_position_is_rejected_without_silently_deduplicating():
    control = make_control()
    refs = put(control)
    source = ChangePool(control.solution_pool).read(refs)
    with pytest.raises(ValueError, match="repeat|distinct|duplicate"):
        partition(source, by=lambda pool: pool.take((0, 0)))
    assert source.refs == refs


def test_callback_and_rng_are_consumed_once_per_nonempty_partition():
    control = make_control()
    refs = put(control)
    source = ChangePool(control.solution_pool).read(refs)
    calls = []
    actual = np.random.default_rng(13)
    expected = np.random.default_rng(13)
    indices = expected.choice(3, size=2, replace=False)

    def choose(pool, *, rng):
        calls.append(pool)
        return pool.sample(2, rng=rng)

    selected, remaining = partition(source, by=choose, rng=actual)
    assert len(calls) == 1
    assert selected.refs == tuple(refs[i] for i in indices)
    assert remaining.refs == tuple(ref for i, ref in enumerate(refs) if i not in set(indices))
    assert actual.bit_generator.state == expected.bit_generator.state


def test_missing_required_rng_and_invalid_signature_fail_before_callback():
    control = make_control()
    refs = put(control)
    source = ChangePool(control.solution_pool).read(refs)
    calls = []

    def needs_rng(pool, *, rng):
        calls.append(pool)
        return pool

    with pytest.raises((TypeError, ValueError), match="rng|Generator"):
        partition(source, by=needs_rng)
    assert calls == []

    def missing_argument(pool, required):
        calls.append(pool)
        return pool

    with pytest.raises(TypeError):
        partition(source, by=missing_argument)
    assert calls == []


def test_typeerror_in_callback_propagates_without_retry_and_keeps_parent_scope_open():
    control = make_control()
    refs = put(control)
    source = ChangePool(control.solution_pool).read(refs)
    calls = []

    def failed(pool):
        calls.append(pool)
        raise TypeError("inside partition callback")

    with pytest.raises(TypeError, match="inside partition callback"):
        partition(source, by=failed)
    assert len(calls) == 1 and source.refs == refs


def test_temporary_feedback_is_reordered_readonly_and_kept_distinct_from_raw():
    control = make_control()
    refs = put(control)
    with offered_pool(control, refs, objectives=[[-1.], [-2.], [-3.]], violations=[4., 5., 6.]) as original:
        source = original.take((2, 0, 2))

        def choose(pool):
            np.testing.assert_array_equal(pool.objectives, [[-3.], [-1.], [-3.]])
            np.testing.assert_array_equal(pool.violations, [6., 4., 6.])
            np.testing.assert_array_equal(pool.raw_feedback()[0], [[30.], [10.], [30.]])
            with pytest.raises(ValueError):
                pool.objectives.setflags(write=True)
            with pytest.raises(ValueError):
                pool.values[0, 0] = 99
            return pool.take((2,))

        selected, remaining = partition(source, by=choose)
        np.testing.assert_array_equal(selected.objectives, [[-3.]])
        np.testing.assert_array_equal(remaining.violations, [6., 4.])
        assert remaining.refs == (refs[2], refs[0])


def test_missing_selection_feedback_is_not_invented_from_raw_evaluation():
    control = make_control()
    refs = put(control)
    source = ChangePool(control.solution_pool).read(refs)

    def choose(pool):
        with pytest.raises(ValueError, match="no explicitly supplied"):
            pool.selection_feedback()
        np.testing.assert_array_equal(pool.raw_feedback()[0], [[10.], [20.], [30.]])
        return pool.take((1,))

    selected, remaining = partition(source, by=choose)
    assert selected.refs == refs[1:2]
    with pytest.raises(ValueError, match="no explicitly supplied"):
        remaining.selection_feedback()


@pytest.mark.parametrize("choice", ("all", "none"))
def test_all_and_none_cover_the_input_without_candidate_or_membership_writes(choice, monkeypatch):
    control = make_control()
    refs = put(control)
    store = control.solution_pool
    store.create_subpool("kept", refs)
    before = store.subpool_descriptor("kept")
    scope = ChangePool(store)
    source = scope.subpool("kept")

    def forbidden(*args, **kwargs):
        pytest.fail("partition attempted a value read, candidate write, evaluation or Unit construction")

    for method in ("read", "read_raw_feedback", "put", "create_subpool", "replace_subpool_members"):
        monkeypatch.setattr(store, method, forbidden)
    # A SimpleNamespace control exposes no Solver/evaluation/Unit service.
    selected, remaining = partition(source,
        by=lambda pool: pool.all() if choice == "all" else pool.take(()))
    assert selected.refs == (refs if choice == "all" else ())
    assert remaining.refs == (() if choice == "all" else refs)
    assert store.subpool_descriptor("kept") == before
    assert store.subpool_refs("kept") == refs and scope.used_refs == ()


def test_empty_input_skips_a_valid_callback_and_returns_two_parent_scoped_empty_views():
    control = make_control()
    refs = put(control)
    scope = ChangePool(control.solution_pool)
    source = scope.read(refs).take(())
    calls = []

    def choose(pool):
        calls.append(pool)
        raise AssertionError("empty partition must not invoke choose")

    selected, remaining = partition(source, by=choose)
    assert calls == [] and selected.refs == remaining.refs == ()
    assert scope.used_refs == ()
    scope.close()
    for pool in (selected, remaining):
        with pytest.raises(RuntimeError, match="ended"):
            pool.refs


def test_returned_views_remain_usable_until_outer_scope_ends():
    control = make_control()
    refs = put(control)
    scope = ChangePool(control.solution_pool)
    source = scope.read(refs)
    selected, remaining = partition(source, by=choose_first)
    np.testing.assert_array_equal(selected.values, [[1.]])
    np.testing.assert_array_equal(remaining.values, [[2.], [3.]])
    assert selected.concat(remaining).refs == refs
    scope.close()
    for view in (source, selected, remaining):
        with pytest.raises(RuntimeError, match="ended"):
            view.values


def test_synchronous_callable_instances_and_partial_rules_are_supported():
    control = make_control()
    refs = put(control)
    source = ChangePool(control.solution_pool).read(refs)
    choose = SynchronousChoose()
    selected, remaining = partition(source, by=choose)
    assert choose.calls == 1 and selected.refs == refs[1:2]
    assert remaining.refs == (refs[0], refs[2])

    def positions(pool, *, indices):
        return pool.take(indices)

    selected, remaining = partition(source, by=partial(positions, indices=(2, 0)))
    assert selected.refs == (refs[2], refs[0]) and remaining.refs == refs[1:2]


@pytest.mark.parametrize("choose", (asynchronous_choose, generator_choose,
                                   AsynchronousChoose(), GeneratorChoose(),
                                   partial(asynchronous_choose)))
def test_async_and_generator_rules_are_rejected_without_starting_them(choose):
    control = make_control()
    refs = put(control)
    source = ChangePool(control.solution_pool).read(refs)
    with pytest.raises(TypeError, match="synchronous"):
        partition(source, by=choose)
    assert source.refs == refs


def test_invalid_pool_callback_and_rng_are_rejected_before_calculation():
    control = make_control()
    refs = put(control)
    source = ChangePool(control.solution_pool).read(refs)
    with pytest.raises(TypeError, match="Pool"):
        partition(refs, by=choose_first)
    with pytest.raises(TypeError, match="callable"):
        partition(source, by=None)
    calls = []

    def choose(pool, *, rng):
        calls.append(pool)
        return pool

    with pytest.raises(TypeError, match="Generator"):
        partition(source, by=choose, rng=np.random.RandomState(1))
    assert calls == []


def test_empty_input_skips_rng_requirement_and_draws_but_still_validates_signature():
    control = make_control()
    refs = put(control)
    source = ChangePool(control.solution_pool).read(refs).take(())
    rng = np.random.default_rng(41)
    expected = np.random.default_rng(41)
    calls = []

    def choose(pool, *, rng):
        calls.append(pool)
        rng.random()
        return pool

    assert all(not len(half) for half in partition(source, by=choose))
    assert all(not len(half) for half in partition(source, by=choose, rng=rng))
    assert calls == [] and rng.bit_generator.state == expected.bit_generator.state

    def invalid(pool, missing):
        calls.append(pool)
        return pool

    with pytest.raises(TypeError, match="accept|choose"):
        partition(source, by=invalid)
    assert calls == []


def test_supplied_rng_is_ignored_without_draws_when_rule_only_accepts_pool():
    control = make_control()
    refs = put(control)
    source = ChangePool(control.solution_pool).read(refs)
    rng = np.random.default_rng(44)
    expected = np.random.default_rng(44)
    calls = []

    def choose(pool):
        calls.append(pool)
        return pool.take((2,))

    selected, remaining = partition(source, by=choose, rng=rng)
    assert selected.refs == refs[2:] and remaining.refs == refs[:2]
    assert len(calls) == 1 and rng.bit_generator.state == expected.bit_generator.state


def test_partition_preserves_only_the_exact_delivered_pending_read_capability():
    control = make_control()
    published = put(control, (1.,), tokens=("published",))
    control.solution_pool.begin_attempt()
    accepted = put(control, (2.,), tokens=("own",))
    sibling = put(control, (3.,), tokens=("sibling",))
    with offered_pool(control, published + accepted, objectives=[[-1.], [-2.]],
                      violations=[0., 0.], accepted_refs=accepted) as source:
        def choose(pool):
            np.testing.assert_array_equal(pool.values, [[1.], [2.]])
            np.testing.assert_array_equal(pool.raw_feedback()[0], [[10.], [20.]])
            with pytest.raises(ValueError, match="uncommitted"):
                pool._scope.read(sibling)
            return pool.take((1,))

        selected, remaining = partition(source, by=choose)
        assert selected.refs == accepted and remaining.refs == published
        np.testing.assert_array_equal(selected.values, [[2.]])
        with pytest.raises(ValueError, match="uncommitted"):
            ChangePool(control.solution_pool).read(accepted)
