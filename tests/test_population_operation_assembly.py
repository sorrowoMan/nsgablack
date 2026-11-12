"""The same assembly boundary preserves each population algorithm's rules."""
from __future__ import annotations

import copy

import numpy as np
import pytest
from blackbase.contracts import BatchDisposition
from blackbase.types import UnknownState

from nsgablack.adapters import (
    DifferentialEvolutionAdapter, MOEADAdapter, NSGA2Adapter, NSGA3Adapter, SPEA2Adapter,
)
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.representation import ClipRepair, RepresentationPipeline


class BiSphere(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, objectives=["left", "right"], bounds=[(-100.0, 100.0)])
        self.fail = False
        self.seen = []

    def evaluate(self, candidate):
        self.seen.append(np.array(candidate, copy=True))
        if self.fail:
            raise RuntimeError("intentional population evaluation failure")
        value = float(np.asarray(candidate)[0])
        return [value * value, (value - 3.0) ** 2]


class SeedSequence:
    def __init__(self):
        self.calls = 0

    def checkpoint_identity(self):
        return {"kind": "ordered-seeds"}

    def initialize(self, problem, context):
        self.calls += 1
        return UnknownState([float(self.calls)], {"family": "direct-initialization"})

    def get_state(self):
        return {"calls": self.calls}

    def set_state(self, state):
        self.calls = int(state["calls"])


class Shift:
    def __init__(self, amount=-0.25):
        self.amount = float(amount)
        self.calls = 0

    def checkpoint_identity(self):
        return {"amount": self.amount}

    def mutate(self, candidate, context):
        self.calls += 1
        return UnknownState(np.asarray(candidate) + self.amount, {"changed_by": "direct-shift"})

    def get_state(self):
        return {"calls": self.calls}

    def set_state(self, state):
        self.calls = int(state["calls"])


class SelectLatest:
    """A deliberately explicit policy override, including worse replacements."""
    def __init__(self):
        self.calls = 0
        self.requests = []

    def checkpoint_identity(self):
        return {"kind": "latest"}

    def select(self, request, *, rng):
        self.calls += 1
        self.requests.append(request)
        assert not request.candidates.flags.writeable
        assert not request.objectives.flags.writeable
        assert not request.violations.flags.writeable
        return tuple(range(len(request.candidates) - request.count, len(request.candidates)))

    def get_state(self):
        return {"calls": self.calls}

    def set_state(self, state):
        self.calls = int(state["calls"])


def make(kind, *, batch=2, variation="pipeline"):
    initializer, mutator, selector = SeedSequence(), Shift(), SelectLatest()
    options = {"population_size": 4, "initializer": initializer, "mutator": mutator, "selector": selector}
    if kind in (NSGA2Adapter, NSGA3Adapter, SPEA2Adapter):
        options.update(offspring_size=batch, crossover_rate=0.0)
    elif kind is MOEADAdapter:
        options.update(batch_size=batch, neighborhood_size=4, nr=2, variation=variation)
    else:
        options.update(batch_size=batch)
    adapter = kind(**options)
    solver = ComposableSolver(BiSphere(), adapter=adapter,
        representation_pipeline=RepresentationPipeline(repair=ClipRepair(low=-100, high=100)))
    solver.set_random_seed(123)
    solver.setup()
    return solver, adapter, initializer, mutator, selector


@pytest.mark.parametrize("kind", [NSGA2Adapter, NSGA3Adapter, SPEA2Adapter,
                                  DifferentialEvolutionAdapter, MOEADAdapter])
def test_direct_operations_work_without_pipeline_search_components(kind):
    solver, adapter, initializer, mutator, selector = make(kind)
    assert solver.step().committed
    assert initializer.calls == 4
    assert mutator.calls == 0
    assert all(state.metadata["family"] == "direct-initialization"
               for state in solver._last_evaluated_event_batch.semantic_states)
    original_refs = tuple(adapter.get_population_solution_refs(solver))
    before = np.array(solver.read_solutions(original_refs).numeric_matrix, copy=True)
    assert solver.step().committed
    assert mutator.calls == 2
    assert selector.calls > 0
    np.testing.assert_array_equal(solver.read_solutions(original_refs).numeric_matrix, before)
    assert all(state.metadata["changed_by"] == "direct-shift"
               for state in solver._last_evaluated_event_batch.semantic_states)
    assert len(adapter.get_population_solution_refs(solver)) == 4
    expected = "survivor" if kind in (NSGA2Adapter, NSGA3Adapter, SPEA2Adapter) else "replacement"
    assert all(request.purpose == expected for request in selector.requests)


def test_de_duplicate_targets_expose_frozen_proposal_baselines():
    solver, adapter, _, _, selector = make(DifferentialEvolutionAdapter, batch=8)
    solver.step()
    old_x, old_f, old_v = (np.array(values, copy=True) for values in adapter.get_population_snapshot())
    solver.step()
    assert len(selector.requests) == 8
    targets = [request.parameters["target_index"] for request in selector.requests]
    assert len(set(targets)) < len(targets)
    for request, target in zip(selector.requests, targets):
        assert request.count == 1
        assert request.parameters["baseline"] == "proposal"
        np.testing.assert_array_equal(request.candidates[0], old_x[target])
        np.testing.assert_array_equal(request.objectives[0], old_f[target])
        assert request.violations[0] == old_v[target]


