"""Real control-plane steps for independent NSGA parent/operator bindings."""
from __future__ import annotations

import copy
from dataclasses import replace

import numpy as np
import pytest
from blackbase.contracts import BatchDisposition
from blackbase.types import CandidateBatch, Feedback, UnknownState

from nsgablack.adapters import NSGA2Adapter, NSGA3Adapter, SPEA2Adapter
from nsgablack.adapters.nsga2.adapter import OperatorBindingRestoreError
from nsgablack.adapters.parent_selection import MixedPoolParentSelector, ParentSelectionRequest
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.core.evaluation_feedback import OptimizationFeedbackBatch
from nsgablack.core.state.solution_pool import SolutionRef
from nsgablack.plugins import CheckpointResumePlugin
from nsgablack.representation import ClipRepair, RepresentationPipeline, UniformInitializer


class Sphere(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, objectives=["min"], bounds=[(-100.0, 100.0)])
        self.seen = []
        self.fail = False

    def evaluate(self, candidate):
        self.seen.append(np.array(candidate, copy=True))
        if self.fail:
            raise RuntimeError("evaluation intentionally failed")
        return [float(np.sum(np.asarray(candidate) ** 2))]


class CountingMutation:
    def __init__(self, amount=-1.0):
        self.amount = float(amount)
        self.calls = 0

    def checkpoint_identity(self):
        return {"amount": self.amount}

    def mutate(self, candidate, context):
        self.calls += 1
        candidate[:] += self.amount  # Must only receive a detached draft.
        return candidate

    def get_state(self):
        return {"calls": self.calls}

    def set_state(self, state):
        self.calls = int(state["calls"])


class CountingSelector:
    def __init__(self, pool_name="elite"):
        self.pool_name = pool_name
        self.calls = 0

    def checkpoint_identity(self):
        return {"pool_name": self.pool_name}

    def select(self, request, *, pool, rng):
        self.calls += 1
        return MixedPoolParentSelector(self.pool_name).select(request, pool=pool, rng=rng)

    def get_state(self):
        return {"calls": self.calls}

    def set_state(self, state):
        self.calls = int(state["calls"])


def make_solver(*, selector=None, mutator=None, repair=None, adapter_type=NSGA2Adapter):
    selector = MixedPoolParentSelector("elite") if selector is None else selector
    mutator = CountingMutation() if mutator is None else mutator
    adapter = adapter_type(population_size=4, offspring_size=2, crossover_rate=0.0,
                           parent_selector=selector, mutator=mutator)
    pipeline = RepresentationPipeline(initializer=UniformInitializer(low=2.0, high=2.0), repair=repair)
    solver = ComposableSolver(Sphere(), adapter=adapter, representation_pipeline=pipeline)
    solver.set_random_seed(47)
    solver.setup()
    return solver, adapter, mutator


def publish_elites(solver, name="elite", *, value=20.0, metadata=None):
    batch = CandidateBatch.from_candidates((UnknownState([value], metadata or {}),), candidate_tokens=(f"{name}-token",))
    feedback = OptimizationFeedbackBatch.from_feedback((Feedback(objectives=[value ** 2]),), violations=[0.0])
    refs = solver.solution_pool.put(batch, stage="accepted", feedback=feedback)
    solver.solution_pool.create_subpool(name, refs)
    return refs


def parents_for_latest_event(solver):
    return tuple(tuple(SolutionRef.from_dict(ref) for ref in provenance.metadata["parent_solution_refs"])
                 for provenance in solver._last_evaluated_event_provenance)


