"""Small Pool rules and local drafts join the existing owner transaction."""
from functools import partial
import copy

import numpy as np
import pytest
from blackbase.contracts import BatchDisposition

from nsgablack.adapters import Pool, partition
from nsgablack.adapters.change_pool import ChangePool, _PoolCoordinates
from nsgablack.adapters.pool_maintenance import collecting_pool_edits
from nsgablack.adapters.selection_pool import offered_pool, pool_selection_indices
from .test_ga_pool_workflow import make_ga, keep_first, bad_archive, archive_output_change
from .test_pool_survivor_selection import make_control, put


@pytest.fixture
def source_pool():
    control = make_control()
    refs = put(control)
    scope = ChangePool(control.solution_pool)
    try:
        yield control, scope.read(refs)
    finally:
        scope.close()


def members_with_automatic_draft(pool):
    members = pool.chosen(keep_first)
    target = Pool(parent=pool, name="elite")
    assert target.refs == ()
    target.inject(members.take((0, 0, 1)), replace=True)
    frozen = target.all()
    alias = Pool(parent=pool, name="elite")
    alias.inject(members.take((1, 2, 2)))
    assert frozen.refs == (members.refs[0], members.refs[0], members.refs[1])
    assert target.all().refs == alias.all().refs == (
        members.refs[0], members.refs[0], members.refs[1], members.refs[2])
    return members


def construct_without_inject(pool):
    Pool(parent=pool, name="unused")
    return keep_first(pool)


def inject_empty(pool):
    Pool(parent=pool, name="elite").inject(pool.take(()), replace=True)
    Pool(parent=pool, name="empty").inject(pool.take(()), replace=True)
    return keep_first(pool)


def append_to_existing_from_survivor(pool):
    Pool(parent=pool, name="elite").inject(pool.take((0,)))
    return keep_first(pool)


def append_old_and_new_in_maintenance(request, *, rng):
    del rng
    old = request.pool.subpool("elite")
    source = old.take((0,)).concat(request.accepted.take((0, 0)))
    Pool(parent=request.pool, name="elite").inject(source)
    # Automatic plans are the only work returned from this callback.


def no_maintenance_result(request, *, rng):
    del request, rng


def wrong_member_count_after_inject(pool):
    Pool(parent=pool, name="late").inject(pool.take((0,)), replace=True)
    return pool.take((0, 1, 2))


def automatic_and_explicit_conflict(pool):
    members = keep_first(pool)
    Pool(parent=pool, name="elite").inject(members.take((0,)), replace=True)
    return members, {"elite": members.take((1,))}


def named_output(pool, *, name):
    Pool(parent=pool, name=name).inject(pool.take((0,)), replace=True)
    return keep_first(pool)


def anonymous_change(request, *, rng):
    del rng
    draft = Pool(parent=request.pool)
    draft.inject(request.pool.read(request.source_refs), replace=True)
    return np.mean(draft.values, axis=0) - .1


def named_change(request, *, rng):
    del rng
    Pool(parent=request.pool, name="unsupported").inject(
        request.pool.read(request.source_refs), replace=True)
    return request.candidate - .1


def test_chosen_retains_outer_positions_through_local_repetition():
    control = make_control()
    refs = put(control)
    with offered_pool(control, refs, objectives=[[1.], [2.], [3.]], violations=[0.] * 3) as pool:
        repeated = pool.take((0, 1, 0))
        assert repeated.chosen(lambda rows: rows).refs == (refs[0], refs[1], refs[0])
        chosen = repeated.chosen(lambda rows: rows.take((2, 0)))
        assert chosen.refs == (refs[0], refs[0])
        with pytest.raises(ValueError, match="repeat"):
            pool_selection_indices(pool, chosen)
        reordered = pool.take((2, 0, 1)).chosen(lambda rows: rows.take((1, 0)))
        assert pool_selection_indices(pool, reordered) == (0, 2)


def test_chosen_calls_rule_once_with_rng_and_does_not_invent_new_records(source_pool):
    control, pool = source_pool
    calls = []
    rng = np.random.default_rng(11)
    expected = np.random.default_rng(11).choice(3, size=6, replace=True)

    def choose(rows, *, rng):
        calls.append(rows.refs)
        return rows.sample(6, rng=rng, replace=True)

    before = control.solution_pool.record_count
    result = pool.chosen(choose, rng=rng)
    assert calls == [pool.refs]
    assert result.refs == tuple(pool.refs[i] for i in expected)
    assert control.solution_pool.record_count == before


