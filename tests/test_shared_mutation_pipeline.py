"""Heterogeneous consumers share problem stages and select only search operators."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import numpy as np
import pytest

from nsgablack.adapters import (
    CompositeAdapter, NSGA2Adapter, SimulatedAnnealingAdapter, RoleAdapter,
    DifferentialEvolutionAdapter,
)
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.representation import RepresentationPipeline
from nsgablack.units import UnitInputSpec, PopulationUnit, FeatureContractError
from nsgablack.utils.runtime_contracts import inspect_runtime_contracts


class Problem(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, objectives=["minimize"], bounds=[(-100, 100)])
        self.seen = []

    def evaluate(self, x):
        self.seen.append(np.array(x, copy=True))
        return [float(x[0])]


class PopulationMutation:
    unit_inputs = UnitInputSpec(fields=("population",))

    def mutate(self, candidate, context, *, unit):
        return unit.fields["population"].mean(axis=0).copy()


class TrajectoryMutation:
    unit_inputs = UnitInputSpec(fields=("current",))

    def mutate(self, candidate, context, *, unit):
        return unit.fields["current"].copy() - 1


class Shift:
    def __init__(self, delta):
        self.delta = delta

    def mutate(self, candidate, context=None):
        return candidate + self.delta


def population(name, center=2):
    adapter = NSGA2Adapter(name=name, population_size=2, offspring_size=1)
    adapter.set_population_snapshot(np.full((2, 1), center, dtype=float), np.zeros((2, 1)), np.zeros(2))
    return adapter


def mutation_issues(solver):
    return [message for code, message in inspect_runtime_contracts(solver)
            if code == "unit-operator-contract-invalid"]


def test_heterogeneous_nested_adapters_share_repair_and_select_compatible_mutations():
    repaired = []
    mutated = []
    class Repair:
        def repair(self, candidate, context):
            repaired.append(context["role"])
            return candidate + 10
    class TrackedTrajectoryMutation(TrajectoryMutation):
        def mutate(self, candidate, context, *, unit):
            mutated.append((context["role"], unit.fields["current"].copy()))
            return super().mutate(candidate, context, unit=unit)
    left, right = population("population"), SimulatedAnnealingAdapter(name="trajectory")
    right.current_x = np.array([8.])
    left.set_mutation_operator("population")
    right.set_mutation_operator("trajectory")
    pipeline = RepresentationPipeline(repair=Repair(), mutation_operators={
        "population": PopulationMutation(), "trajectory": TrackedTrajectoryMutation(),
    })
    root = CompositeAdapter([RoleAdapter("group", left), RoleAdapter("path", right)])
    problem = Problem()
    solver = ComposableSolver(problem, adapter=root, representation_pipeline=pipeline)
    assert not mutation_issues(solver)
    assert solver.step().committed
    # An unscored trajectory first evaluates its repaired baseline, without mutation.
    np.testing.assert_array_equal(problem.seen, [[12.], [18.]])
    assert repaired == ["group", "path"]
    assert mutated == []
    np.testing.assert_array_equal(right.current_x, [18.])
    assert right.current_score == 18.
    # The next proposal consumes that evaluated Unit, then shares problem repair.
    assert solver.step().committed
    np.testing.assert_array_equal(problem.seen, [[12.], [18.], [12.], [27.]])
    assert repaired == ["group", "path", "group", "path"]
    assert len(mutated) == 1
    assert mutated[0][0] == "path"
    np.testing.assert_array_equal(mutated[0][1], [18.])
    assert pipeline.mutator is None
    assert {value["mutation_operator"] for value in root.get_unit_contracts().values()
            if "mutation_operator" in value} == {"population", "trajectory"}


def test_two_instances_choose_distinct_operators_without_changing_default():
    left, right = population("left"), population("right")
    right.set_mutation_operator("local")
    default = Shift(1)
    pipeline = RepresentationPipeline(mutator=default, mutation_operators={"local": Shift(20)})
    problem = Problem()
    solver = ComposableSolver(problem, adapter=CompositeAdapter([left, right]), representation_pipeline=pipeline)
    assert solver.step().committed
    np.testing.assert_array_equal(problem.seen, [[3.], [22.]])
    assert pipeline.mutator is default


@pytest.mark.parametrize("name,pattern", [("typo", "unknown mutation"),
                                        (None, "selected no default"),
                                        ("trajectory", "current")])
def test_bad_binding_is_reported_and_never_falls_back(name, pattern):
    adapter = population("group")
    adapter.set_mutation_operator(name)
    pipeline = RepresentationPipeline(mutation_operators={"trajectory": TrajectoryMutation()})
    problem = Problem()
    solver = ComposableSolver(problem, adapter=adapter, representation_pipeline=pipeline)
    assert any(pattern in issue for issue in mutation_issues(solver))
    with pytest.raises((ValueError, FeatureContractError)):
        solver.step()
    assert not problem.seen
    np.testing.assert_array_equal(adapter.population, [[2.], [2.]])


def test_named_scalar_and_batch_unit_inputs_have_same_contract():
    mutator = PopulationMutation()
    pipeline = RepresentationPipeline(mutation_operators={"population": mutator})
    inputs = [mutator.unit_inputs.capture(PopulationUnit("same", np.full((2, 1), center)))
              for center in (3., 7.)]
    np.testing.assert_array_equal(pipeline.mutate_batch(np.zeros((2, 1)), operator="population", units=inputs),
                                  [[3.], [7.]])
    with pytest.raises(FeatureContractError, match="UnitInputs"):
        pipeline.mutate(np.zeros(1), operator="population")
    with pytest.raises(ValueError, match="unknown mutation"):
        pipeline.mutate_batch(np.zeros((0, 1)), operator="typo")


def test_named_ordinary_batch_uses_selected_component_and_row_contexts():
    class Batch(Shift):
        def mutate_batch(self, states, contexts):
            return [state + ctx["offset"] for state, ctx in zip(states, contexts)]
    pipeline = RepresentationPipeline(mutator=Shift(100), mutation_operators={"batch": Batch(1)})
    np.testing.assert_array_equal(pipeline.mutate_batch(np.zeros((2, 1)), [{"offset": 2}, {"offset": 4}],
                                                       operator="batch"), [[2.], [4.]])


def test_named_operator_errors_do_not_retry_another_operator():
    calls = []
    class Failing(PopulationMutation):
        def mutate(self, candidate, context, *, unit):
            calls.append("fail")
            raise TypeError("named callback failed")
    pipeline = RepresentationPipeline(mutator=Shift(100), mutation_operators={"fail": Failing()}, transactional=True)
    inputs = PopulationMutation.unit_inputs.capture(PopulationUnit("p", np.zeros((2, 1))))
    with pytest.raises(TypeError, match="named callback failed"):
        pipeline.mutate(np.zeros(1), operator="fail", unit=inputs)
    assert calls == ["fail"]


def test_overlapping_calls_cannot_swap_each_others_operator():
    barrier = Barrier(2)
    class Concurrent(Shift):
        def mutate(self, candidate, context):
            barrier.wait(timeout=5)
            return super().mutate(candidate, context)
    pipeline = RepresentationPipeline(mutation_operators={"left": Concurrent(1), "right": Concurrent(9)})
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(pipeline.mutate, np.zeros(1), operator=name) for name in ("left", "right")]
        np.testing.assert_array_equal([job.result() for job in jobs], [[1.], [9.]])


def test_named_rng_seed_is_repeatable_and_context_contracts_are_visible():
    class RandomMutation:
        context_requires = ("temperature",)
        def set_random_seed(self, seed):
            self.rng = np.random.default_rng(seed)
        def mutate(self, candidate, context):
            return self.rng.random(candidate.shape)
    def build(names):
        return RepresentationPipeline(mutation_operators={name: RandomMutation() for name in names}, random_seed=32)
    left, right = build(("a", "b")), build(("b", "a"))
    for name in ("a", "b"):
        np.testing.assert_array_equal(left.mutate(np.zeros(8), operator=name), right.mutate(np.zeros(8), operator=name))
    assert "temperature" in left.get_context_contract()["requires"]
    assert left.describe()["mutation_operators"] == {"a": "RandomMutation", "b": "RandomMutation"}


def test_registry_is_detached_and_binding_requires_a_consuming_adapter():
    mapping = {"local": Shift(1)}
    pipeline = RepresentationPipeline(mutation_operators=mapping)
    mapping.clear()
    assert pipeline.get_mutator("local").delta == 1
    with pytest.raises(TypeError):
        pipeline.mutation_operators["local"] = Shift(2)
    with pytest.raises(ValueError, match="does not consume"):
        DifferentialEvolutionAdapter().set_mutation_operator("local")
    with pytest.raises(ValueError, match="nonempty"):
        population("p").set_mutation_operator("")
