"""One batch calculation creates independent, scoped proposal identities."""
from dataclasses import replace

import numpy as np
import pytest
from blackbase.types import CandidateBatch, UnknownState

from nsgablack.adapters import ChangeRequest, ChangeResult, PoolOutput, VNSAdapter
from nsgablack.adapters.change import apply_function_change
from nsgablack.adapters.change_access import scoped_change_access
from nsgablack.adapters.change_batch import ChangeBatchResult, apply_function_change_batch
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.core.state.solution_pool import SolutionRef
from nsgablack.representation import RepresentationPipeline


class UncalledProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, objectives=["minimize"], bounds=[(-100., 100.)])

    def evaluate(self, candidate):
        raise AssertionError("a change bridge must not evaluate")


def two_children(request, *, rng):
    assert request.max_outputs == 2
    donors = request.pool.main(stage="initial")
    values = donors.values
    first = UnknownState(values[1] + rng.uniform(0., .1, size=1), {"kind": "first"})
    return ChangeBatchResult((
        ChangeResult(first, source_refs=(donors.refs[1],),
                     outputs=(PoolOutput("first-output", create=True),)),
        ChangeResult(request.candidate - 2., source_refs=(donors.refs[0],),
                     edits=(request.pool.trim_members("elite", 1),)),
    ))


def equal_children(request, *, rng):
    del rng
    return ChangeBatchResult((ChangeResult(request.candidate), ChangeResult(request.candidate)))


def empty_children(request, *, rng):
    del request, rng
    return ChangeBatchResult()


def single_child(request, *, rng):
    del rng
    return request.candidate + 1.


def wrapped_single_child(request, *, rng):
    return ChangeBatchResult((ChangeResult(single_child(request, rng=rng)),))


def matrix_result(request, *, rng):
    del rng
    return np.stack((request.candidate, request.candidate))


def invalid_later_child(request, *, rng):
    del rng
    return ChangeBatchResult((ChangeResult(request.candidate + 1.),
                              ChangeResult(np.array([1., 2.]))))


def missing_later_output(request, *, rng):
    del rng
    return ChangeBatchResult((ChangeResult(request.candidate + 1.),
        ChangeResult(request.candidate + 2., outputs=(PoolOutput("missing"),))))


def undeclared_source(request, *, rng):
    del rng
    ref = SolutionRef.from_dict(dict(request.parameters["forbidden"]))
    return ChangeBatchResult((ChangeResult(request.candidate, source_refs=(ref,)),))


def failed_calculation(request, *, rng):
    del request, rng
    raise TypeError("calculation failure must not trigger a retry")


def make_inputs(function, *, source_count=2, parameters=None):
    owner = VNSAdapter(change=function)
    control = ComposableSolver(UncalledProblem(), adapter=owner,
                               representation_pipeline=RepresentationPipeline())
    control.setup()
    batch = CandidateBatch.from_candidates(
        [UnknownState([4.], {"original": "anchor"}), UnknownState([8.], {"original": "donor"}),
         UnknownState([12.], {"original": "other"})], candidate_tokens=("a", "b", "c"))
    refs = control.store_solutions(batch)
    control.solution_pool.create_subpool("elite", refs[:2])
    anchor = control.propose_solutions(refs[:1]).semantic_states[0]
    request = ChangeRequest([[4.], [8.]][:source_count], source_refs=refs[:source_count],
                            parameters=parameters)
    return owner, control, anchor, request, refs


def record_calculation(monkeypatch, owner):
    calls = []
    original = owner.get_bound_change().change

    def track(request, *, rng):
        calls.append(request)
        return original(request, rng=rng)

    monkeypatch.setattr(owner.get_bound_change(), "change", track)
    return calls


def source_refs(metadata, key):
    return tuple(SolutionRef.from_dict(dict(ref)) for ref in metadata[key])


