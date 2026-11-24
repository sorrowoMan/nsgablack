"""Independently assembled trajectory roles preserve their algorithm guards."""
import copy
import warnings

import numpy as np
import pytest

from blackbase.contracts import BatchDisposition
from blackbase.types import CandidateBatch, UnknownState
from nsgablack.adapters import (
    GaussianSearchAdapter, PatternSearchAdapter, SimulatedAnnealingAdapter,
    SingleTrajectoryAdaptiveAdapter, VNSAdapter,
)
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.plugins import CheckpointResumeConfig, CheckpointResumePlugin
from nsgablack.representation import RepresentationPipeline
from nsgablack.representation import JointRepairPolicy
from nsgablack.units import UnitInputSpec


class Sphere(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, objectives=["minimize"], bounds=[(-100., 100.)])
        self.calls = []

    def evaluate(self, candidate):
        self.calls.append(float(candidate[0]))
        return [float(candidate[0]) ** 2]


class Initializer:
    def __init__(self, start=4.):
        self.start, self.calls = start, 0

    def checkpoint_identity(self):
        return {"kind": "trajectory_initializer", "start": self.start}

    def initialize(self, problem, context):
        self.calls += 1
        return np.array([self.start])

    def get_state(self):
        return {"calls": self.calls}

    def set_state(self, state):
        self.calls = state["calls"]


class Mutation:
    context_requires = ("mutation_sigma",)

    def __init__(self, offsets=(-1., 1.)):
        self.offsets, self.calls = tuple(offsets), 0

    def checkpoint_identity(self):
        return {"kind": "trajectory_mutation", "offsets": self.offsets}

    def mutate(self, candidate, context):
        offset = self.offsets[self.calls % len(self.offsets)]
        self.calls += 1
        return np.asarray(candidate) + offset

    def get_state(self):
        return {"calls": self.calls}

    def set_state(self, state):
        self.calls = state["calls"]


class Selector:
    def __init__(self, policy="last"):
        self.policy, self.calls, self.purposes = policy, 0, []

    def checkpoint_identity(self):
        return {"kind": "trajectory_selector", "policy": self.policy}

    def select(self, request, *, rng):
        self.calls += 1
        self.purposes.append(request.purpose)
        assert not request.objectives.flags.writeable
        assert not request.violations.flags.writeable
        if request.purpose == "proposal_order":
            return tuple(reversed(range(len(request.objectives))))
        if self.policy == "invalid":
            return (len(request.objectives),)
        if self.policy == "worst":
            return (int(np.argmax(request.scores)),)
        return (len(request.objectives) - 1,)

    def get_state(self):
        return {"calls": self.calls, "purposes": list(self.purposes)}

    def set_state(self, state):
        self.calls, self.purposes = state["calls"], list(state["purposes"])


class Repair:
    stateless = True

    def checkpoint_identity(self):
        return {"kind": "nonnegative_proposal"}

    def repair(self, candidate, context):
        return np.maximum(np.asarray(candidate), 0.)


def make_solver(kind, *, selector=None, offsets=(-1., 1.), start=4., **kwargs):
    initializer, mutation = Initializer(start), Mutation(offsets)
    common = {"initializer": initializer}
    if kind in {"sa", "vns", "single"}:
        common["mutator"] = mutation
    if selector is not None:
        common["selector"] = selector
    if kind == "sa":
        adapter = SimulatedAnnealingAdapter(batch_size=2, random_seed=3,
            initial_temperature=1e-6, cooling_rate=.5, min_temperature=1e-12, **common, **kwargs)
    elif kind == "vns":
        adapter = VNSAdapter(batch_size=2, restart_on_stagnation=False, **common, **kwargs)
    elif kind == "single":
        adapter = SingleTrajectoryAdaptiveAdapter(batch_size=2, accept_worse_prob=0.,
            restart_patience=1000, **common, **kwargs)
    elif kind == "pattern":
        adapter = PatternSearchAdapter(step_size=1., **common, **kwargs)
    else:
        adapter = GaussianSearchAdapter(initialization="center", population_size=3, **common, **kwargs)
    solver = ComposableSolver(Sphere(), adapter=adapter, representation_pipeline=RepresentationPipeline())
    solver.set_random_seed(7)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        solver.setup()
    assert not [item for item in caught if "mutat" in str(item.message).lower()]
    return solver, initializer, mutation


