"""Feature maintenance is checked against reconstruction, not cache internals."""
import json
from dataclasses import dataclass

import numpy as np
import pytest

from nsgablack.adapters import NSGA2Adapter
from nsgablack.units import (
    PopulationUnit, PopulationView, UnitBinding, UnitFeature, FeatureContractError,
    POPULATION_DISTANCES, SELECTION_RANKING,
)
from nsgablack.representation import PopulationUnitBuilder
from nsgablack.bias import PopulationDiversityPreference, PreferenceQuery


def full_distances(x):
    return np.linalg.norm(x[:, None, :] - x[None, :, :], axis=2)


@pytest.mark.parametrize("change", ["row", "rows", "reorder", "append", "shrink", "empty"])
def test_distance_maintenance_matches_reconstruction(change):
    unit = PopulationUnit("p", np.array([[0., 1.], [2., 3.], [2., 3.], [9., 1.]]))
    original = unit.pairwise_distances()
    assert unit.pairwise_distances() is original
    if change == "row":
        unit.population[1] = [4, 5]
    elif change == "rows":
        unit.population[[0, 3]] = [[-1, 0], [1, 8]]
    elif change == "reorder":
        unit.population = unit.population[[3, 1, 2, 0]]
    elif change == "append":
        unit.population = np.vstack([unit.population, [4, 5]])
    elif change == "shrink":
        unit.population = unit.population[:2]
    else:
        unit.population = np.empty((0, 2))
    maintained = unit.pairwise_distances()
    np.testing.assert_allclose(maintained, full_distances(unit.population))
    np.testing.assert_allclose(maintained, unit.pairwise_distances(cache=False))
    np.testing.assert_array_equal(original, full_distances(np.array([[0., 1.], [2., 3.], [2., 3.], [9., 1.]])))
    with pytest.raises(ValueError):
        maintained.setflags(write=True)


def test_feature_scope_and_duplicate_value_identity_remain_separate():
    first = PopulationUnit("same-id", np.array([[0.], [5.]]), candidate_tokens=("a", "b"))
    second = PopulationUnit("same-id", np.array([[0.], [9.]]), candidate_tokens=("a", "b"))
    assert first.pairwise_distances()[0, 1] == 5
    assert second.pairwise_distances()[0, 1] == 9
    binding = UnitBinding(PopulationUnitBuilder())
    a = PopulationView.capture(first, binding, owner_path=("first",))
    b = PopulationView.capture(second, binding, owner_path=("second",))
    pref = PopulationDiversityPreference()
    assert pref.evaluate(PreferenceQuery("candidate_in_unit", candidate=[0], candidate_token="new", unit=a)).value == 0
    assert pref.evaluate(PreferenceQuery("candidate_in_unit", candidate=[0], candidate_token="a", unit=a)).value == 5
    assert pref.evaluate(PreferenceQuery("candidate_in_unit", candidate=[0], candidate_token="a", unit=b)).value == 9
    first.population[1] = [100]
    assert a.pairwise_distances()[0, 1] == 5  # A captured view intentionally stays at its revision.
    assert first.pairwise_distances()[0, 1] == 100


def test_optional_cache_and_failure_never_publish_wrong_revision():
    calls = []
    def compute(inputs):
        calls.append(1)
        if inputs["population"][0, 0] < 0:
            raise ValueError("bad geometry")
        return np.sum(inputs["population"])
    feature = UnitFeature("sum", ("population",), compute)
    unit = PopulationUnit("p", np.array([[2.]]))
    assert unit.feature(feature) == unit.feature(feature) == 2
    assert len(calls) == 1
    assert unit.feature(feature, cache=False) == 2
    assert len(calls) == 2
    unit.population[0, 0] = -1
    with pytest.raises(ValueError, match="bad geometry"):
        unit.feature(feature)
    unit.population[0, 0] = 3
    assert unit.feature(feature) == 3
    unit.clear_features()
    assert unit.feature(feature) == 3
    assert len(calls) == 5