def test_batch_calls_function_once_and_binds_separate_sources_outputs_and_tokens(monkeypatch):
    owner, control, anchor, request, refs = make_inputs(two_children)
    calls = record_calculation(monkeypatch, owner)
    elite = control.solution_pool.subpool_descriptor("elite")
    children = apply_function_change_batch(owner, control, anchor, request, {},
        rng=np.random.default_rng(3), max_outputs=2)
    assert len(calls) == 1 and calls[0].max_outputs == 2
    assert len(children) == 2 and isinstance(children[0], UnknownState)
    assert children[0].metadata["kind"] == "first"
    assert len({control.candidate_provenance_for(child).candidate_token for child in children}) == 2
    assert {control.candidate_provenance_for(child).candidate_token for child in children}.isdisjoint(
        ref.candidate_token for ref in refs)
    first, second = (control.candidate_provenance_for(child) for child in children)
    assert source_refs(first.metadata, "change_source_refs") == refs[1:2]
    assert source_refs(second.metadata, "change_source_refs") == refs[:1]
    # Both children depend on the same calculation's materialized donor set.
    assert source_refs(first.metadata, "change_input_refs") == refs
    assert source_refs(second.metadata, "change_input_refs") == refs
    assert first.metadata["change_outputs"]["proposal_token"] == first.candidate_token
    assert second.metadata["change_pool_edits"]["proposal_token"] == second.candidate_token
    assert "change_pool_edits" not in first.metadata and "change_outputs" not in second.metadata
    assert not control.solution_pool.has_subpool("first-output")
    assert control.solution_pool.subpool_descriptor("elite") == elite
    assert control.solution_pool.subpool_refs("elite") == refs[:2]
    assert control.evaluation_count == 0 and owner.current_unit is None and owner.neighborhood_unit is None
    with pytest.raises(RuntimeError, match="ended"):
        calls[0].pool.main()


def test_equal_values_get_distinct_proposal_tokens_and_keep_default_source_slots():
    owner, control, anchor, request, refs = make_inputs(equal_children)
    request = ChangeRequest([[4.], [4.]], source_refs=(refs[0], refs[0]))
    children = apply_function_change_batch(owner, control, anchor, request, {},
        rng=np.random.default_rng(1), max_outputs=2)
    records = [control.candidate_provenance_for(child) for child in children]
    assert records[0].candidate_token != records[1].candidate_token
    for record in records:
        assert source_refs(record.metadata, "change_source_refs") == (refs[0], refs[0])
        assert source_refs(record.metadata, "change_input_refs") == (refs[0], refs[0])


def test_empty_batch_calculates_once_with_no_child_registration_or_unit(monkeypatch):
    owner, control, anchor, request, _ = make_inputs(empty_children)
    calls = record_calculation(monkeypatch, owner)
    before = control.solution_pool.record_count
    assert apply_function_change_batch(owner, control, anchor, request, {},
        rng=np.random.default_rng(1), max_outputs=0) == ()
    assert len(calls) == 1 and calls[0].max_outputs == 0
    assert control.solution_pool.record_count == before
    assert control.evaluation_count == 0 and owner.current_unit is None and owner.neighborhood_unit is None
    with pytest.raises(RuntimeError, match="ended"):
        calls[0].pool.main()


def test_overflow_precedes_any_child_registration_and_closes_scope(monkeypatch):
    owner, control, anchor, request, _ = make_inputs(equal_children)
    calls = record_calculation(monkeypatch, owner)
    before = control.solution_pool.record_count
    with pytest.raises(ValueError, match="max_outputs"):
        apply_function_change_batch(owner, control, anchor, request, {},
            rng=np.random.default_rng(1), max_outputs=1)
    assert len(calls) == 1 and control.solution_pool.record_count == before
    with pytest.raises(RuntimeError, match="ended"):
        calls[0].pool.main()


@pytest.mark.parametrize("function", (invalid_later_child, missing_later_output, matrix_result))
def test_batch_preflights_all_items_and_never_interprets_a_matrix_as_children(function):
    owner, control, anchor, request, _ = make_inputs(function)
    before = control.solution_pool.record_count
    with pytest.raises(ValueError):
        apply_function_change_batch(owner, control, anchor, request, {},
            rng=np.random.default_rng(1), max_outputs=2)
    assert control.solution_pool.record_count == before and control.evaluation_count == 0


@pytest.mark.parametrize("function", (empty_children, equal_children, matrix_result))
def test_scalar_consumers_reject_empty_multiple_or_implicit_matrix_results(function):
    owner, control, anchor, request, _ = make_inputs(function)
    with pytest.raises(ValueError, match="exactly one|one-dimensional"):
        apply_function_change(owner, control, anchor, request, {}, rng=np.random.default_rng(1))
    assert control.evaluation_count == 0 and owner.current_unit is None and owner.neighborhood_unit is None