def test_mixed_pool_parents_use_exact_refs_without_mutating_either_source():
    solver, adapter, mutator = make_solver()
    assert solver.step().committed
    assert mutator.calls == 0  # Bootstrap is evaluated before any parent selection.
    assert solver.evaluation_count == 4
    assert len(adapter.get_population_solution_refs(solver)) == 4
    population_refs = adapter.get_population_solution_refs(solver)
    elite_refs = publish_elites(solver)
    source_values = np.array(solver.read_solutions(population_refs + elite_refs).numeric_matrix, copy=True)
    assert solver.step().committed
    parents = parents_for_latest_event(solver)
    flattened = tuple(ref for pair in parents for ref in pair)
    assert len(parents) == 2 and all(len(pair) == 2 for pair in parents)
    assert sum(ref in elite_refs for ref in flattened) == 2
    assert sum(ref in population_refs for ref in flattened) == 2
    assert mutator.calls == 2
    np.testing.assert_array_equal(solver.read_solutions(population_refs + elite_refs).numeric_matrix, source_values)
    source_tokens = {ref.candidate_token for ref in flattened}
    assert set(solver._last_evaluated_event_batch.candidate_tokens).isdisjoint(source_tokens)


def test_changing_pool_binding_changes_only_parent_source():
    solver, adapter, _ = make_solver(selector=MixedPoolParentSelector("first", 1.0))
    solver.step()
    first = publish_elites(solver, "first", value=15.0)
    second = publish_elites(solver, "second", value=25.0)
    solver.step()
    assert all(ref in first for pair in parents_for_latest_event(solver) for ref in pair)
    adapter.set_parent_selector(MixedPoolParentSelector("second", 1.0))
    solver.step()
    assert all(ref in second for pair in parents_for_latest_event(solver) for ref in pair)


def test_numeric_variation_preserves_external_parent_semantic_metadata():
    solver, _, _ = make_solver(selector=MixedPoolParentSelector("elite", 1.0))
    solver.step()
    refs = publish_elites(solver, metadata={"family": "external", "tags": ["exact", "version"]})
    solver.step()
    for state in solver._last_evaluated_event_batch.semantic_states:
        assert state.metadata["family"] == "external"
        assert tuple(state.metadata["tags"]) == ("exact", "version")
    original, = solver.read_solutions(refs).semantic_states
    assert original.metadata["family"] == "external"
    np.testing.assert_array_equal(original.values, [20.0])


def test_selector_bootstrap_preserves_semantic_initializer_output():
    class SemanticInitializer:
        def initialize(self, problem, context):
            return UnknownState([2.0], {"family": "initial-seed"})

    adapter = NSGA2Adapter(population_size=4, offspring_size=2,
        parent_selector=MixedPoolParentSelector("elite"), mutator=CountingMutation())
    solver = ComposableSolver(Sphere(), adapter=adapter,
        representation_pipeline=RepresentationPipeline(initializer=SemanticInitializer()))
    solver.setup()
    assert solver.step().committed
    assert all(state.metadata["family"] == "initial-seed"
               for state in solver._last_evaluated_event_batch.semantic_states)
    states = solver.read_solutions(adapter.get_population_solution_refs(solver)).semantic_states
    assert all(state.metadata["family"] == "initial-seed" for state in states)


def test_semantic_mutator_output_is_retained_in_numeric_adapter_projection():
    class SemanticMutation:
        stateless = True

        def checkpoint_identity(self):
            return {"kind": "semantic-mutation"}

        def mutate(self, candidate, context):
            return UnknownState(candidate - 1.0, {"changed_by": "semantic-operator"})

    solver, _, _ = make_solver(mutator=SemanticMutation())
    solver.step()
    publish_elites(solver)
    assert solver.step().committed
    assert all(state.metadata["changed_by"] == "semantic-operator"
               for state in solver._last_evaluated_event_batch.semantic_states)


def test_direct_semantic_mutator_also_works_without_custom_parent_selection():
    class SemanticMutation:
        stateless = True

        def checkpoint_identity(self):
            return {"kind": "direct-semantic"}

        def mutate(self, candidate, context):
            return UnknownState(candidate + 1.0, {"family": "semantic-result"})

    adapter = NSGA2Adapter(population_size=4, offspring_size=2, mutator=SemanticMutation())
    solver = ComposableSolver(Sphere(), adapter=adapter,
        representation_pipeline=RepresentationPipeline(initializer=UniformInitializer(low=2.0, high=2.0)))
    solver.setup()
    assert solver.step().committed
    assert all(state.metadata["family"] == "semantic-result"
               for state in solver._last_evaluated_event_batch.semantic_states)


