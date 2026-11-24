"""Real steps for initializer ownership without replacing structured search."""
from __future__ import annotations

import copy

import numpy as np
import pytest
from blackbase.types import CandidateBatch, UnknownState

from nsgablack.adapters import (
    AStarAdapter, FixedCandidateAdapter, GradientDescentAdapter, MASAdapter,
    MOAStarAdapter, TrustRegionDFOAdapter, TrustRegionMODFOAdapter,
    TrustRegionNonSmoothAdapter, TrustRegionSubspaceAdapter,
)
from nsgablack.context_keys import KEY_SOLUTION_INPUT_REF
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.plugins import CheckpointResumePlugin
from nsgablack.representation import JointRepairPolicy, RepresentationPipeline
from nsgablack.representation.structure_builders import encode_unit_value, decode_unit_value
from nsgablack.units.contracts import candidate_array


KINDS = ("tr_dfo", "tr_mo", "tr_nonsmooth", "tr_subspace", "finite_difference",
         "mas", "fixed", "astar", "moa_star")


class Sphere(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=2, objectives=["min"], bounds=[(-10., 10.)] * 2)
        self.seen = []
        self.fail = False

    def evaluate(self, candidate):
        self.seen.append(np.array(candidate, copy=True))
        if self.fail:
            raise RuntimeError("structured operation evaluation failure")
        return [float(np.sum(np.asarray(candidate) ** 2))]


class CountingInitializer:
    def __init__(self, value=2.):
        self.value = float(value)
        self.calls = 0

    def checkpoint_identity(self):
        return {"value": self.value}

    def initialize(self, problem, context):
        self.calls += 1
        return np.full(problem.dimension, self.value)

    def get_state(self):
        return {"calls": self.calls}

    def set_state(self, state):
        self.calls = int(state["calls"])


class ProblemBounds:
    def repair(self, candidate, context):
        return np.clip(candidate, -10., 10.)

    def validate(self, candidate, context):
        return bool(np.all(np.abs(candidate.values) <= 10.))


class CountingUnitRepair:
    def __init__(self):
        self.calls = 0

    def checkpoint_identity(self):
        return {"kind": "identity_unit_repair"}

    def repair(self, unit, evidence, context):
        self.calls += 1
        return evidence.after

    def validate(self, unit, evidence, context):
        return True

    def get_state(self):
        return {"calls": self.calls}

    def set_state(self, state):
        self.calls = int(state["calls"])


def adapter_for(kind, *, initializer=None, repair=None):
    kwargs = {"initializer": initializer}
    if repair is not None:
        kwargs["repair"] = repair
    if kind == "tr_dfo":
        return TrustRegionDFOAdapter(batch_size=3, **kwargs)
    if kind == "tr_mo":
        return TrustRegionMODFOAdapter(batch_size=3, **kwargs)
    if kind == "tr_nonsmooth":
        return TrustRegionNonSmoothAdapter(batch_size=3, **kwargs)
    if kind == "tr_subspace":
        return TrustRegionSubspaceAdapter(batch_size=3, subspace_dim=1, **kwargs)
    if kind == "finite_difference":
        return GradientDescentAdapter(**kwargs)
    if kind == "mas":
        return MASAdapter(batch_size=3, enable_surrogate=False, **kwargs)
    if kind == "fixed":
        return FixedCandidateAdapter(**kwargs)
    cls = AStarAdapter if kind == "astar" else MOAStarAdapter
    return cls(neighbors=lambda state, context: (np.asarray(state) + .25,),
               pool_start_policy="new_root", **kwargs)


def solver_for(adapter, *, problem_repair=None, joint=False):
    solver = ComposableSolver(
        Sphere(), adapter=adapter,
        representation_pipeline=RepresentationPipeline(repair=problem_repair),
        joint_repair_policy=JointRepairPolicy() if joint else None,
    )
    solver.set_random_seed(79)
    solver.setup()
    return solver


@pytest.mark.parametrize("kind", KINDS)
def test_structured_initializer_reaches_real_evaluation_without_pipeline_source(kind):
    initial = CountingInitializer()
    adapter = adapter_for(kind, initializer=initial)
    solver = solver_for(adapter)
    assert initial.calls == 0
    assert solver.step().committed
    assert initial.calls == 1
    np.testing.assert_array_equal(solver.problem.seen, [[2., 2.]])
    assert solver.evaluation_count == 1
    assert set(adapter.get_local_operator_bindings()) == {"initializer"}