@pytest.mark.parametrize("kind", ["new-root", "foreign-scope", "indices"])
def test_chosen_rejects_results_outside_its_local_offered_root(source_pool, kind):
    control, pool = source_pool
    other = ChangePool(control.solution_pool)
    try:
        def choose(rows):
            if kind == "new-root":
                return rows._scope.read(rows.refs[:1])
            if kind == "foreign-scope":
                return other.read(rows.refs[:1])
            return (0,)

        with pytest.raises((TypeError, ValueError)):
            pool.chosen(choose)
    finally:
        other.close()


@pytest.mark.parametrize("operation", ["chosen", "partition"])
@pytest.mark.parametrize("foreign_scope", [False, True])
def test_pure_selection_rejects_inject_on_same_or_other_scope_drafts(source_pool, operation, foreign_scope):
    control, pool = source_pool
    other = ChangePool(control.solution_pool)
    try:
        source = other.read(pool.refs) if foreign_scope else pool
        target = Pool(parent=source)

        def choose(rows):
            # Both injection inputs share their own scope; purity, rather than
            # the cross-scope source guard, must reject this side effect.
            target.inject(source.take((0,)), replace=True)
            return rows

        with pytest.raises((RuntimeError, ValueError), match="chosen|pure|read.only"):
            if operation == "chosen":
                pool.chosen(choose)
            else:
                partition(pool, by=choose)
        assert target.refs == ()
    finally:
        other.close()


@pytest.mark.parametrize("operation", ["chosen", "partition"])
def test_pure_selection_rejects_named_construction_in_another_enabled_writer(source_pool, operation):
    control, pool = source_pool
    store = control.solution_pool
    baseline = store.snapshot_step_state()
    store.begin_attempt()
    writer = ChangePool(store)
    try:
        with collecting_pool_edits(store), writer._writing("maintenance"):
            # This scope really can construct named targets before the pure
            # rule starts; ordinary writer absence is not the rejection.
            assert Pool(parent=writer, name="allowed").refs == ()

            def choose(rows):
                Pool(parent=writer, name="forbidden")
                return rows

            with pytest.raises((RuntimeError, ValueError), match="chosen|pure|read.only"):
                if operation == "chosen":
                    pool.chosen(choose)
                else:
                    partition(pool, by=choose)
        assert not store.has_subpool("allowed")
        assert not store.has_subpool("forbidden")
    finally:
        writer.close()
        store.restore_step_state(baseline)


def test_empty_chosen_skips_callback_and_internal_typeerror_is_not_retried(source_pool):
    _, pool = source_pool
    calls = []
    rng = np.random.default_rng(17)
    state = copy.deepcopy(rng.bit_generator.state)

    def fail(rows, *, rng):
        calls.append(rows.refs)
        raise TypeError("rule calculation failed")

    assert pool.take(()).chosen(fail).refs == ()
    assert calls == [] and rng.bit_generator.state == state
    with pytest.raises(TypeError, match="rule calculation failed"):
        pool.chosen(fail, rng=rng)
    assert len(calls) == 1


def test_anonymous_draft_is_empty_then_appends_exact_versions_without_numeric_deduplication():
    control = make_control()
    refs = (put(control, (1., 1.), tokens=("same", "other"))
            + put(control, (1.,), tokens=("same",)))
    scope = ChangePool(control.solution_pool)
    try:
        source = scope.read(refs)
        target = Pool(parent=scope)
        assert target.refs == ()
        before = control.solution_pool.record_count
        target.inject(source.take((0, 0, 1)))
        target.inject(source.take((0, 2, 2)))
        assert target.refs == refs
        target.inject(source.take((2, 2, 0)), replace=True)
        assert target.refs == (refs[2], refs[2], refs[0])
        assert control.solution_pool.record_count == before
    finally:
        scope.close()