@pytest.mark.parametrize("empty", [False, True])
def test_missing_or_empty_parent_pool_fails_before_evaluation(empty):
    solver, adapter, mutator = make_solver()
    solver.step()
    if empty:
        solver.solution_pool.create_subpool("elite")
    before = adapter.get_state()
    calls = len(solver.problem.seen)
    with pytest.raises(ValueError, match="parent selection pool"):
        solver.step()
    assert adapter.get_state() == before
    assert len(solver.problem.seen) == calls
    assert mutator.calls == 0


def test_partial_admission_and_problem_repair_preserve_child_and_parent_identities(monkeypatch):
    solver, adapter, _ = make_solver(mutator=CountingMutation(10.0), repair=ClipRepair(low=0.0, high=3.0))
    solver.step()
    elite_refs = publish_elites(solver)
    before = set(solver.solution_pool.select())
    evidence = []
    ordinary = adapter.on_proposal_repair

    def capture(control, repair, context):
        evidence.append(repair)
        ordinary(control, repair, context)

    monkeypatch.setattr(adapter, "on_proposal_repair", capture)

    class Partial:
        policy_id = "pool-parent-partial"

        def select(self, candidates, feedback, context):
            return BatchDisposition(len(candidates.semantic_states), (1,))

    solver.set_evaluation_acceptance_policy(Partial())
    assert solver.step().committed
    assert len(evidence) == 1
    repair = evidence[0]
    assert repair.before.candidate_tokens == repair.after.candidate_tokens
    np.testing.assert_array_equal(repair.after.numeric_matrix, [[3.0], [3.0]])
    accepted = set(solver.solution_pool.select()) - before
    assert len(accepted) == 1
    ref, = accepted
    assert ref.candidate_token == solver._last_evaluated_event_batch.candidate_tokens[1]
    assert ref.candidate_token not in {parent.candidate_token for pair in parents_for_latest_event(solver) for parent in pair}
    assert any(parent in elite_refs for pair in parents_for_latest_event(solver) for parent in pair)
    np.testing.assert_array_equal(solver.read_solutions((ref,)).numeric_matrix, [[3.0]])


def test_failed_step_restores_selector_mutator_and_rng_before_retry():
    selector = CountingSelector()
    solver, adapter, mutator = make_solver(selector=selector)
    solver.step()
    publish_elites(solver)
    saved = copy.deepcopy(adapter.get_state())
    pool_refs = solver.solution_pool.select()
    seen = len(solver.problem.seen)
    solver.problem.fail = True
    with pytest.raises(RuntimeError, match="intentionally failed"):
        solver.step()
    assert adapter.get_state() == saved
    assert solver.solution_pool.select() == pool_refs
    assert selector.calls == mutator.calls == 0
    solver.problem.fail = False
    assert solver.step().committed
    assert selector.calls == 1 and mutator.calls == 2
    np.testing.assert_array_equal(solver.problem.seen[seen], solver.problem.seen[seen + 1])


def test_formal_checkpoint_restores_bound_components_and_continuation():
    source, source_adapter, source_mutator = make_solver(selector=CountingSelector())
    source.step()
    publish_elites(source)
    source.step()
    writer = CheckpointResumePlugin()
    writer.attach(source)
    payload = writer._build_payload(solver=source, reason="bound-pool-parent-operators")
    restored, restored_adapter, restored_mutator = make_solver(selector=CountingSelector())
    reader = CheckpointResumePlugin()
    reader.attach(restored)
    reader._restore_payload(solver=restored, payload=payload)
    assert restored_adapter.get_state() == source_adapter.get_state()
    assert restored_mutator.calls == source_mutator.calls == 2
    assert source.step().committed and restored.step().committed
    np.testing.assert_array_equal(restored.population, source.population)
    assert restored_mutator.calls == source_mutator.calls == 4


