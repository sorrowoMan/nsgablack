"""Pool selection preserves exact offered coordinates and accepted capabilities."""
from functools import partial
from types import SimpleNamespace

import numpy as np
import pytest
from blackbase.context import create_snapshot_store
from blackbase.types import CandidateBatch, Feedback

from nsgablack.adapters import NSGA2Adapter
from nsgablack.adapters.change_pool import ChangePool, ChangeSelection, Pool
from nsgablack.adapters.selection import FeasibilityFirstSelection, SelectionRequest
from nsgablack.adapters.selection_pool import offered_pool, pool_selection_indices
from nsgablack.core.evaluation_feedback import OptimizationFeedbackBatch
from nsgablack.core.state.solution_pool import SolutionPool


def make_control():
    return SimpleNamespace(solution_pool=SolutionPool(
        create_snapshot_store(backend="memory"), run_id="survivor-pool"))


def put(control, values=(1., 2., 3.), *, tokens=None, stage="accepted"):
    tokens = tokens or tuple("abc"[:len(values)])
    feedback = OptimizationFeedbackBatch.from_feedback(tuple(
        Feedback(objectives=[value * 10]) for value in values), violations=[0.] * len(values))
    return control.solution_pool.put(CandidateBatch.from_candidates(
        [[value] for value in values], candidate_tokens=tokens), stage=stage, feedback=feedback)


def request(pool, count):
    f, v = pool.selection_feedback()
    return SelectionRequest("survivor", pool.values, f, v, count, pool=pool)


def choose_positions(pool, *, indices=(2, 0)):
    return pool.take(indices)


def choose_with_rng(pool, *, rng):
    return pool.sample(2, rng=rng)


def choose_requested(pool, *, count):
    return pool.top(count, key=lambda p: p.objectives[:, 0])


def choose_requested_random(pool, *, count, rng):
    return pool.random(count, rng=rng)


@pytest.mark.parametrize("choose", [choose_requested, choose_requested_random])
def test_plain_choice_receives_actual_request_count_without_rebinding(choose):
    control = make_control()
    refs = put(control)
    adapter = NSGA2Adapter()
    adapter.set_selector(choose)
    assert adapter.algorithm_unit is None
    assert adapter.get_bound_selector().checkpoint_identity()["schema"] == "nsgablack.pool_selection/v2"
    for count in (1, 3, 2):
        with offered_pool(control, refs, objectives=[[3.], [1.], [2.]], violations=[0.]*3) as pool:
            indices = adapter.select_indices(request(pool, count), rng=np.random.default_rng(1))
            assert len(indices) == len(set(indices)) == count
            if choose is choose_requested:
                assert indices.tolist() == [1, 2, 0][:count]


def test_explicit_partial_count_keeps_existing_fixed_choice_contract():
    adapter = NSGA2Adapter()
    adapter.set_selector(partial(choose_requested, count=2))
    assert adapter.get_bound_selector().checkpoint_identity()["schema"] == "nsgablack.pool_selection/v1"
    control = make_control()
    refs = put(control)
    with offered_pool(control, refs, objectives=[[1.], [2.], [3.]], violations=[0.]*3) as pool:
        with pytest.raises(ValueError, match="expected 1, got 2"):
            adapter.select_indices(request(pool, 1), rng=np.random.default_rng(1))


def test_public_pool_all_concat_and_existing_merge_have_distinct_identity_semantics():
    control = make_control()
    refs = put(control)
    scope = ChangePool(control.solution_pool)
    original = scope.read(refs)
    assert Pool is ChangeSelection
    part = original.take((2, 0))
    assert part.all() is part
    assert part.all().refs == (refs[2], refs[0])
    assert part.concat(original.take((0, 1))).refs == (refs[2], refs[0], refs[0], refs[1])
    assert part.merge(original.take((0, 1))).refs == (refs[2], refs[0], refs[1])
    assert original.refs == refs