def test_feedback_view_and_missing_evaluation_are_explicit():
    unit = PopulationUnit("p", np.array([[0.], [1.]]))
    with pytest.raises(FeatureContractError, match="evaluated"):
        unit.feature(SELECTION_RANKING)
    unit.objectives, unit.violations = np.array([[1.], [2.]]), np.zeros(2)
    with pytest.raises(FeatureContractError, match="feedback view"):
        unit.feature(UnitFeature("ambiguous", ("objectives",), lambda v: v["objectives"]))
    with pytest.raises(FeatureContractError, match="feedback view"):
        unit.feature(UnitFeature("raw", ("objectives",), lambda v: v["objectives"], feedback_view="raw"))
    rank, _ = unit.feature(SELECTION_RANKING)
    unit.objectives[:] = [[3.], [0.]]  # Selection-view change in the same generation.
    new_rank, _ = unit.feature(SELECTION_RANKING)
    assert rank[0] < rank[1] and new_rank[0] > new_rank[1]


def test_custom_raw_feature_does_not_depend_on_selection_view():
    @dataclass
    class RawPopulation(PopulationUnit):
        raw_objectives: object = None
        feature_feedback_fields = {**PopulationUnit.feature_feedback_fields, "raw_objectives": "raw"}
    unit = RawPopulation("p", np.array([[0.]]), np.array([[2.]]), np.zeros(1), raw_objectives=np.array([[8.]]))
    raw = UnitFeature("raw-values", ("raw_objectives",), lambda v: v["raw_objectives"], feedback_view="raw")
    original = unit.feature(raw)
    unit.objectives[:] = 100
    assert unit.feature(raw) is original
    assert original[0, 0] == 8


def test_candidate_change_invalidates_feedback_features_until_feedback_is_attached():
    unit = PopulationUnit("p", np.array([[0.], [1.]]), np.array([[0.], [1.]]), np.zeros(2))
    unit.feature(SELECTION_RANKING)
    unit.population[0] = 10
    with pytest.raises(FeatureContractError, match="reevaluate"):
        unit.feature(SELECTION_RANKING)
    binding = UnitBinding(PopulationUnitBuilder())
    restored = binding.restore(json.loads(json.dumps(binding.dump(unit))))
    with pytest.raises(FeatureContractError, match="reevaluate"):
        restored.feature(SELECTION_RANKING)
    assert unit.pairwise_distances()[0, 1] == 9
    unit.objectives, unit.violations = np.array([[10.], [1.]]), np.zeros(2)
    assert unit.feature(SELECTION_RANKING)[0][0] > unit.feature(SELECTION_RANKING)[0][1]


def test_callbacks_cannot_edit_input_or_reenter_feature_computation():
    unit = PopulationUnit("p", np.array([[0.]]))
    def mutate(inputs):
        inputs["population"][0] = 4
    with pytest.raises(ValueError, match="read-only"):
        unit.feature(UnitFeature("mutate", ("population",), mutate))
    nested = UnitFeature("nested", ("population",), lambda _: unit.pairwise_distances())
    with pytest.raises(FeatureContractError, match="nested"):
        unit.feature(nested)
    def external_change(inputs):
        unit.population[0] = 5
        return 0
    with pytest.raises(FeatureContractError, match="changed during"):
        unit.feature(UnitFeature("external", ("population",), external_change))
    assert unit.pairwise_distances()[0, 0] == 0


def test_codec_omits_features_but_preserves_declared_algorithm_state():
    @dataclass
    class StatefulPopulation(PopulationUnit):
        historical_best: float = 42
    class Builder(PopulationUnitBuilder):
        unit_type = StatefulPopulation
    unit = StatefulPopulation("p", np.array([[1.], [4.]]))
    binding = UnitBinding(Builder())
    before = binding.dump(unit)
    unit.pairwise_distances()
    assert binding.dump(unit) == before
    restored = binding.restore(json.loads(json.dumps(before)))
    assert restored.historical_best == 42
    restored.population[1] = 9
    assert restored.pairwise_distances()[0, 1] == 8
    assert unit.pairwise_distances()[0, 1] == 3


