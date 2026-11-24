"""Operators consume declared Unit data; repair has one proposal-stage owner."""
from types import SimpleNamespace

import numpy as np
import pytest

from nsgablack.adapters import (
    AlgorithmAdapter, NSGA2Adapter, CompositeAdapter, RoleAdapter,
    DifferentialEvolutionAdapter, SimulatedAnnealingAdapter, VNSAdapter,
    SingleTrajectoryAdaptiveAdapter, PatternSearchAdapter, GradientDescentAdapter,
    GradientOptimizerAdapter, MOEADAdapter,
)
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.representation import RepresentationPipeline
from nsgablack.units import (
    UnitInputSpec, UnitFeature, PopulationUnit, POPULATION_DISTANCES, FeatureContractError,
)


class Problem(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, objectives=["minimize"], bounds=[(-100, 100)])
        self.seen = []
    def evaluate(self, x):
        self.seen.append(np.asarray(x).copy())
        return [float(x[0])]


class SetOne:
    def mutate(self, x, context=None):
        x[:] = 1
        return x


class ShiftRepair:
    def __init__(self):
        self.calls = 0
    def repair(self, x, context=None):
        self.calls += 1
        x[:] += 4
        return x


def nsga(name="nsga", center=0., offspring=1):
    adapter = NSGA2Adapter(name=name, population_size=2, offspring_size=offspring)
    adapter.set_population_snapshot(np.full((2, 1), center), np.zeros((2, 1)), np.zeros(2))
    return adapter


@pytest.mark.parametrize("batch", [False, True])
def test_mutation_never_implicitly_repairs(batch):
    class BatchMutator(SetOne):
        def mutate_batch(self, states, contexts):
            return [self.mutate(np.array(x, copy=True)) for x in states]
    repair = ShiftRepair()
    pipeline = RepresentationPipeline(mutator=BatchMutator(), repair=repair)
    output = pipeline.mutate_batch(np.zeros((2, 1))) if batch else pipeline.mutate(np.zeros(1))
    assert repair.calls == 0
    np.testing.assert_array_equal(output, np.ones((2, 1)) if batch else [1.])


@pytest.mark.parametrize("allowance", [0, 1, 3])
def test_nonidempotent_repair_runs_once_for_each_budget_approved_proposal(allowance):
    repair, problem = ShiftRepair(), Problem()
    adapter = nsga(offspring=3)
    seen = []
    adapter.on_proposal_repair = lambda control, evidence, ctx: seen.append(evidence)
    solver = ComposableSolver(problem, adapter=adapter,
                              representation_pipeline=RepresentationPipeline(mutator=SetOne(), repair=repair))
    solver.evaluation_batch_allowance = lambda count, context: allowance
    outcome = solver.step()
    assert repair.calls == allowance and len(problem.seen) == allowance
    if allowance:
        assert outcome.committed
        np.testing.assert_array_equal(problem.seen, np.full((allowance, 1), 5.))
        np.testing.assert_array_equal(seen[0].before.numeric_matrix, np.ones((allowance, 1)))
        np.testing.assert_array_equal(seen[0].after.numeric_matrix, np.full((allowance, 1), 5.))
    else:
        assert outcome.status == "rejected" and not seen


@pytest.mark.parametrize("factory", [
    lambda: nsga(), lambda: DifferentialEvolutionAdapter(population_size=4, batch_size=1),
    lambda: SimulatedAnnealingAdapter(batch_size=1), lambda: VNSAdapter(batch_size=1),
    lambda: SingleTrajectoryAdaptiveAdapter(batch_size=1), lambda: PatternSearchAdapter(max_directions=1),
    lambda: GradientDescentAdapter(max_directions=1), lambda: GradientOptimizerAdapter(),
])
def test_builtin_propose_returns_drafts_without_executing_repair(factory):
    control = SimpleNamespace(init_candidate=lambda ctx: np.zeros(1),
                              init_population=lambda count, ctx: tuple(np.zeros(1) for _ in range(count)),
                              mutate_candidate=lambda x, ctx: np.asarray(x) + 1,
                              repair_candidate=lambda *args: pytest.fail("proposal repaired early"))
    assert len(factory().propose(control, {})) > 0


def test_moead_proposal_repair_contexts_keep_subproblem_identity():
    adapter = MOEADAdapter(population_size=4, batch_size=2, variation="pipeline")
    adapter.set_population_snapshot(np.zeros((4, 1)), np.zeros((4, 1)), np.zeros(4))
    adapter.weights, adapter.neighbors = np.ones((4, 1)), np.tile(np.arange(4), (4, 1))
    control = SimpleNamespace(mutate_candidate=lambda x, ctx: x + 1,
                              repair_candidate=lambda *args: pytest.fail("proposal repaired early"))
    proposals = adapter.propose(control, {})
    rows = adapter.get_proposal_contexts(len(proposals), {})
    assert [row["moead_subproblem"] for row in rows] == adapter._pending_indices