def test_checkpoint_refuses_missing_extra_or_changed_binding_identity():
    solver, adapter, _ = make_solver()
    solver.step()
    state = adapter.get_state()
    for candidate in (
        NSGA2Adapter(population_size=4),
        NSGA2Adapter(population_size=4, parent_selector=MixedPoolParentSelector("other"), mutator=CountingMutation()),
        NSGA2Adapter(population_size=4, parent_selector=MixedPoolParentSelector("elite"), mutator=CountingMutation(5.0)),
    ):
        with pytest.raises(ValueError, match="(binding|identity|assembly)"):
            candidate.set_state(state)
    missing = copy.deepcopy(state)
    missing.pop("operator_bindings")
    with pytest.raises(ValueError, match="bindings"):
        adapter.set_state(missing)
    with pytest.raises(ValueError, match="bindings"):
        adapter.set_state({})


def test_binding_identity_failure_does_not_restore_an_earlier_component_first():
    solver, adapter, mutator = make_solver(selector=CountingSelector())
    solver.step()
    publish_elites(solver)
    solver.step()
    before = adapter.get_state()
    bad = copy.deepcopy(before)
    bad["operator_bindings"]["parent_selector"]["state"]["calls"] = 900
    bad["operator_bindings"]["mutator"]["identity"]["amount"] = 999.0
    with pytest.raises(ValueError, match="identity"):
        adapter.set_state(bad)
    assert adapter.get_state() == before and mutator.calls == 2


def test_component_restore_failure_compensates_all_touched_bindings():
    class RefusingMutation(CountingMutation):
        def set_state(self, state):
            super().set_state(state)
            if self.calls > 10:
                raise ValueError("component refused state")

    solver, adapter, _ = make_solver(selector=CountingSelector(), mutator=RefusingMutation())
    solver.step()
    publish_elites(solver)
    solver.step()
    before = adapter.get_state()
    bad = copy.deepcopy(before)
    bad["operator_bindings"]["parent_selector"]["state"]["calls"] = 900
    bad["operator_bindings"]["mutator"]["state"]["calls"] = 500
    with pytest.raises(ValueError, match="component refused"):
        adapter.set_state(bad)
    assert adapter.get_state() == before


def test_compensation_failure_preserves_original_cause_and_attempts_other_bindings():
    class PoisonedMutation(CountingMutation):
        fail_restore = False

        def set_state(self, state):
            super().set_state(state)
            if self.fail_restore:
                raise ValueError(f"codec refused calls={self.calls}")

    selector = CountingSelector()
    mutator = PoisonedMutation()
    solver, adapter, _ = make_solver(selector=selector, mutator=mutator)
    solver.step()
    publish_elites(solver)
    solver.step()
    saved = adapter.get_state()
    bad = copy.deepcopy(saved)
    bad["operator_bindings"]["parent_selector"]["state"]["calls"] = 900
    bad["operator_bindings"]["mutator"]["state"]["calls"] = 500
    mutator.fail_restore = True
    with pytest.raises(OperatorBindingRestoreError) as caught:
        adapter.set_state(bad)
    error = caught.value
    assert error.__cause__ is error.original_error
    assert "calls=500" in str(error.original_error)
    assert len(error.compensation_errors) == 1
    assert "calls=2" in str(error.compensation_errors[0])
    assert selector.calls == saved["operator_bindings"]["parent_selector"]["state"]["calls"]


def test_legacy_state_without_bindings_still_roundtrips():
    adapter = NSGA2Adapter(population_size=4)
    saved = adapter.get_state()
    assert "operator_bindings" not in saved
    clone = NSGA2Adapter(population_size=4)
    clone.set_state(saved)
    assert clone.get_state() == saved


def test_manual_population_without_exact_refs_cannot_supply_pool_parents():
    solver, adapter, _ = make_solver()
    adapter.set_population_snapshot(np.array([[1.0], [2.0]]), np.array([[1.0], [4.0]]), np.zeros(2))
    publish_elites(solver)
    with pytest.raises(ValueError, match="(binding|reference|pool)"):
        solver.step()