@pytest.mark.parametrize("kind", ("fixed", "astar", "moa_star"))
def test_semantic_initializer_preserves_event_metadata_and_exact_pool_identity(kind):
    class SemanticInitializer(CountingInitializer):
        def initialize(self, problem, context):
            self.calls += 1
            return UnknownState(np.full(problem.dimension, self.value),
                                {"source": "semantic-initializer", "tags": ["exact", "seed"]})

    initial = SemanticInitializer()
    adapter = adapter_for(kind, initializer=initial)
    solver = solver_for(adapter)
    assert solver.step().committed
    event = solver._last_evaluated_event_batch
    assert event.semantic_states[0].metadata["source"] == "semantic-initializer"
    assert tuple(event.semantic_states[0].metadata["tags"]) == ("exact", "seed")
    ref, = solver.solution_pool.select()
    assert ref.candidate_token == event.candidate_tokens[0]
    assert solver._last_evaluated_event_provenance[0].candidate_token == ref.candidate_token
    published = solver.read_solutions((ref,))
    assert published.semantic_states[0].metadata == event.semantic_states[0].metadata
    np.testing.assert_array_equal(published.numeric_matrix, [[2., 2.]])
    if kind == "fixed":
        assert isinstance(adapter.current_unit.to_candidate(), UnknownState)
        assert adapter.current_unit.to_candidate().metadata == event.semantic_states[0].metadata
        assert adapter.get_solution_pool_roots(solver) == (ref,)
    else:
        node = adapter._open[0][2] if kind == "astar" else next(iter(adapter._labels.values()))
        np.testing.assert_array_equal(node.state, published.numeric_matrix[0])
        assert ref in adapter.get_solution_pool_roots(solver)
    assert initial.calls == 1


@pytest.mark.parametrize("kind", KINDS)
def test_explicit_pool_input_has_priority_over_bound_initializer(kind):
    initial = CountingInitializer(9.)
    adapter = adapter_for(kind, initializer=initial)
    solver = solver_for(adapter)
    refs = solver.store_solutions(CandidateBatch.from_candidates(([3., 4.],),
                                                              candidate_tokens=("input-seed",)))
    input_key = solver.solution_pool.bind_input(refs)
    proposed = adapter.propose(solver, {KEY_SOLUTION_INPUT_REF: input_key})
    assert initial.calls == 0
    np.testing.assert_array_equal([candidate_array(row) for row in proposed], [[3., 4.]])
    assert solver.solution_pool.input_remaining(input_key) == 0


@pytest.mark.parametrize("kind", KINDS)
def test_exception_rolls_back_initializer_and_search_baseline_together(kind):
    initial = CountingInitializer()
    adapter = adapter_for(kind, initializer=initial)
    solver = solver_for(adapter)
    before = copy.deepcopy(adapter.get_state())
    solver.problem.fail = True
    with pytest.raises(RuntimeError, match="structured operation evaluation failure"):
        solver.step()
    assert initial.calls == 0
    assert adapter.get_state() == before
    assert solver._latest_snapshot_handle is None
    solver.problem.fail = False
    assert solver.step().committed
    assert initial.calls == 1


@pytest.mark.parametrize("kind", KINDS)
def test_structured_checkpoint_restores_binding_without_rerunning_initialization(kind):
    source = adapter_for(kind, initializer=CountingInitializer())
    solver = solver_for(source)
    assert solver.step().committed
    saved = source.get_state()
    restored_initial = CountingInitializer()
    restored = adapter_for(kind, initializer=restored_initial)
    solver_for(restored)
    assert restored_initial.calls == 0
    restored.set_state(saved)
    assert restored_initial.calls == 1
    assert restored.get_state() == saved


@pytest.mark.parametrize("kind", KINDS)
def test_restore_rejects_missing_binding_before_changing_algorithm_state(kind):
    source = adapter_for(kind, initializer=CountingInitializer())
    solver = solver_for(source)
    assert solver.step().committed
    target = adapter_for(kind)
    solver_for(target)
    before = copy.deepcopy(target.get_state())
    with pytest.raises(ValueError):
        target.set_state(source.get_state())
    assert target.get_state() == before


@pytest.mark.parametrize("kind", KINDS)
def test_restore_rejects_different_initializer_configuration(kind):
    source = adapter_for(kind, initializer=CountingInitializer())
    target_initial = CountingInitializer(7.)
    target = adapter_for(kind, initializer=target_initial)
    with pytest.raises(ValueError):
        target.set_state(source.get_state())
    assert target_initial.calls == 0