def test_all_freezes_draft_members_and_same_root_selection_feedback():
    control = make_control()
    refs = put(control)
    with offered_pool(control, refs, objectives=[[-1.], [-2.], [-3.]], violations=[0., 1., 2.]) as pool:
        target = Pool(parent=pool)
        target.inject(pool.take((2, 0)), replace=True)
        before = target.all()
        target.inject(pool.take((1,)))
        assert before.refs == (refs[2], refs[0])
        assert target.all().refs == (refs[2], refs[0], refs[1])
        np.testing.assert_array_equal(before.objectives, [[-3.], [-1.]])
        np.testing.assert_array_equal(target.all().objectives, [[-3.], [-1.], [-2.]])
        np.testing.assert_array_equal(target.all().violations, [2., 0., 1.])
        with pytest.raises(ValueError):
            before.objectives.setflags(write=True)
    for view in (target, before):
        with pytest.raises(RuntimeError, match="ended"):
            view.all()


def test_mixing_distinct_feedback_roots_does_not_guess_one_comparison_frame():
    control = make_control()
    refs = put(control)
    with offered_pool(control, refs, objectives=[[-1.], [-2.], [-3.]], violations=[0.] * 3) as pool:
        target = Pool(parent=pool)
        target.inject(pool.take((0,)), replace=True)
        other = pool._scope._selection((refs[1],),
            root=_PoolCoordinates((refs[1],), np.array([[900.]]), np.array([0.])), positions=(0,))
        target.inject(other)
        assert target.refs == refs[:2]
        with pytest.raises(ValueError, match="feedback"):
            target.all().objectives
        np.testing.assert_array_equal(target.raw_feedback()[0], [[10.], [20.]])


def test_inject_rejects_foreign_scope_and_raw_arrays_without_changing_draft(source_pool):
    control, pool = source_pool
    target = Pool(parent=pool)
    target.inject(pool.take((0,)), replace=True)
    other = ChangePool(control.solution_pool)
    try:
        for source in (other.read(pool.refs[1:]), pool.values, pool.refs):
            with pytest.raises((TypeError, ValueError)):
                target.inject(source)
            assert target.refs == pool.refs[:1]
    finally:
        other.close()


def test_named_target_requires_a_real_write_callback_but_anonymous_draft_does_not(source_pool):
    _, pool = source_pool
    with pytest.raises(RuntimeError):
        Pool(parent=pool, name="outside")
    target = Pool(parent=pool)
    target.inject(pool.take((0,)), replace=True)
    assert target.refs == pool.refs[:1]


def test_real_survivor_merges_same_named_draft_into_one_exact_member_plan():
    solver, adapter = make_ga(selector=members_with_automatic_draft, maintenance=None)
    assert solver.step().committed
    members = adapter.get_population_solution_refs(solver)
    assert solver.solution_pool.subpool_refs("elite") == (members[0], members[0], members[1], members[2])
    descriptor = solver.solution_pool.subpool_descriptor("elite")
    assert solver.step().committed
    assert solver.solution_pool.subpool_descriptor("elite") == descriptor
    assert solver.evaluation_count == len(solver.problem.calls) == 8


def test_constructing_an_unused_named_target_does_not_create_it():
    solver, _ = make_ga(selector=construct_without_inject, maintenance=None)
    assert solver.step().committed
    assert not solver.solution_pool.has_subpool("unused")


def test_empty_replacement_clears_existing_target_and_creates_absent_empty_target():
    solver, adapter = make_ga(selector=members_with_automatic_draft, maintenance=None)
    assert solver.step().committed
    descriptor = solver.solution_pool.subpool_descriptor("elite")
    adapter.set_selector(inject_empty)
    assert solver.step().committed
    assert solver.solution_pool.subpool_refs("elite") == ()
    assert solver.solution_pool.subpool_refs("empty") == ()
    assert solver.solution_pool.subpool_descriptor("elite")["view_id"] == descriptor["view_id"]


def test_first_append_to_existing_target_needs_explicit_old_member_read_permission():
    solver, _ = make_ga(selector=append_to_existing_from_survivor, maintenance=None)
    with pytest.raises(ValueError, match="declared|permission|read|scope"):
        solver.step()
    assert solver.solution_pool.subpool_refs("elite") == ()
    assert solver.evaluation_count == 4