@pytest.mark.parametrize("function", (single_child, wrapped_single_child))
def test_single_result_functions_work_for_scalar_and_batch_consumers(function):
    owner, control, anchor, request, refs = make_inputs(function)
    single = apply_function_change(owner, control, anchor, request, {}, rng=np.random.default_rng(1))
    children = apply_function_change_batch(owner, control, anchor, request, {},
        rng=np.random.default_rng(1), max_outputs=1)
    assert len(children) == 1
    np.testing.assert_array_equal(np.asarray(single), np.asarray(children[0]))
    assert source_refs(control.candidate_provenance_for(single).metadata, "change_source_refs") == refs[:2]


def test_batch_removes_ancestor_commands_for_children_without_new_instructions():
    owner, control, anchor, request, _ = make_inputs(equal_children)
    provenance = control.candidate_provenance_for(anchor)
    metadata = {**dict(provenance.metadata),
        "change_outputs": {"schema": "old", "proposal_token": provenance.candidate_token},
        "change_pool_edits": {"schema": "old", "proposal_token": provenance.candidate_token}}
    control.bind_candidate_provenance((anchor,), (replace(provenance, metadata=metadata),), activate=False)
    children = apply_function_change_batch(owner, control, anchor, request, {},
        rng=np.random.default_rng(1), max_outputs=2)
    for child in children:
        metadata = control.candidate_provenance_for(child).metadata
        assert "change_outputs" not in metadata and "change_pool_edits" not in metadata


def test_batch_does_not_repair_evaluate_or_consume_rng_for_internal_binding(monkeypatch):
    owner, control, anchor, request, _ = make_inputs(two_children)

    def forbidden(*args, **kwargs):
        pytest.fail("proposal creation called repair or evaluation")

    for method in ("repair_candidate", "evaluate_individual", "evaluate_population"):
        monkeypatch.setattr(control, method, forbidden)
    rng = np.random.default_rng(9)
    expected = np.random.default_rng(9)
    expected.uniform(0., .1, size=1)  # The user calculation's single draw.
    apply_function_change_batch(owner, control, anchor, request, {}, rng=rng, max_outputs=2)
    assert rng.bit_generator.state == expected.bit_generator.state


def test_batch_calculation_failure_is_not_retried_and_closes_input_scope(monkeypatch):
    owner, control, anchor, request, _ = make_inputs(failed_calculation)
    calls = record_calculation(monkeypatch, owner)
    before = control.solution_pool.record_count
    with pytest.raises(TypeError, match="must not trigger a retry"):
        apply_function_change_batch(owner, control, anchor, request, {},
            rng=np.random.default_rng(1), max_outputs=2)
    assert len(calls) == 1 and control.solution_pool.record_count == before
    with pytest.raises(RuntimeError, match="ended"):
        calls[0].pool.main()


def test_per_child_sources_cannot_bypass_task_input_permissions():
    owner, control, anchor, request, refs = make_inputs(undeclared_source, source_count=1)
    request = replace(request, parameters={"forbidden": refs[2].as_dict()})
    before = control.solution_pool.record_count
    with scoped_change_access(refs[:1], allow_main=False):
        with pytest.raises(ValueError, match="outside this change task"):
            apply_function_change_batch(owner, control, anchor, request, {},
                rng=np.random.default_rng(1), max_outputs=1)
    assert control.solution_pool.record_count == before


@pytest.mark.parametrize("results", (np.ones((2, 1)), [[1.], [2.]], {1, 2}, "", iter(())))
def test_batch_result_requires_explicit_ordered_change_results(results):
    with pytest.raises(TypeError, match="ordered sequence of ChangeResult"):
        ChangeBatchResult(results)
    assert ChangeBatchResult().results == ()


@pytest.mark.parametrize("limit", (-1, True, 1.5, "2", None))
def test_output_allowance_is_explicit_nonnegative_integer(limit):
    owner, control, anchor, request, _ = make_inputs(empty_children)
    with pytest.raises(ValueError, match="max_outputs"):
        apply_function_change_batch(owner, control, anchor, request, {},
            rng=np.random.default_rng(1), max_outputs=limit)


def test_request_allowance_is_optional_readonly_and_validated():
    assert ChangeRequest([[1.]]).max_outputs is None
    assert ChangeRequest([[1.]], max_outputs=np.int64(3)).max_outputs == 3
    for value in (-1, True, 1.5, "2"):
        with pytest.raises(ValueError, match="max_outputs"):
            ChangeRequest([[1.]], max_outputs=value)