@pytest.mark.parametrize("kind", ("sa", "vns", "single", "pattern", "gaussian"))
def test_direct_initializer_uses_normal_evaluated_baseline_without_pipeline_search(kind):
    solver, initializer, mutation = make_solver(kind)
    assert solver.representation_pipeline.mutator is None
    assert solver.step().committed
    assert initializer.calls == 1 and mutation.calls == 0
    assert solver.problem.calls == [4.]
    selected, = solver.adapter.get_pool_refinement_results(solver)
    np.testing.assert_array_equal(solver.read_solutions((selected,)).numeric_matrix, [[4.]])


def test_sa_selector_changes_order_and_keeps_metropolis_and_one_cooling():
    selector = Selector()
    solver, _, mutation = make_solver("sa", selector=selector, offsets=(-1., -2.))
    adapter = solver.adapter
    assert solver.step().committed
    assert selector.calls == 0 and adapter.temperature == 1e-6
    assert solver.step().committed
    assert mutation.calls == 2 and selector.purposes == ["proposal_order"]
    np.testing.assert_array_equal(adapter.current_x, [2.])
    assert adapter.temperature == 5e-7

    solver, _, _ = make_solver("sa", selector=Selector(), offsets=(10., 20.))
    assert solver.step().committed and solver.step().committed
    np.testing.assert_array_equal(solver.adapter.current_x, [4.])


@pytest.mark.parametrize("kind", ("vns", "single", "pattern"))
def test_selector_nominates_candidate_but_cannot_override_improvement_guard_or_erase_best(kind):
    selector = Selector("worst")
    solver, _, _ = make_solver(kind, selector=selector)
    assert solver.step().committed
    assert selector.calls == 0
    assert solver.step().committed
    np.testing.assert_array_equal(solver.adapter.current_x, [4.])
    best, = solver.adapter.get_pool_refinement_results(solver)
    np.testing.assert_array_equal(solver.read_solutions((best,)).numeric_matrix, [[3.]])
    assert selector.purposes == ["candidate"]
    if kind == "vns":
        assert solver.adapter.k == 1
    elif kind == "pattern":
        assert solver.adapter.step_size < 1.


def test_single_stagnation_restart_uses_bound_initializer_and_rescores_baseline():
    solver, initializer, mutation = make_solver("single", selector=Selector("worst"))
    solver.adapter.cfg.restart_patience = 1
    assert solver.step().committed and solver.step().committed
    assert initializer.calls == 2 and solver.adapter.current_score is None
    assert mutation.calls == 2
    assert solver.step().committed
    assert mutation.calls == 2 and solver.adapter.current_score == 16.
    assert solver.problem.calls[-1] == 4.


@pytest.mark.parametrize("kind", ("sa", "vns", "single", "pattern"))
def test_bound_operation_failure_rolls_back_components_and_algorithm(kind, monkeypatch):
    solver, initializer, mutation = make_solver(kind, selector=Selector())
    assert solver.step().committed
    before = copy.deepcopy(solver.adapter.get_state())
    state = before["operator_bindings"]
    monkeypatch.setattr(solver, "_update_best", lambda *args, **kwargs:
        (_ for _ in ()).throw(RuntimeError("post update failure")))
    with pytest.raises(RuntimeError, match="post update failure"):
        solver.step()
    assert solver.adapter.operator_bindings_state() == state
    assert initializer.calls == 1 and mutation.calls == 0
    np.testing.assert_array_equal(solver.adapter.current_x, [4.])
    assert len(solver.problem.calls) == 3


