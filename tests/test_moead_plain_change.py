"""Plain MOEA/D change functions preserve direction, evidence and recovery rules."""
from __future__ import annotations

import copy

import numpy as np
import pytest
from blackbase.contracts import BatchDisposition
from blackbase.types import UnknownState

from nsgablack.adapters import MOEADAdapter
from nsgablack.adapters.subpools import adapter_path
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.core.state.solution_pool import SolutionRef
from nsgablack.representation import ClipRepair, RepresentationPipeline


class BiSphere(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, objectives=["left", "right"], bounds=[(-100., 100.)])
        self.fail = False
        self.seen = []

    def evaluate(self, candidate):
        self.seen.append(np.array(candidate, copy=True))
        if self.fail:
            raise RuntimeError("intentional change evaluation failure")
        value = float(np.asarray(candidate)[0])
        return [value * value, (value - 3.) ** 2]


class OrderedSeeds:
    def __init__(self):
        self.count = 0

    def checkpoint_identity(self):
        return {"kind": "plain-change-ordered-seeds"}

    def initialize(self, problem, context):
        self.count += 1
        return UnknownState([float(self.count * 2)], {"family": "semantic-seed"})

    def get_state(self):
        return {"count": self.count}

    def set_state(self, state):
        self.count = state["count"]


class ForbiddenPipelineMutation:
    def mutate(self, candidate, context):
        raise AssertionError("a plain change must replace the whole variation path")


def mutate_then_cross(request, *, rng):
    a, b = request.parents[:2]
    return ((a + 1.) ** 2 + (b + 1.) ** 2) / 2.


def cross_then_mutate(request, *, rng):
    a, b = request.parents[:2]
    return ((a + b) / 2. + 1.) ** 2


def random_direction_change(request, *, rng):
    return request.candidate + rng.normal(0., .5, size=request.candidate.shape)


def wrong_shape_change(request, *, rng):
    return request.parents


def make(change=mutate_then_cross, *, variation="de", batch_size=2):
    adapter = MOEADAdapter(population_size=4, batch_size=batch_size,
        neighborhood_size=4, nr=2, variation=variation,
        initializer=OrderedSeeds(), change=change)
    solver = ComposableSolver(BiSphere(), adapter=adapter,
        representation_pipeline=RepresentationPipeline(mutator=ForbiddenPipelineMutation(),
            repair=ClipRepair(low=-100., high=100.)))
    solver.set_random_seed(47)
    solver.setup()
    return solver, adapter


def capture_requests(monkeypatch, adapter):
    requests = []
    original = adapter.apply_change

    def apply(control, candidate, request, context, *, rng):
        requests.append(request)
        return original(control, candidate, request, context, rng=rng)

    monkeypatch.setattr(adapter, "apply_change", apply)
    return requests


@pytest.mark.parametrize("variation", ["de", "pipeline"])
def test_plain_change_replaces_full_variation_with_readonly_direction_inputs(monkeypatch, variation):
    solver, adapter = make(variation=variation)
    assert solver.step().committed
    source_refs = adapter.get_population_solution_refs(solver)
    source_x = np.array(adapter.pop_X, copy=True)
    source_ideal = np.array(adapter.ideal, copy=True)
    requests = capture_requests(monkeypatch, adapter)

    def forbidden_de(*args, **kwargs):
        pytest.fail("native DE must not run before an assembled change")

    monkeypatch.setattr(adapter, "_de_variation", forbidden_de)
    assert solver.step().committed
    assert len(requests) == 2 and not adapter.uses_pipeline_mutation
    expected = []
    for request in requests:
        parameters = request.parameters
        indices = tuple(parameters["parent_indices"])
        target = parameters["subproblem_index"]
        assert indices[0] == target and len(set(indices)) == len(indices) == 4
        assert request.source_refs == tuple(source_refs[index] for index in indices)
        np.testing.assert_array_equal(request.parents, source_x[list(indices)])
        np.testing.assert_array_equal(parameters["weight"], adapter.weights[target])
        np.testing.assert_array_equal(parameters["ideal"], source_ideal)
        assert request.unit_id == adapter.get_unit_id()
        assert not request.parents.flags.writeable and not parameters["weight"].flags.writeable
        with pytest.raises(ValueError):
            request.parents.flags.writeable = True
        with pytest.raises(TypeError):
            parameters["subproblem_index"] = -1
        expected.append(mutate_then_cross(request, rng=None))
    np.testing.assert_allclose(solver._last_evaluated_event_batch.numeric_matrix, expected)
    for request, provenance in zip(requests, solver._last_evaluated_event_provenance, strict=True):
        supplied = tuple(SolutionRef.from_dict(ref) for ref in provenance.metadata["change_input_refs"])
        assert supplied == request.source_refs
    np.testing.assert_array_equal(solver.read_solutions(source_refs).numeric_matrix, source_x)
    assert set(solver._last_evaluated_event_batch.candidate_tokens).isdisjoint(
        ref.candidate_token for ref in source_refs)
    assert all(state.metadata["family"] == "semantic-seed"
               for state in solver._last_evaluated_event_batch.semantic_states)
    # Direction views keep the original two-objective evaluation, not the
    # scalar comparison used by any downstream projected local search.
    views = solver.solution_pool.projection_subpools(adapter_path(adapter, adapter))
    assert len(views) == 4 and adapter.pop_F.shape == (4, 2)
    for view in views:
        batch = solver.read_solutions(solver.solution_pool.subpool_refs(view))
        assert batch.numeric_matrix.shape == (1, 1)