def test_repair_failure_propagates_even_for_transactional_pipeline():
    class FailingRepair:
        def repair(self, x, context=None):
            raise RuntimeError("failed repair")
    problem, adapter = Problem(), nsga()
    solver = ComposableSolver(problem, adapter=adapter, representation_pipeline=RepresentationPipeline(
        mutator=SetOne(), repair=FailingRepair(), transactional=True))
    with pytest.raises(RuntimeError, match="failed repair"):
        solver.step()
    assert not problem.seen
    np.testing.assert_array_equal(adapter.population, np.zeros((2, 1)))


@pytest.mark.parametrize("batch", [False, True])
def test_nested_roles_preserve_per_row_repair_context_after_local_and_global_clipping(batch):
    class Probe(AlgorithmAdapter):
        def propose(self, control, context):
            return [np.array([i], dtype=float) for i in range(3)]
        def update(self, *args):
            pass
    calls = []
    class Repair:
        def repair(self, x, context=None):
            calls.append(context["role"])
            return x + (10 if context["role"] == "left" else 20)
    class BatchRepair(Repair):
        def repair_batch(self, states, contexts):
            return [self.repair(x, ctx) for x, ctx in zip(states, contexts)]
    adapter = CompositeAdapter([RoleAdapter("left", Probe("a"), max_candidates=2),
                                RoleAdapter("right", Probe("b"))])
    problem = Problem()
    solver = ComposableSolver(problem, adapter=adapter,
        representation_pipeline=RepresentationPipeline(repair=(BatchRepair() if batch else Repair())))
    solver.evaluation_batch_allowance = lambda count, context: 3
    assert solver.step().committed
    assert calls == ["left", "left", "right"]
    np.testing.assert_array_equal(problem.seen, [[10.], [11.], [20.]])


class PopulationMutation:
    unit_inputs = UnitInputSpec(fields=("population",), features=(POPULATION_DISTANCES,))
    def __init__(self):
        self.seen = []
    def mutate(self, x, context, *, unit):
        assert set(unit.fields) == {"population"}
        with pytest.raises(ValueError, match="read-only"):
            unit.fields["population"][0, 0] = 999
        self.seen.append(unit)
        return np.full_like(x, unit.fields["population"].mean())


def test_same_unit_id_in_two_adapters_does_not_mix_operator_inputs():
    left, right = nsga("left", 1), nsga("right", 9)
    left.algorithm_unit.unit_id = right.algorithm_unit.unit_id = "same-id"
    mutator, problem = PopulationMutation(), Problem()
    solver = ComposableSolver(problem, adapter=CompositeAdapter([left, right]),
        representation_pipeline=RepresentationPipeline(mutator=mutator))
    assert solver.step().committed
    np.testing.assert_array_equal(problem.seen, [[1.], [9.]])
    assert mutator.seen[0].unit_id == mutator.seen[1].unit_id
    assert mutator.seen[0].revision != mutator.seen[1].revision
    left.population[0] = 100
    assert mutator.seen[0].fields["population"][0, 0] == 1


def test_unit_batch_inputs_are_explicit_aligned_and_readonly():
    mutator = PopulationMutation()
    pipeline = RepresentationPipeline(mutator=mutator)
    units = [PopulationUnit("p", np.full((2, 1), mean)) for mean in (2., 8.)]
    inputs = [mutator.unit_inputs.capture(u) for u in units]
    with pytest.raises(ValueError, match="align"):
        pipeline.mutate_batch(np.zeros((2, 1)), units=inputs[:1])
    assert not mutator.seen
    np.testing.assert_array_equal(pipeline.mutate_batch(np.zeros((2, 1)), units=inputs), [[2.], [8.]])
    with pytest.raises(FeatureContractError, match="UnitInputs"):
        pipeline.mutate(np.zeros(1))


def test_feedback_dependency_capture_rejects_stale_feedback():
    spec = UnitInputSpec(fields=("objectives",), feedback_view="selection")
    unit = PopulationUnit("p", np.zeros((2, 1)), np.zeros((2, 1)), np.zeros(2))
    unit.population[0] = 10
    with pytest.raises(FeatureContractError, match="reevaluate"):
        spec.capture(unit)
    with pytest.raises(FeatureContractError, match="feedback view"):
        UnitInputSpec(fields=("objectives",)).capture(unit)