def test_exact_duplicate_ref_positions_are_not_recovered_by_value_or_ref_equality():
    control = make_control()
    refs = put(control, (1., 1.), tokens=("a", "b"))
    ordered = (refs[0], refs[1], refs[0])
    adapter = NSGA2Adapter()
    adapter.set_selector(partial(choose_positions, indices=(2,)))
    with offered_pool(control, ordered, objectives=[[3.], [2.], [1.]], violations=[0.] * 3) as pool:
        assert adapter.select_indices(request(pool, 1), rng=np.random.default_rng(1)).tolist() == [2]


def test_chained_filter_sort_and_take_preserve_original_request_coordinates():
    control = make_control()
    refs = put(control)

    def choose(pool):
        return pool.take((2, 0, 1)).filter(
            lambda items: items.values[:, 0] >= 2).sort(lambda items: items.objectives[:, 0])

    adapter = NSGA2Adapter()
    adapter.set_selector(choose)
    with offered_pool(control, refs, objectives=[[9.], [1.], [2.]], violations=[0.] * 3) as pool:
        assert adapter.select_indices(request(pool, 2), rng=np.random.default_rng(1)).tolist() == [1, 2]


def test_supplied_selection_feedback_is_distinct_from_raw_and_readonly():
    control = make_control()
    refs = put(control)
    with offered_pool(control, refs, objectives=[[-3.], [-2.], [-1.]], violations=[0., 1., 2.]) as pool:
        np.testing.assert_array_equal(pool.objectives, [[-3.], [-2.], [-1.]])
        np.testing.assert_array_equal(pool.raw_feedback()[0], [[10.], [20.], [30.]])
        with pytest.raises(ValueError):
            pool.objectives.setflags(write=True)
        reordered = pool.take((2, 0))
        np.testing.assert_array_equal(reordered.violations, [2., 0.])
        np.testing.assert_array_equal(reordered.objectives, [[-1.], [-3.]])


def test_selection_request_rejects_mismatching_candidates_or_selection_feedback():
    control = make_control()
    refs = put(control)
    with offered_pool(control, refs, objectives=[[1.], [2.], [3.]], violations=[0.] * 3) as pool:
        with pytest.raises(ValueError, match="candidates differ"):
            SelectionRequest("survivor", [[9.], [2.], [3.]], pool.objectives, pool.violations, 1, pool=pool)
        with pytest.raises(ValueError, match="feedback differs"):
            SelectionRequest("survivor", pool.values, [[9.], [2.], [3.]], pool.violations, 1, pool=pool)


@pytest.mark.parametrize("indices, count, message", [((0, 0), 2, "repeat"), ((0,), 2, "count")])
def test_pool_return_must_obey_survivor_count_and_distinct_original_positions(indices, count, message):
    control = make_control()
    refs = put(control)
    adapter = NSGA2Adapter()
    adapter.set_selector(partial(choose_positions, indices=indices))
    with offered_pool(control, refs, objectives=[[1.], [2.], [3.]], violations=[0.] * 3) as pool:
        with pytest.raises(ValueError, match=message):
            adapter.select_indices(request(pool, count), rng=np.random.default_rng(1))


def test_same_references_reselected_from_a_new_root_cannot_spoof_returned_coordinates():
    control = make_control()
    refs = put(control)

    def choose(pool):
        return pool._scope.read(pool.refs[:1])

    adapter = NSGA2Adapter()
    adapter.set_selector(choose)
    with offered_pool(control, refs, objectives=[[1.], [2.], [3.]], violations=[0.] * 3) as pool:
        with pytest.raises(ValueError, match="root and scope"):
            adapter.select_indices(request(pool, 1), rng=np.random.default_rng(1))


def test_foreign_or_closed_scope_and_expanded_position_cannot_be_returned():
    control = make_control()
    refs = put(control)
    with offered_pool(control, refs, objectives=[[1.], [2.], [3.]], violations=[0.] * 3) as pool:
        offered = pool.take((0, 1))
        with pytest.raises(ValueError, match="exceeds"):
            pool_selection_indices(offered, pool.take((2,)))
        with offered_pool(control, refs, objectives=[[1.], [2.], [3.]], violations=[0.] * 3) as other:
            with pytest.raises(ValueError, match="root and scope"):
                pool_selection_indices(pool, other.take((0,)))
        with pytest.raises(RuntimeError, match="ended"):
            pool_selection_indices(pool, other)
    with pytest.raises(RuntimeError, match="ended"):
        pool.all()