@pytest.mark.parametrize("kind", [NSGA2Adapter, NSGA3Adapter, SPEA2Adapter])
def test_survivor_selector_does_not_require_a_full_population_after_partial_admission(kind):
    solver, adapter, _, _, selector = make(kind, batch=2)

    class FirstOnly:
        policy_id = "test-first-only/v1"

        def select(self, candidates, feedback, context):
            return BatchDisposition(proposed_count=len(candidates.semantic_states),
                                    accepted_indices=(0,), reason="test")

    solver.set_evaluation_acceptance_policy(FirstOnly())
    assert solver.step().committed
    assert len(adapter.population) == 1
    assert solver.step().committed
    assert len(adapter.population) == 2
    assert selector.requests[-1].count == 2


def test_de_non_prefix_admission_keeps_baselines_and_targets_aligned(monkeypatch):
    solver, adapter, _, _, selector = make(DifferentialEvolutionAdapter, batch=3)
    solver.step()
    original_propose = adapter.propose
    captured = {}

    def propose(control, context):
        result = original_propose(control, context)
        captured["indices"] = tuple(adapter._last_target_indices)
        captured["baselines"] = copy.deepcopy(adapter._last_target_baselines)
        return result

    class NonPrefix:
        policy_id = "test-non-prefix/v1"

        def select(self, candidates, feedback, context):
            return BatchDisposition(proposed_count=3, accepted_indices=(0, 2), reason="test")

    monkeypatch.setattr(adapter, "propose", propose)
    solver.set_evaluation_acceptance_policy(NonPrefix())
    solver.step()
    assert len(selector.requests) == 2
    assert adapter._last_target_indices == [captured["indices"][i] for i in (0, 2)]
    for request, source_index in zip(selector.requests, (0, 2)):
        np.testing.assert_array_equal(request.candidates[0], captured["baselines"]["population"][source_index])


@pytest.mark.parametrize("variation", ["pipeline", "de"])
def test_moead_selection_keeps_direction_comparison_and_published_projection(variation):
    solver, adapter, _, mutator, selector = make(MOEADAdapter, variation=variation)
    solver.step()
    solver.step()
    assert mutator.calls == 2
    assert selector.requests
    for request in selector.requests:
        parameters = request.parameters
        assert parameters["algorithm"] == "moead"
        weight = np.asarray(parameters["weight"])
        ideal = np.asarray(parameters["ideal"])
        expected = np.max(weight * np.abs(request.objectives - ideal), axis=1)
        np.testing.assert_allclose(request.scores, expected)
        assert request.count == 1
    # Discover by actual creator ownership, not by a view-name prefix. The
    # direction members keep their ordinary multiobjective feedback.
    from nsgablack.adapters.subpools import adapter_path
    creator = adapter_path(solver.adapter, adapter)
    names = solver.solution_pool.projection_subpools(creator)
    assert len(names) == 4
    assert all(len(solver.read_solutions(solver.solution_pool.subpool_refs(name)).numeric_matrix) == 1
               for name in names)
    assert adapter.pop_F.shape == (4, 2)


@pytest.mark.parametrize("kind", [NSGA2Adapter, DifferentialEvolutionAdapter, MOEADAdapter])
def test_population_bound_components_and_members_rollback_on_evaluation_failure(kind):
    solver, adapter, initializer, mutator, selector = make(kind)
    solver.step()
    population = tuple(np.array(values, copy=True) for values in adapter.get_population_snapshot())
    previous = (initializer.calls, mutator.calls, selector.calls)
    refs = tuple(adapter.get_population_solution_refs(solver))
    solver.problem.fail = True
    with pytest.raises(RuntimeError, match="intentional population evaluation failure"):
        solver.step()
    assert (initializer.calls, mutator.calls, selector.calls) == previous
    for old, current in zip(population, adapter.get_population_snapshot()):
        np.testing.assert_array_equal(old, current)
    assert tuple(adapter.get_population_solution_refs(solver)) == refs


@pytest.mark.parametrize("kind", [NSGA2Adapter, DifferentialEvolutionAdapter, MOEADAdapter])
def test_population_operator_checkpoint_restores_binding_codecs(kind):
    solver, adapter, _, mutator, selector = make(kind)
    solver.step()
    solver.step()
    saved = copy.deepcopy(adapter.get_state())
    expected = (mutator.calls, selector.calls)
    mutator.calls += 10
    selector.calls += 20
    adapter.set_state(saved)
    assert (mutator.calls, selector.calls) == expected
    assert "operator_bindings" in saved


def test_parent_selection_is_not_advertised_for_differential_or_directional_replacement():
    for kind in (DifferentialEvolutionAdapter, MOEADAdapter):
        with pytest.raises((TypeError, ValueError), match="parent_selector|support"):
            kind().set_parent_selector(SelectLatest())