@pytest.mark.parametrize("kind", KINDS)
def test_formal_checkpoint_restores_pool_and_binding_before_continuing(kind):
    initial = CountingInitializer()
    source = solver_for(adapter_for(kind, initializer=initial))
    assert source.step().committed
    writer = CheckpointResumePlugin()
    writer.attach(source)
    payload = writer._build_payload(solver=source, reason="structured-operation-binding")
    restored_initial = CountingInitializer()
    restored = solver_for(adapter_for(kind, initializer=restored_initial))
    reader = CheckpointResumePlugin()
    reader.attach(restored)
    reader._restore_payload(solver=restored, payload=payload)
    assert restored.adapter.get_state() == source.adapter.get_state()
    assert restored_initial.calls == initial.calls == 1
    assert source.step().committed and restored.step().committed
    np.testing.assert_array_equal(restored._last_evaluated_event_batch.numeric_matrix,
                                  source._last_evaluated_event_batch.numeric_matrix)
    assert restored_initial.calls == initial.calls


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("role", ("mutator", "selector"))
def test_structured_search_does_not_claim_plain_mutation_or_selection(kind, role):
    adapter = adapter_for(kind)
    with pytest.raises((TypeError, ValueError)):
        getattr(adapter, f"set_{role}")(object())


@pytest.mark.parametrize("kind", ("tr_dfo", "tr_mo", "tr_nonsmooth", "tr_subspace", "finite_difference", "mas"))
def test_unit_repair_binding_uses_joint_repair_and_joins_step_rollback(kind):
    initial, repair = CountingInitializer(), CountingUnitRepair()
    adapter = adapter_for(kind, initializer=initial, repair=repair)
    solver = solver_for(adapter, problem_repair=ProblemBounds(), joint=True)
    solver.problem.fail = True
    with pytest.raises(RuntimeError, match="structured operation evaluation failure"):
        solver.step()
    assert initial.calls == repair.calls == 0
    solver.problem.fail = False
    outcome = solver.step()
    assert outcome.committed and initial.calls == repair.calls == 1
    assert outcome.metadata["joint_repair"]["status"] == "verified"
    np.testing.assert_array_equal(solver.problem.seen[-1], [2., 2.])


@pytest.mark.parametrize("kind", ("fixed", "astar", "moa_star"))
def test_multi_or_candidate_unit_owners_reject_single_unit_repair(kind):
    adapter = adapter_for(kind)
    with pytest.raises((TypeError, ValueError)):
        adapter.set_repair(CountingUnitRepair())


@pytest.mark.parametrize("kind", ("fixed", "moa_star"))
def test_empty_legacy_restore_does_not_bypass_a_live_binding(kind):
    adapter_for(kind).set_state(None)
    with pytest.raises(ValueError, match="bindings"):
        adapter_for(kind, initializer=CountingInitializer()).set_state(None)


@pytest.mark.parametrize("kind", ("fixed", "astar", "moa_star"))
def test_invalid_algorithm_payload_compensates_restored_operator_state(kind):
    initial = CountingInitializer()
    adapter = adapter_for(kind, initializer=initial)
    solver = solver_for(adapter)
    assert solver.step().committed
    bad = copy.deepcopy(adapter.get_state())
    bad["operator_bindings"]["initializer"]["state"]["calls"] = 999
    if kind == "astar":
        frontier = decode_unit_value(bad["frontier_state"])
        frontier["summary"]["pool_start_policy"] = "invalid_root_policy"
        bad["frontier_state"] = encode_unit_value(frontier)
    elif kind == "moa_star":
        bad["pool_start_policy"] = "invalid_root_policy"
    else:
        bad["unit_contract"] = {}
    with pytest.raises(ValueError):
        adapter.set_state(bad)
    assert initial.calls == 1


def test_invalid_frontier_step_restore_compensates_operator_state():
    initial = CountingInitializer()
    adapter = adapter_for("astar", initializer=initial)
    solver = solver_for(adapter)
    assert solver.step().committed
    bad = adapter.snapshot_step_state()
    bad["operator_bindings"]["initializer"]["state"]["calls"] = 999
    bad["summary"]["pool_start_policy"] = "invalid_root_policy"
    with pytest.raises(ValueError):
        adapter.restore_step_state(bad)
    assert initial.calls == 1


@pytest.mark.parametrize("cls", (AStarAdapter, MOAStarAdapter))
def test_graph_root_sources_cannot_be_ambiguous(cls):
    with pytest.raises(ValueError, match="alternative root sources"):
        cls(neighbors=lambda state, context: (), start_state=np.zeros(2),
            initializer=CountingInitializer())


def test_trust_region_repair_still_rejects_candidate_outside_sampling_region():
    class MoveOutside(ProblemBounds):
        def repair(self, candidate, context):
            return np.asarray(candidate) + 5.

    adapter = TrustRegionDFOAdapter(batch_size=3, initializer=CountingInitializer(0.))
    solver = solver_for(adapter)
    assert solver.step().committed
    calls = solver.evaluation_count
    solver.set_representation_pipeline(RepresentationPipeline(repair=MoveOutside()))
    with pytest.raises(ValueError, match="outside the trust region"):
        solver.step()
    assert solver.evaluation_count == calls