def test_vns_selector_coordinates_follow_partial_admission():
    solver, _, _ = make_solver("vns", selector=Selector(), offsets=(-1., -2.))
    assert solver.step().committed
    class SecondOnly:
        def select(self, candidates, feedback, context):
            return BatchDisposition(len(candidates.semantic_states), (1,))
    solver.set_evaluation_acceptance_policy(SecondOnly())
    assert solver.step().committed
    np.testing.assert_array_equal(solver.adapter.current_x, [2.])
    selected, = solver.adapter.get_pool_refinement_results(solver)
    np.testing.assert_array_equal(solver.read_solutions((selected,)).numeric_matrix, [[2.]])
    assert solver.adapter._pending_units == []


@pytest.mark.parametrize("kind", ("sa", "vns", "single", "pattern"))
def test_formal_checkpoint_restores_operation_state_and_next_step(kind, tmp_path, monkeypatch):
    monkeypatch.setenv("NSGABLACK_CHECKPOINT_HMAC_KEY", "trajectory-operation-test-key")
    config = CheckpointResumeConfig(checkpoint_dir=str(tmp_path), save_on_finish=False)
    solver, _, _ = make_solver(kind, selector=Selector())
    assert solver.step().committed and solver.step().committed
    plugin = CheckpointResumePlugin(config=config)
    solver.add_plugin(plugin)
    path = plugin.save_checkpoint(reason="trajectory-operation")
    restored, _, _ = make_solver(kind, selector=Selector())
    reader = CheckpointResumePlugin(config=config)
    restored.add_plugin(reader)
    assert reader.resume(str(path))
    restored.run(max_steps=0)
    assert restored.adapter.operator_bindings_state() == solver.adapter.operator_bindings_state()
    assert restored.problem.calls == []
    assert solver.step().committed and restored.step().committed
    np.testing.assert_array_equal(restored.adapter.current_x, solver.adapter.current_x)
    expected, = solver.adapter.get_pool_refinement_results(solver)
    actual, = restored.adapter.get_pool_refinement_results(restored)
    np.testing.assert_array_equal(restored.read_solutions((actual,)).numeric_matrix,
                                  solver.read_solutions((expected,)).numeric_matrix)


def test_intrinsic_geometry_and_structural_repair_do_not_advertise_unimplemented_roles():
    for adapter in (GaussianSearchAdapter(), PatternSearchAdapter()):
        with pytest.raises((ValueError, TypeError), match="mutator|support"):
            adapter.set_mutator(Mutation())
    with pytest.raises((ValueError, TypeError), match="selector|support"):
        GaussianSearchAdapter().set_selector(Selector())
    with pytest.raises((ValueError, TypeError), match="repair|support"):
        VNSAdapter().set_repair(Repair())


@pytest.mark.parametrize("kind", ("sa", "single", "pattern", "gaussian"))
def test_bound_repair_uses_joint_draft_and_revalidates_problem_instead_of_bypassing_pipeline(kind):
    calls = []
    class Bounds:
        def repair(self, candidate, context):
            calls.append("problem_repair")
            return np.clip(candidate, 0., 3.)
        def validate(self, candidate, context):
            calls.append("problem_validate")
            return bool(np.all((candidate.values >= 0.) & (candidate.values <= 3.)))
    class UnitRepair:
        stateless = True
        def checkpoint_identity(self):
            return {"kind": "trajectory_joint_draft", "owner": kind}
        def repair(self, unit, evidence, context):
            calls.append("unit_repair")
            fixed = CandidateBatch.from_candidates(
                [state.with_values(np.minimum(state.values, 2.)) for state in evidence.after.semantic_states],
                candidate_tokens=evidence.after.candidate_tokens)
            setattr(unit, "best" if kind == "gaussian" else "current", fixed.numeric_matrix[0].copy())
            return fixed
        def validate(self, unit, evidence, context):
            calls.append("unit_validate")
            return bool(np.all(evidence.after.numeric_matrix <= 2.))

    solver, _, _ = make_solver(kind)
    solver.representation_pipeline.set_repair(Bounds())
    solver.adapter.set_repair(UnitRepair())
    solver.joint_repair_policy = JointRepairPolicy()
    outcome = solver.step()
    assert outcome.committed
    assert solver.problem.calls == [2.]
    assert calls.index("problem_repair") < calls.index("unit_repair")
    assert calls.index("unit_repair") < calls.index("problem_validate")
    assert "unit_validate" in calls
    assert outcome.metadata["joint_repair"]["status"] == "verified"


