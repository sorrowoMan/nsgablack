"""Pool query operators preserve exact identity and call-scoped read access."""
import numpy as np
import pytest
from blackbase.context import create_snapshot_store
from blackbase.types import CandidateBatch, Feedback

from nsgablack.adapters.change_pool import ChangePool
from nsgablack.core.evaluation_feedback import OptimizationFeedbackBatch
from nsgablack.core.state.solution_pool import SolutionPool


def make_selection():
    pool = SolutionPool(create_snapshot_store(backend="memory"), run_id="query-test")
    refs = pool.put(CandidateBatch.from_candidates(
        [[2.], [1.], [1.], [3.]], candidate_tokens=("a", "b", "c", "d")), stage="accepted")
    newer = pool.put(CandidateBatch.from_candidates([[2.]], candidate_tokens=("a",)), stage="accepted")
    scope = ChangePool(pool)
    return pool, scope, scope.read(refs + newer)


def test_where_receives_readonly_selection_once_and_keeps_exact_equal_candidates():
    pool, scope, selection = make_selection()
    before = pool.snapshot_step_state()
    calls = []

    def choose(items):
        calls.append(items.refs)
        values = items.values
        with pytest.raises(ValueError):
            values[0, 0] = 99
        with pytest.raises(ValueError):
            values.setflags(write=True)
        return values[:, 0] <= 2

    result = selection.where(choose)
    assert calls == [selection.refs]
    assert result.refs == selection.refs[:3] + selection.refs[4:]
    assert result.refs[0].candidate_token == result.refs[-1].candidate_token
    assert result.refs[0] != result.refs[-1]
    assert result.refs[1] != result.refs[2]
    assert pool.snapshot_step_state()["index"] == before["index"]
    assert scope.used_refs == selection.refs


@pytest.mark.parametrize("mask", ([1, 0, 1, 0, 1], True, [[True] * 5], [True] * 4,
                                  [True, False, None, False, True]))
def test_where_rejects_nonboolean_or_unaligned_masks(mask):
    _, _, selection = make_selection()
    with pytest.raises(ValueError, match="boolean mask"):
        selection.where(lambda _: mask)


def test_order_and_top_are_stable_in_both_directions_with_explicit_rules():
    _, scope, selection = make_selection()
    calls = []

    def score(items):
        calls.append(items.refs)
        return items.values[:, 0]

    refs = selection.refs
    assert selection.order_by(score).refs == (refs[1], refs[2], refs[0], refs[4], refs[3])
    assert selection.order_by(score, reverse=True).refs == (refs[3], refs[0], refs[4], refs[1], refs[2])
    assert selection.top(3, key=score).refs == (refs[1], refs[2], refs[0])
    assert selection.top(30, key=score, reverse=True).refs == selection.order_by(score, reverse=True).refs
    assert len(calls) == 5
    assert scope.used_refs == refs


def test_lexicographic_key_supports_feasibility_first_without_soft_feedback():
    pool = SolutionPool(create_snapshot_store(backend="memory"), run_id="raw-order")
    raw = (([0., 9.], 2.), ([4., 8.], 0.), ([4., 1.], 0.), ([9., 0.], 0.))
    feedback = OptimizationFeedbackBatch.from_feedback(tuple(
        Feedback(objectives=[0.], info={"raw_evaluation": {
            "objectives": f, "constraint_violation": v}}) for f, v in raw), violations=[0.] * 4)
    refs = pool.put(CandidateBatch.from_candidates([[0.], [1.], [2.], [3.]],
        candidate_tokens=("a", "b", "c", "d")), stage="accepted", feedback=feedback)
    selection = ChangePool(pool).main()

    def feasible_then_objective(items):
        objectives, violations = items.raw_feedback()
        return np.column_stack((violations > 0, violations, objectives[:, 0]))

    assert selection.order_by(feasible_then_objective).refs == (refs[1], refs[2], refs[3], refs[0])
    assert selection.order_by(feasible_then_objective, reverse=True).refs == (refs[0], refs[3], refs[1], refs[2])
    np.testing.assert_array_equal(pool.read_raw_feedback(refs)[1], [2., 0., 0., 0.])


@pytest.mark.parametrize("scores", ([1., 2., np.nan, 3., 4.], [1., 2., np.inf, 3., 4.],
    [[1.], [2.]], np.empty((5, 0)), np.ones((5, 1, 1)), [True] * 5,
    ["1"] * 5, [1j] * 5, 3.))
def test_ordering_rejects_bad_shapes_nonreal_and_nonfinite_keys(scores):
    _, _, selection = make_selection()
    with pytest.raises(ValueError, match="finite real"):
        selection.order_by(lambda _: scores)


def test_ordering_keeps_precise_signed_and_unsigned_integer_keys():
    _, _, selection = make_selection()
    scores = np.array([0, 2 ** 64 - 1, 2 ** 64 - 2, 1, 1], dtype=np.uint64)
    refs = selection.refs
    assert selection.order_by(lambda _: scores, reverse=True).refs == (
        refs[1], refs[2], refs[3], refs[4], refs[0])
    signed = np.array([0, -(2 ** 63), 1, 1, 2], dtype=np.int64)
    assert selection.order_by(lambda _: signed, reverse=True).refs == (
        refs[4], refs[2], refs[3], refs[0], refs[1])