def test_doctor_validates_unit_inputs_without_computing_features():
    from nsgablack.utils.runtime_contracts import inspect_runtime_contracts
    feature = UnitFeature("probe", ("population",), lambda _: pytest.fail("Doctor executed feature"))
    mutator = PopulationMutation()
    mutator.unit_inputs = UnitInputSpec(features=(feature,))
    pipeline = RepresentationPipeline(mutator=mutator)
    solver = ComposableSolver(Problem(), adapter=nsga(), representation_pipeline=pipeline)
    assert not any(code == "unit-operator-contract-invalid" for code, _ in inspect_runtime_contracts(solver))
    mutator.unit_inputs = UnitInputSpec(fields=("missing",))
    assert any(code == "unit-operator-contract-invalid" for code, _ in inspect_runtime_contracts(solver))


def test_unit_mutator_typeerror_is_not_retried_without_dependencies():
    class Failing(PopulationMutation):
        def mutate(self, x, context, *, unit):
            self.seen.append(unit)
            raise TypeError("callback failed")
    mutator = Failing()
    pipeline = RepresentationPipeline(mutator=mutator, transactional=True)
    inputs = mutator.unit_inputs.capture(PopulationUnit("p", np.zeros((2, 1))))
    with pytest.raises(TypeError, match="callback failed"):
        pipeline.mutate(np.zeros(1), unit=inputs)
    assert len(mutator.seen) == 1


def test_finite_difference_repair_geometry_is_validated_before_evaluation():
    class TwoDimensional(Problem):
        def __init__(self):
            BlackBoxProblem.__init__(self, dimension=2, objectives=["minimize"], bounds=[(-100, 100)] * 2)
            self.seen = []
    adapter, problem = GradientDescentAdapter(max_directions=1), TwoDimensional()
    adapter.current_x = np.zeros(2)
    solver = ComposableSolver(problem, adapter=adapter,
                              representation_pipeline=RepresentationPipeline(repair=ShiftRepair()))
    assert solver.step().committed  # Repair establishes the evaluated center first.
    before, evaluated = adapter.current_x.copy(), len(problem.seen)
    with pytest.raises(ValueError, match="coordinate geometry"):
        solver.step()
    assert len(problem.seen) == evaluated  # Coupled probe repair fails before evaluation.
    np.testing.assert_array_equal(adapter.current_x, before)


def test_vns_reconciles_pending_unit_identity_before_evaluation():
    from blackbase.types import UnknownState
    adapter, problem, repair = VNSAdapter(batch_size=1), Problem(), ShiftRepair()
    adapter.current_x = UnknownState([0.], {"meaning": "kept"})
    original = adapter.on_proposal_repair
    reconciled = []
    def check(control, evidence, context):
        old_id = adapter._pending_units[0].unit_id
        original(control, evidence, context)
        unit = adapter._pending_units[0]
        assert unit.unit_id == old_id
        assert unit.to_candidate().metadata["meaning"] == "kept"
        # The unevaluated seed is the first proposal; mutation starts after its
        # baseline has been admitted. Repair shifts that seed from 0 to 4.
        np.testing.assert_array_equal(unit.to_candidate().values, [4.])
        reconciled.append(unit.unit_id)
        assert not problem.seen
    adapter.on_proposal_repair = check
    solver = ComposableSolver(problem, adapter=adapter,
        representation_pipeline=RepresentationPipeline(mutator=SetOne(), repair=repair))
    assert solver.step().committed
    assert repair.calls == 1 and len(reconciled) == 1


@pytest.mark.parametrize("explicit_metadata", [False, True])
def test_numeric_repair_preserves_each_rows_metadata_unless_explicitly_replaced(explicit_metadata):
    from blackbase.types import UnknownState
    seen = []
    class Proposer(AlgorithmAdapter):
        def propose(self, control, context):
            return [UnknownState([1.], {"tag": tag}) for tag in ("a", "b")]
        def on_proposal_repair(self, control, evidence, context):
            seen.append(evidence)
        def update(self, *args):
            pass
    class Repair:
        def repair(self, x, context=None):
            values = np.asarray(x) + 1
            return UnknownState(values, {"explicit": True}) if explicit_metadata else values
    solver = ComposableSolver(Problem(), adapter=Proposer("semantic"),
                              representation_pipeline=RepresentationPipeline(repair=Repair()))
    assert solver.step().committed
    expected = [{"explicit": True}] * 2 if explicit_metadata else [{"tag": "a"}, {"tag": "b"}]
    assert [dict(state.metadata) for state in seen[0].after.semantic_states] == expected
    assert seen[0].before.candidate_tokens == seen[0].after.candidate_tokens
    assert len(set(seen[0].after.candidate_tokens)) == 2