def test_function_rng_is_supplied_and_checkpoint_identity_includes_configuration():
    control = make_control()
    refs = put(control)
    first, second = NSGA2Adapter(), NSGA2Adapter()
    first.set_selector(choose_with_rng)
    second.set_selector(choose_with_rng)
    assert first.operator_bindings_state() == second.operator_bindings_state()
    with offered_pool(control, refs, objectives=[[1.], [2.], [3.]], violations=[0.] * 3) as pool:
        req = request(pool, 2)
        np.testing.assert_array_equal(first.select_indices(req, rng=np.random.default_rng(7)),
                                      second.select_indices(req, rng=np.random.default_rng(7)))


def test_array_only_legacy_path_keeps_component_selector_but_refuses_plain_choose():
    req = SelectionRequest("survivor", [[1.], [2.]], [[3.], [1.]], [0., 0.], 1)
    adapter = NSGA2Adapter()
    adapter.set_selector(FeasibilityFirstSelection())
    assert adapter.select_indices(req, rng=np.random.default_rng(1)).tolist() == [1]
    adapter.set_selector(partial(choose_positions, indices=(0,)))
    with pytest.raises(ValueError, match="array-only"):
        adapter.select_indices(req, rng=np.random.default_rng(1))


def test_ordinary_choose_cannot_return_indices_or_hide_mutable_closure_state():
    def wrong(pool):
        return (0,)

    captured = []

    def hidden(pool):
        captured.append(1)
        return pool

    adapter = NSGA2Adapter()
    with pytest.raises(TypeError, match="mutable"):
        adapter.set_selector(hidden)
    adapter.set_selector(wrong)
    control = make_control()
    refs = put(control)
    with offered_pool(control, refs, objectives=[[1.], [2.], [3.]], violations=[0.] * 3) as pool:
        with pytest.raises(TypeError, match="must return a Pool"):
            adapter.select_indices(request(pool, 1), rng=np.random.default_rng(1))


def test_accepted_capability_authorizes_only_exact_delivered_versions_not_main_or_siblings():
    control = make_control()
    published = put(control, (1.,), tokens=("old",))
    control.solution_pool.create_subpool("elite", published)
    control.solution_pool.begin_attempt()
    accepted = put(control, (2.,), tokens=("own",))
    sibling = put(control, (3.,), tokens=("sibling",))
    draft = put(control, (4.,), tokens=("draft",), stage="proposal")
    plain = ChangePool(control.solution_pool)
    with pytest.raises(ValueError, match="uncommitted"):
        plain.read(accepted)
    capability = ChangePool(control.solution_pool, accepted_refs=accepted)
    assert capability.main().refs == published
    assert capability.read(accepted).refs == accepted
    np.testing.assert_array_equal(capability.read(accepted).values, [[2.]])
    np.testing.assert_array_equal(capability.read(accepted).raw_feedback()[0], [[20.]])
    assert capability.replace_members("elite", published + accepted).members == published + accepted
    with pytest.raises(ValueError, match="uncommitted"):
        capability.read(sibling)
    with pytest.raises(ValueError, match="admitted"):
        ChangePool(control.solution_pool, accepted_refs=draft)
    with offered_pool(control, published + accepted, objectives=[[1.], [2.]],
                      violations=[0., 0.], accepted_refs=accepted) as pool:
        np.testing.assert_array_equal(pool.values, [[1.], [2.]])
        with pytest.raises(ValueError, match="mother pool"):
            pool._scope.main()
        with pytest.raises(ValueError, match="uncommitted"):
            pool._scope.read(sibling)


def test_offered_capability_and_feedback_cannot_exceed_exact_input_rows():
    control = make_control()
    refs = put(control)
    with pytest.raises(ValueError, match="exceeds"):
        with offered_pool(control, refs[:1], objectives=[[1.]], violations=[0.], accepted_refs=refs[1:]):
            pass
    with pytest.raises(ValueError, match="align"):
        with offered_pool(control, refs, objectives=[[1.]], violations=[0.] * 3):
            pass