def test_empty_queries_and_zero_top_skip_callbacks_and_materialization(monkeypatch):
    pool, scope, selection = make_selection()
    empty = selection.take(())

    def unexpected(*args, **kwargs):
        pytest.fail("empty or reference-only operation materialized data or invoked callback")

    monkeypatch.setattr(pool, "read", unexpected)
    monkeypatch.setattr(pool, "read_raw_feedback", unexpected)
    assert empty.where(unexpected).refs == ()
    assert empty.order_by(unexpected).refs == ()
    assert empty.top(5, key=unexpected).refs == ()
    assert selection.top(0, key=unexpected).refs == ()
    assert empty.groups(3) == ()
    assert scope.used_refs == ()


def test_callback_errors_propagate_once_without_typeerror_retry():
    _, _, selection = make_selection()
    calls = []

    def broken(items):
        calls.append(items)
        raise TypeError("inside caller")

    for invoke in (lambda: selection.where(broken), lambda: selection.order_by(broken),
                   lambda: selection.top(2, key=broken)):
        calls.clear()
        with pytest.raises(TypeError, match="inside caller"):
            invoke()
        assert calls == [selection]


def test_set_operations_compare_exact_versions_preserve_left_order_and_duplicates(monkeypatch):
    pool, scope, selection = make_selection()
    refs = selection.refs
    left = selection.take((2, 0, 0, 4, 1, 3))
    newer = selection.take((4,))
    same_values_distinct_ref = selection.take((1,))

    def unexpected(*args, **kwargs):
        pytest.fail("identity query materialized values")

    monkeypatch.setattr(pool, "read", unexpected)
    monkeypatch.setattr(pool, "read_raw_feedback", unexpected)
    assert left.intersection(selection.take((0, 1, 4)), selection.take((0, 4))).refs == (
        refs[0], refs[0], refs[4])
    assert left.intersection(newer).refs == (refs[4],)
    assert left.difference(newer).refs == (refs[2], refs[0], refs[0], refs[1], refs[3])
    assert left.difference(same_values_distinct_ref).refs == (refs[2], refs[0], refs[0], refs[4], refs[3])
    assert left.intersection().refs == left.refs
    assert left.difference().refs == left.refs
    assert scope.used_refs == ()


def test_groups_keep_tail_identity_and_do_not_publish_subpools_or_build_units():
    pool, scope, selection = make_selection()
    before = pool.published_subpool_names()
    groups = selection.groups(2)
    assert tuple(group.refs for group in groups) == (
        selection.refs[:2], selection.refs[2:4], selection.refs[4:])
    assert selection.groups(np.int64(8))[0].refs == selection.refs
    assert pool.published_subpool_names() == before
    assert scope.used_refs == ()


@pytest.mark.parametrize("n", (-1, True, np.bool_(False), 1.5, "2", None))
def test_top_requires_nonnegative_integer_counts(n):
    _, _, selection = make_selection()
    with pytest.raises(ValueError, match="nonnegative integer"):
        selection.top(n, key=lambda _: np.ones(5))


@pytest.mark.parametrize("size", (0, -1, True, np.bool_(True), 1.5, "2", None))
def test_groups_require_positive_integer_size(size):
    _, _, selection = make_selection()
    with pytest.raises(ValueError, match="positive integer"):
        selection.groups(size)


def test_queries_validate_callable_and_reverse_even_for_empty_inputs():
    _, _, selection = make_selection()
    for items in (selection, selection.take(())):
        with pytest.raises(TypeError, match="callable"):
            items.where(None)
        with pytest.raises(TypeError, match="callable"):
            items.order_by(None)
        with pytest.raises(TypeError, match="callable"):
            items.top(0, key=None)
        with pytest.raises(TypeError, match="boolean"):
            items.order_by(lambda _: [], reverse=1)
        with pytest.raises(TypeError, match="boolean"):
            items.top(0, key=lambda _: [], reverse=1)
    with pytest.raises(TypeError):
        selection.top(2)


def test_foreign_operands_task_guards_and_closed_scope_cannot_be_bypassed():
    pool, scope, selection = make_selection()
    foreign = ChangePool(pool).main()
    for operation in (selection.intersection, selection.difference):
        with pytest.raises(ValueError, match="different change"):
            operation(foreign)
        with pytest.raises(ValueError, match="different change"):
            operation(selection.refs)
    restricted = ChangePool(pool, allowed_refs=selection.refs[:2], allow_main=False)
    allowed = restricted.read(selection.refs[:2])
    assert allowed.where(lambda _: [True, True]).refs == selection.refs[:2]
    with pytest.raises(ValueError, match="declared inputs"):
        restricted.read(selection.refs[2:])
    assert allowed.difference(allowed.take((0,))).refs == selection.refs[1:2]
    grouped = selection.groups(2)
    scope.close()
    operations = (lambda: selection.where(lambda _: []),
        lambda: selection.order_by(lambda _: []), lambda: selection.top(0, key=lambda _: []),
        lambda: selection.intersection(), lambda: selection.difference(),
        lambda: selection.groups(2), lambda: grouped[0].refs)
    for operation in operations:
        with pytest.raises(RuntimeError, match="ended"):
            operation()