def test_maintenance_append_preserves_old_repetitions_and_deduplicates_only_new_additions():
    solver, adapter = make_ga(selector=keep_first, maintenance=None)
    assert solver.step().committed
    members = adapter.get_population_solution_refs(solver)
    solver.solution_pool.replace_subpool_members("elite", (members[0], members[0], members[1]))
    adapter.set_pool_maintenance(append_old_and_new_in_maintenance)
    accepted_before = len(solver.solution_pool.select(stage="accepted"))
    assert solver.step().committed
    incoming = solver.solution_pool.select(stage="accepted")[accepted_before:]
    assert solver.solution_pool.subpool_refs("elite") == (members[0], members[0], members[1], incoming[0])
    assert solver.evaluation_count == 8


def test_maintenance_none_is_still_invalid_without_an_automatic_plan():
    solver, _ = make_ga(selector=keep_first, maintenance=no_maintenance_result)
    with pytest.raises(TypeError, match="PoolEdit|sequence|return"):
        solver.step()
    assert solver.solution_pool.subpool_refs("elite") == ()


@pytest.mark.parametrize("failure", ["count", "maintenance", "tuple-conflict", "append-conflict"])
def test_automatic_draft_failure_rolls_back_unit_rng_and_memberships_but_not_evaluation_cost(failure):
    solver, adapter = make_ga(selector=members_with_automatic_draft, maintenance=None)
    assert solver.step().committed
    if failure == "count":
        adapter.set_selector(wrong_member_count_after_inject)
    elif failure == "maintenance":
        adapter.set_pool_maintenance(bad_archive)
    elif failure == "tuple-conflict":
        adapter.set_selector(automatic_and_explicit_conflict)
    else:
        adapter.set_change(archive_output_change)
    before = copy.deepcopy(adapter.get_state())
    descriptor = solver.solution_pool.subpool_descriptor("elite")
    members = solver.solution_pool.subpool_refs("elite")
    manifest = solver.solution_pool.publication_ref()
    with pytest.raises((ValueError, RuntimeError)):
        solver.step()
    assert adapter.get_state() == before
    assert solver.solution_pool.subpool_descriptor("elite") == descriptor
    assert solver.solution_pool.subpool_refs("elite") == members
    assert solver.solution_pool.publication_ref() == manifest
    assert not solver.solution_pool.has_subpool("late")
    assert solver.evaluation_count == len(solver.problem.calls) == 8


def test_algorithm_owned_view_is_not_a_writable_target():
    solver, adapter = make_ga(selector=keep_first, maintenance=None)
    assert solver.step().committed
    members = adapter.get_population_solution_refs(solver)
    solver.solution_pool.publish_subpool_view("owned", members, created_by=("owner",))
    adapter.set_selector(partial(named_output, name="owned"))
    with pytest.raises(ValueError, match="ordinary|algorithm|view"):
        solver.step()
    assert solver.solution_pool.subpool_refs("owned") == members
    assert adapter.get_population_solution_refs(solver) == members


def test_zero_admission_does_not_invoke_survivor_or_publish_automatic_drafts(monkeypatch):
    solver, adapter = make_ga(selector=members_with_automatic_draft, maintenance=None)

    class Reject:
        def select(self, candidates, feedback, context):
            return BatchDisposition(len(candidates.semantic_states), ())

    def forbidden(*args, **kwargs):
        raise AssertionError("survivor ran despite zero admission")

    solver.set_evaluation_acceptance_policy(Reject())
    monkeypatch.setattr(adapter.get_bound_selector(), "select", forbidden)
    assert not solver.step().committed
    assert solver.solution_pool.subpool_refs("elite") == ()
    assert solver.evaluation_count == 4


@pytest.mark.parametrize("named", [False, True])
def test_change_propose_allows_anonymous_work_but_cannot_publish_named_drafts(named):
    solver, adapter = make_ga(change=named_change if named else anonymous_change,
        selector=keep_first, maintenance=None)
    assert solver.step().committed
    if named:
        with pytest.raises(RuntimeError):
            solver.step()
        assert solver.evaluation_count == 4
        assert not solver.solution_pool.has_subpool("unsupported")
    else:
        assert solver.step().committed
        assert solver.evaluation_count == 8