def test_change_composition_order_changes_candidates_without_rewriting_moead():
    first, _ = make(mutate_then_cross)
    second, _ = make(cross_then_mutate)
    for solver in (first, second):
        assert solver.step().committed
        assert solver.step().committed
    left = first._last_evaluated_event_batch.numeric_matrix
    right = second._last_evaluated_event_batch.numeric_matrix
    assert np.all(left > right)


def test_evaluation_failure_restores_rng_directions_members_and_exact_refs():
    solver, adapter = make(random_direction_change)
    assert solver.step().committed
    old_state = copy.deepcopy(adapter.get_state())
    refs = adapter.get_population_solution_refs(solver)
    population = np.array(adapter.pop_X, copy=True)
    old_generation = solver.generation
    solver.problem.fail = True
    before_calls = len(solver.problem.seen)
    with pytest.raises(RuntimeError, match="intentional change evaluation failure"):
        solver.step()
    failed_candidates = np.array(solver.problem.seen[before_calls:], copy=True)
    assert adapter._rng.bit_generator.state == old_state["rng_state"]
    assert adapter._pending_indices == old_state["pending_indices"]
    assert adapter._pending_modes == old_state["pending_modes"]
    assert adapter.get_population_solution_refs(solver) == refs
    np.testing.assert_array_equal(adapter.pop_X, population)
    assert solver.generation == old_generation
    solver.problem.fail = False
    before_calls = len(solver.problem.seen)
    assert solver.step().committed
    retried_candidates = np.array(solver.problem.seen[before_calls:], copy=True)
    # A failure may stop evaluation at the first row. Every evaluated prefix
    # must nevertheless repeat the same random candidate after rollback.
    np.testing.assert_array_equal(retried_candidates[:len(failed_candidates)], failed_candidates)


def test_nonprefix_admission_keeps_custom_change_direction_mapping(monkeypatch):
    solver, adapter = make(batch_size=3)
    assert solver.step().committed
    requests = capture_requests(monkeypatch, adapter)

    class NonPrefix:
        policy_id = "plain-change-non-prefix/v1"

        def select(self, candidates, feedback, context):
            return BatchDisposition(proposed_count=3, accepted_indices=(0, 2), reason="test")

    solver.set_evaluation_acceptance_policy(NonPrefix())
    assert solver.step().committed
    assert len(requests) == 3
    assert adapter._pending_indices == [requests[index].parameters["subproblem_index"] for index in (0, 2)]
    assert adapter._pending_modes == [requests[index].parameters["mode"] for index in (0, 2)]
    assert len(adapter.get_population_solution_refs(solver)) == 4


def test_checkpoint_rejects_a_different_change_function_before_replacing_members():
    solver, adapter = make()
    assert solver.step().committed
    saved = copy.deepcopy(adapter.get_state())
    _, other = make(cross_then_mutate)
    assert other.algorithm_unit is None
    with pytest.raises(ValueError, match="identity|assembly|binding|match"):
        other.set_state(saved)
    assert other.algorithm_unit is None


def test_bad_change_shape_fails_before_any_evaluation_and_restores_slots():
    solver, adapter = make(wrong_shape_change)
    assert solver.step().committed
    old_calls = len(solver.problem.seen)
    old_rng = copy.deepcopy(adapter._rng.bit_generator.state)
    with pytest.raises((TypeError, ValueError), match="shape|dimension|candidate|one"):
        solver.step()
    assert len(solver.problem.seen) == old_calls
    assert adapter._rng.bit_generator.state == old_rng
    assert adapter._pending_indices == [] and adapter._pending_modes == []


def test_direct_mutator_and_named_pipeline_mutation_conflict_with_change():
    from nsgablack.representation import GaussianMutation

    with pytest.raises(ValueError, match="change|mutator|exclusive"):
        MOEADAdapter(change=mutate_then_cross, mutator=GaussianMutation(sigma=.1))
    adapter = MOEADAdapter(change=mutate_then_cross)
    with pytest.raises(ValueError, match="change|mutation|exclusive"):
        adapter.set_mutation_operator("named")
