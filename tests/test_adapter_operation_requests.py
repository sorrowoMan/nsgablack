"""Behavior evidence for declared operation inputs rather than Solver closures."""
import numpy as np
import pytest

from nsgablack.adapters import NSGA2Adapter, SelectionRequest, FeasibilityFirstSelection
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.representation import RepresentationPipeline, UniformInitializer
from nsgablack.units import UnitInputSpec, UnitFeature


class Problem(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, objectives=["min"], bounds=[(-10., 10.)])
        self.seen = []

    def evaluate(self, candidate):
        self.seen.append(float(candidate[0]))
        return [float(candidate[0]) ** 2]


class PreserveMembers:
    stateless = True
    unit_inputs = UnitInputSpec(fields=("population",))

    def __init__(self):
        self.seen = []

    def checkpoint_identity(self):
        return {"policy": "keep-current-members"}

    def select(self, request, *, rng, unit):
        assert request.purpose == "survivor"
        assert not request.candidates.flags.writeable
        population = unit.fields["population"]
        if population is not None:
            assert not population.flags.writeable
            with pytest.raises(ValueError):
                population.setflags(write=True)
        self.seen.append((len(request.candidates), None if population is None else len(population)))
        return tuple(range(request.count))


def test_selector_reads_actual_owner_unit_without_mutating_members():
    selector = PreserveMembers()
    adapter = NSGA2Adapter(population_size=2, offspring_size=2,
        initializer=UniformInitializer(2., 2.), selector=selector)
    solver = ComposableSolver(Problem(), adapter=adapter, representation_pipeline=RepresentationPipeline())
    solver.set_random_seed(19)
    solver.setup()
    assert solver.step().committed
    before = adapter.get_population_solution_refs(solver)
    assert solver.step().committed
    assert selector.seen == [(2, None), (4, 2)]
    assert adapter.get_population_solution_refs(solver) == before


@pytest.mark.parametrize("feature", [False, True])
def test_feedback_dependent_direct_mutation_bootstraps_before_reading_scores(feature):
    class Mutation:
        stateless = True
        unit_inputs = (UnitInputSpec(features=(UnitFeature("mean-score", ("objectives",),
            lambda values: float(np.mean(values["objectives"])), feedback_view="selection"),)) if feature
            else UnitInputSpec(fields=("objectives",), feedback_view="selection"))

        def __init__(self):
            self.calls = 0

        def checkpoint_identity(self):
            return {"feature": feature}

        def mutate(self, candidate, context, *, unit):
            self.calls += 1
            score = unit.features["mean-score"] if feature else float(np.mean(unit.fields["objectives"]))
            assert score == 4.
            return candidate - 1.

    mutation = Mutation()
    adapter = NSGA2Adapter(population_size=2, offspring_size=2, mutator=mutation)
    solver = ComposableSolver(Problem(), adapter=adapter,
        representation_pipeline=RepresentationPipeline(initializer=UniformInitializer(2., 2.)))
    solver.setup()
    assert solver.step().committed
    assert mutation.calls == 0
    assert solver.problem.seen == [2., 2.]
    assert solver.step().committed
    assert mutation.calls == 2
    assert solver.problem.seen == [2., 2., 1., 1.]


def request(**kwargs):
    return SelectionRequest("candidate", [[1.], [2.], [3.]], [[9.], [1.], [5.]], [0., 3., 0.], 1, **kwargs)


def test_selection_request_detaches_nested_data_and_filters_services():
    weights = np.array([.2, .8])
    source = {"weights": weights, "nested": {"slots": [1, 2]}}
    offered = request(parameters=source, context={"generation": 1, "service": object()})
    weights[:] = 1.
    source["nested"]["slots"].append(9)
    np.testing.assert_array_equal(offered.parameters["weights"], [.2, .8])
    assert offered.parameters["nested"]["slots"] == (1, 2)
    assert dict(offered.context) == {"generation": 1}
    with pytest.raises(ValueError):
        offered.parameters["weights"].setflags(write=True)
    with pytest.raises(TypeError):
        offered.parameters["nested"]["slots"] = ()


@pytest.mark.parametrize("parameters", [{"service": object()}, {1: "not-a-name"}])
def test_selection_request_rejects_non_data_parameters(parameters):
    with pytest.raises(TypeError):
        request(parameters=parameters)


def test_selection_request_rejects_cycles_without_walking_runtime_objects():
    value = {}
    value["cycle"] = value
    with pytest.raises(TypeError, match="cycles"):
        request(parameters=value)


def test_explicit_feasibility_policy_uses_supplied_direction_scores():
    selector = FeasibilityFirstSelection()
    assert selector.select(request(), rng=np.random.default_rng(1)) == (2,)
    assert selector.select(request(scores=[1., -100., 2.]), rng=np.random.default_rng(1)) == (0,)


@pytest.mark.parametrize("kwargs", [{"objective_index": True}, {"objective_index": -1},
                                    {"constraint_tolerance": np.nan}])
def test_invalid_feasibility_policy_configuration_is_rejected(kwargs):
    with pytest.raises(ValueError):
        FeasibilityFirstSelection(**kwargs)