@pytest.mark.parametrize("result", [(), (0, 1, 2, 3), "not-refs"])
def test_selector_bad_result_is_rejected_before_variation_or_evaluation(result):
    class BadSelector:
        stateless = True

        def checkpoint_identity(self):
            return {"kind": "bad"}

        def select(self, request, *, pool, rng):
            return result

    solver, _, mutator = make_solver(selector=BadSelector())
    solver.step()
    before = len(solver.problem.seen)
    with pytest.raises(ValueError, match="exact SolutionRefs"):
        solver.step()
    assert len(solver.problem.seen) == before and mutator.calls == 0


def test_selector_wrong_token_cannot_impersonate_equal_valued_parent():
    class WrongReference:
        stateless = True

        def checkpoint_identity(self):
            return {"kind": "wrong-reference"}

        def select(self, request, *, pool, rng):
            bad = replace(request.population_refs[0], candidate_token="wrong-token")
            return (bad,) * request.count

    solver, _, _ = make_solver(selector=WrongReference())
    solver.step()
    with pytest.raises(ValueError, match="(token|identity|reference)"):
        solver.step()


@pytest.mark.parametrize("container", ["set", "frozenset", "mapping"])
def test_parent_selector_rejects_unordered_or_mapping_results(container):
    class UnorderedSelector:
        stateless = True

        def checkpoint_identity(self):
            return {"container": container}

        def select(self, request, *, pool, rng):
            assert len(request.population_refs) == request.count
            if container == "mapping":
                return dict.fromkeys(request.population_refs)
            return set(request.population_refs) if container == "set" else frozenset(request.population_refs)

    solver, _, mutator = make_solver(selector=UnorderedSelector())
    assert solver.step().committed
    before = len(solver.problem.seen)
    with pytest.raises(ValueError, match="ordered sequence"):
        solver.step()
    assert len(solver.problem.seen) == before and mutator.calls == 0


def test_parent_request_detaches_rankings_and_excludes_mutable_context():
    ref = SolutionRef("pool", "record", 0, "token")
    ranking = np.array([0])
    request = ParentSelectionRequest((ref,), ranking, np.array([np.inf]), 2, {"step": 2})
    ranking[0] = 9
    assert request.rank[0] == 0
    with pytest.raises(ValueError):
        request.rank.setflags(write=True)
    with pytest.raises(TypeError):
        request.context["step"] = 3
    with pytest.raises(TypeError, match="scalar"):
        ParentSelectionRequest((ref,), [0], [1.0], 2, {"service": object()})


def test_direct_operator_context_and_artifact_contracts_remain_visible():
    class DeclaredMutation(CountingMutation):
        context_requires = ("mutation_sigma",)
        context_provides = ("candidate.changed",)
        context_mutates = ("candidate.draft",)
        context_cache = ("candidate.cache",)
        artifact_requires = ("artifact.model",)
        artifact_provides = ("artifact.proposal",)
        phase_in = ("search",)
        phase_out = ("evaluation",)

    class DeclaredSelector(CountingSelector):
        context_requires = ("phase",)
        artifact_requires = ("artifact.parent-index",)

    adapter = NSGA2Adapter(parent_selector=DeclaredSelector(), mutator=DeclaredMutation())
    contract = adapter.get_context_contract()
    assert set(contract["requires"]) == {"mutation_sigma", "phase"}
    assert "candidate.changed" in contract["provides"]
    assert contract["mutates"] == ["candidate.draft"]
    assert contract["cache"] == ["candidate.cache"]
    assert set(contract["artifact_requires"]) == {"artifact.model", "artifact.parent-index"}
    assert contract["artifact_provides"] == ["artifact.proposal"]
    assert contract["phase_in"] == ["search"] and contract["phase_out"] == ["evaluation"]
    assert "pool_name" not in contract["requires"]


@pytest.mark.parametrize("adapter_type", [NSGA3Adapter, SPEA2Adapter])
def test_inherited_adapters_accept_explicit_bindings_without_config_leakage(adapter_type):
    solver, adapter, mutator = make_solver(adapter_type=adapter_type)
    assert set(adapter.get_local_operator_bindings()) == {"parent_selector", "mutator"}
    assert solver.step().committed
    publish_elites(solver)
    assert solver.step().committed
    assert mutator.calls == 2