@pytest.mark.parametrize("kind", ("sa", "vns", "single"))
def test_direct_numeric_mutation_retains_semantic_envelope_and_derives_new_identity(kind):
    class SemanticInitializer(Initializer):
        def initialize(self, problem, context):
            self.calls += 1
            return UnknownState([self.start], {"domain": "preserved"})
    solver, _, _ = make_solver(kind, selector=Selector())
    solver.adapter.set_initializer(SemanticInitializer())
    assert solver.step().committed
    initial, = solver.adapter.get_pool_refinement_results(solver)
    assert solver.step().committed
    batch = solver.get_candidate_population_batch()
    assert batch.semantic_states
    assert all(state.metadata["domain"] == "preserved" for state in batch.semantic_states)
    accepted = solver.solution_pool.select(stage="accepted")
    descendants = tuple(ref for ref in accepted if ref.candidate_token != initial.candidate_token)
    assert descendants
    values = solver.solution_pool.read(descendants)
    assert all(state.metadata["domain"] == "preserved" for state in values.semantic_states)


@pytest.mark.parametrize("kind", ("sa", "vns", "single"))
def test_bound_mutation_reads_only_its_own_readonly_unit_input(kind):
    field = "candidate" if kind == "vns" else "current"
    seen = []
    class UnitMutation:
        stateless = True
        context_requires = ("mutation_sigma",)
        unit_inputs = UnitInputSpec(fields=(field,))
        def checkpoint_identity(self):
            return {"kind": "trajectory_unit_mutation", "field": field}
        def mutate(self, candidate, context, *, unit):
            own = unit.fields[field]
            own = own.values if isinstance(own, UnknownState) else own
            with pytest.raises(ValueError):
                own[0] = 100.
            seen.append(np.asarray(own).copy())
            return np.asarray(own) - 1.
    solver, _, _ = make_solver(kind)
    solver.adapter.set_mutator(UnitMutation())
    assert solver.step().committed and solver.step().committed
    assert len(seen) == 2
    np.testing.assert_array_equal(seen, [[4.], [4.]])
    np.testing.assert_array_equal(solver.adapter.current_x, [3.])


def test_invalid_selector_row_fails_closed_and_restores_binding_state():
    selector = Selector("invalid")
    solver, _, mutation = make_solver("vns", selector=selector)
    assert solver.step().committed
    with pytest.raises(ValueError, match="within the offered rows"):
        solver.step()
    assert selector.calls == 0 and mutation.calls == 0
    np.testing.assert_array_equal(solver.adapter.current_x, [4.])
    assert solver.adapter.k == 0
    assert solver.problem.calls == [4., 3., 5.]


def test_rejected_gaussian_algorithm_payload_does_not_leave_initializer_restored():
    solver, initializer, _ = make_solver("gaussian")
    assert solver.step().committed
    saved = copy.deepcopy(solver.adapter.get_state())
    initializer.calls = 12
    before = copy.deepcopy(solver.adapter.operator_bindings_state())
    saved["method_id"] = "wrong_algorithm"
    with pytest.raises(ValueError, match="method does not match"):
        solver.adapter.set_state(saved)
    assert initializer.calls == 12
    assert solver.adapter.operator_bindings_state() == before


def test_rejected_vns_unit_payload_does_not_leave_initializer_restored():
    solver, initializer, _ = make_solver("vns", selector=Selector())
    assert solver.step().committed
    saved = copy.deepcopy(solver.adapter.get_state())
    initializer.calls = 12
    before = copy.deepcopy(solver.adapter.operator_bindings_state())
    saved["current_unit"] = {"schema": "wrong_unit"}
    with pytest.raises((TypeError, ValueError, KeyError)):
        solver.adapter.set_state(saved)
    assert initializer.calls == 12
    assert solver.adapter.operator_bindings_state() == before