def test_nsga_ranking_consumes_declared_feature_and_rolls_back():
    adapter = NSGA2Adapter(population_size=2, offspring_size=1)
    adapter.set_population_snapshot(np.array([[0.], [1.]]), np.array([[0.], [1.]]), np.zeros(2))
    rank = adapter.algorithm_unit.feature(SELECTION_RANKING)[0]
    adapter._refresh_ranking()
    assert adapter._rank is rank
    transaction = adapter.begin_step_transaction()
    adapter.objectives[:] = [[5.], [0.]]
    adapter._refresh_ranking()
    assert adapter._rank[0] > adapter._rank[1]
    transaction.rollback()
    assert adapter._rank[0] < adapter._rank[1]


def test_proposal_operators_get_detached_parents():
    from types import SimpleNamespace
    adapter = NSGA2Adapter(population_size=2, offspring_size=1)
    adapter.set_population_snapshot(np.array([[0.], [1.]]), np.array([[0.], [1.]]), np.zeros(2))
    before = adapter.algorithm_unit.pairwise_distances()
    def crossover(control, first, second, context):
        first[:] = 7
        return first
    def mutate(x, context):
        x[:] = 9
        return x
    adapter._crossover = crossover
    proposal = adapter.propose(SimpleNamespace(mutate_candidate=mutate, repair_candidate=lambda x, c: x), {})
    assert proposal[0][0] == 9
    np.testing.assert_array_equal(adapter.population, [[0.], [1.]])
    assert adapter.algorithm_unit.pairwise_distances() is before


def test_repaired_rejected_proposal_keeps_current_unit_and_features():
    from nsgablack.core import ComposableSolver, BlackBoxProblem, FeasibleEvaluationAcceptance
    from nsgablack.representation import RepresentationPipeline
    class Problem(BlackBoxProblem):
        def __init__(self):
            super().__init__(dimension=1, objectives=["minimize"], bounds=[(-10, 10)])
        def evaluate(self, x):
            assert x[0] == 2  # Candidate passed through repair before evaluation.
            return [float(x[0])]
        def evaluate_constraints(self, x):
            return max(0., float(x[0]))
    class Mutation:
        def mutate(self, x, context=None):
            x[:] = 9
            return x
    class Repair:
        def repair(self, x, context=None):
            return np.clip(x, -2, 2)
    adapter = NSGA2Adapter(population_size=2, offspring_size=1)
    solver = ComposableSolver(Problem(), adapter=adapter,
        representation_pipeline=RepresentationPipeline(mutator=Mutation(), repair=Repair()),
        evaluation_acceptance_policy=FeasibleEvaluationAcceptance())
    adapter.set_population_snapshot(np.array([[-1.], [0.]]), np.array([[-1.], [0.]]), np.zeros(2))
    before = adapter.algorithm_unit.pairwise_distances().copy()
    outcome = solver.step()
    assert outcome.status == "rejected" and outcome.evaluations == 1
    np.testing.assert_array_equal(adapter.population, [[-1.], [0.]])
    np.testing.assert_array_equal(adapter.algorithm_unit.pairwise_distances(), before)


def test_doctor_validates_declarations_without_computing_features():
    from nsgablack.core import ComposableSolver, BlackBoxProblem
    from nsgablack.utils.runtime_contracts import inspect_runtime_contracts
    class Problem(BlackBoxProblem):
        def __init__(self):
            super().__init__(dimension=1, objectives=["minimize"], bounds=[(-5, 5)])
        def evaluate(self, x):
            return [float(x[0])]
    adapter = NSGA2Adapter()
    solver = ComposableSolver(Problem(), adapter=adapter)
    adapter.unit_features = (UnitFeature("missing", ("nonexistent",), lambda _: pytest.fail("computed")),)
    assert "unit-feature-contract-invalid" in {code for code, _ in inspect_runtime_contracts(solver)}
