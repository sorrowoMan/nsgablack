"""Candidate, feedback and identity stay aligned across population operations."""
import json
from types import SimpleNamespace

import numpy as np
import pytest

from nsgablack.adapters import (
    DifferentialEvolutionAdapter, MOEADAdapter, NSGA2Adapter, NSGA3Adapter, SPEA2Adapter,
)
from nsgablack.representation import PopulationUnitBuilder
from nsgablack.units import PopulationUnit, UnitBinding, FeatureContractError, SELECTION_RANKING


def population():
    return PopulationUnit("p", np.array([[0.], [1.]]), np.array([[0.], [1.]]),
                          np.zeros(2), ("a", "b"))


@pytest.mark.parametrize("first", ["objectives", "violations"])
@pytest.mark.parametrize("restore", [False, True])
def test_partial_feedback_attachment_cannot_certify_the_other_field(first, restore):
    unit = population()
    unit.population[0] = 10
    setattr(unit, first, np.array([[10.], [1.]]) if first == "objectives" else np.zeros(2))
    binding = UnitBinding(PopulationUnitBuilder())
    if restore:
        unit = binding.restore(json.loads(json.dumps(binding.dump(unit))))
    with pytest.raises(FeatureContractError, match="reevaluate"):
        unit.feature(SELECTION_RANKING)
    second = "violations" if first == "objectives" else "objectives"
    setattr(unit, second, np.zeros(2) if second == "violations" else np.array([[10.], [1.]]))
    assert unit.feature(SELECTION_RANKING)[0].tolist() == [1, 0]


def test_feedback_attached_across_two_candidate_revisions_is_still_stale():
    unit = population()
    unit.population[0] = 10
    unit.objectives = np.array([[10.], [1.]])
    unit.population[0] = 20
    unit.violations = np.zeros(2)
    with pytest.raises(FeatureContractError, match="reevaluate"):
        unit.require_current_feedback()
    unit.attach_feedback(np.array([[20.], [1.]]), np.zeros(2))
    unit.require_current_feedback()


def test_attach_feedback_validates_both_arrays_before_publishing_either():
    unit = population()
    old = unit.feature(SELECTION_RANKING)
    with pytest.raises(ValueError, match="align"):
        unit.attach_feedback([[9.], [8.]], [0.])
    np.testing.assert_array_equal(unit.objectives, [[0.], [1.]])
    assert unit.feature(SELECTION_RANKING) is old
    feedback = np.array([[9.], [8.]])
    unit.attach_feedback(feedback, np.zeros(2))
    feedback[:] = 100
    np.testing.assert_array_equal(unit.objectives, [[9.], [8.]])


@pytest.mark.parametrize("kwargs", [
    {"indices": [-1]}, {"indices": [2]}, {"indices": [0.5]},
    {"population": [[2., 3.]]}, {"objectives": [[2., 3.]]},
    {"violations": []}, {"candidate_tokens": ()}, {"candidate_tokens": (object(),)},
    {"population": [["not-a-number"]]},
])
def test_invalid_row_replacement_leaves_all_fields_and_cached_results_intact(kwargs):
    unit = population()
    binding = UnitBinding(PopulationUnitBuilder())
    before = binding.dump(unit)
    cached = unit.pairwise_distances()
    args = dict(indices=[0], population=[[2.]], objectives=[[2.]], violations=[0.], candidate_tokens=("c",))
    args.update(kwargs)
    with pytest.raises((TypeError, ValueError)):
        unit.replace_evaluated_rows(**args)
    assert binding.dump(unit) == before
    assert unit.pairwise_distances() is cached


def test_row_replacement_preserves_order_tokens_and_detaches_caller_arrays():
    unit = population()
    old = unit.pairwise_distances()
    candidates = np.array([[9.], [3.]])
    unit.replace_evaluated_rows([0, 0], candidates, candidates ** 2, [0., 0.], candidate_tokens=("c", "d"))
    candidates[:] = 100
    np.testing.assert_array_equal(unit.population, [[3.], [1.]])
    np.testing.assert_array_equal(unit.objectives, [[9.], [1.]])
    assert unit.candidate_tokens == ("d", "b")
    assert old[0, 1] == 1 and unit.pairwise_distances()[0, 1] == 2
    assert unit.feature(SELECTION_RANKING)[0].tolist() == [1, 0]
    # Numeric equality does not mean equal identity.
    unit.replace_evaluated_rows([1], [[1.]], [[1.]], [0.], candidate_tokens=("other-one",))
    assert unit.candidate_tokens == ("d", "other-one")


def test_row_replacement_cannot_recertify_preexisting_stale_rows():
    unit = population()
    unit.population[1] = 99
    with pytest.raises(FeatureContractError, match="reevaluate"):
        unit.replace_evaluated_rows([0], [[3.]], [[9.]], [0.], candidate_tokens=("c",))
    assert unit.population[0, 0] == 0


def test_legacy_shared_revision_survives_restore_without_new_field_stamps():
    unit = population()
    unit.population[0] = 99
    binding = UnitBinding(PopulationUnitBuilder())
    saved = binding.dump(unit)
    del saved["payload"]["feedback_field_revisions"]
    restored = binding.restore(json.loads(json.dumps(saved)))
    with pytest.raises(FeatureContractError, match="reevaluate"):
        restored.require_current_feedback()


def test_de_duplicate_targets_keep_proposal_time_baselines_and_rollback():
    adapter = DifferentialEvolutionAdapter(population_size=2, batch_size=2)
    adapter.set_population_snapshot(np.array([[10.], [20.]]), np.array([[10.], [20.]]), np.zeros(2))
    adapter.set_population_candidate_tokens(("old-a", "old-b"))
    adapter._last_target_indices, adapter._last_target_scores = [0, 0], np.array([10., 10.])
    adapter.candidate_tokens_for = lambda control, candidates: ("first", "second")
    transaction = adapter.begin_step_transaction()
    adapter.update(SimpleNamespace(), [[1.], [2.]], (np.array([[1.], [2.]]), np.zeros(2)), {})
    # Both beat their captured baseline; the second accepted proposal wins.
    np.testing.assert_array_equal(adapter.population, [[2.], [20.]])
    assert adapter.get_population_candidate_tokens() == ("second", "old-b")
    adapter.algorithm_unit.feature(SELECTION_RANKING)
    transaction.rollback()
    np.testing.assert_array_equal(adapter.population, [[10.], [20.]])
    assert adapter.get_population_candidate_tokens() == ("old-a", "old-b")
    adapter.algorithm_unit.feature(SELECTION_RANKING)


def moead():
    adapter = MOEADAdapter(population_size=4, batch_size=1, neighborhood_size=4,
                          nr=2, variation="pipeline", decomposition="weighted_sum")
    adapter.set_population_snapshot(np.arange(10., 50., 10.).reshape(-1, 1),
                                    np.arange(10., 50., 10.).reshape(-1, 1), np.zeros(4))
    adapter.set_population_candidate_tokens(("a", "b", "c", "d"))
    adapter.weights = np.ones((4, 1))
    adapter.neighbors = np.tile(np.arange(4), (4, 1))
    adapter.ideal = np.array([0.])  # Historical best need not be in today's population.
    adapter._rng = np.random.default_rng(12)
    return adapter


def test_moead_replacement_keeps_geometry_history_and_feedback_aligned():
    adapter = moead()
    neighbors = adapter.neighbors.copy()
    adapter.neighbors.setflags(write=False)
    adapter._pending_indices, adapter._pending_modes = [0], ["neighborhood"]
    adapter.candidate_tokens_for = lambda control, candidates: ("new",)
    transaction = adapter.begin_step_transaction()
    adapter.update(SimpleNamespace(), [[1.]], (np.array([[1.]]), np.zeros(1)), {})
    changed = np.flatnonzero(adapter.pop_X[:, 0] == 1)
    assert len(changed) == 2
    for index in changed:
        assert adapter.pop_F[index, 0] == 1 and adapter.get_population_candidate_tokens()[index] == "new"
    np.testing.assert_array_equal(adapter.neighbors, neighbors)
    np.testing.assert_array_equal(adapter.ideal, [0.])
    adapter.algorithm_unit.feature(SELECTION_RANKING)
    transaction.rollback()
    np.testing.assert_array_equal(adapter.pop_X[:, 0], [10., 20., 30., 40.])
    adapter.algorithm_unit.feature(SELECTION_RANKING)


def test_moead_proposal_mutation_and_repair_do_not_edit_parent_unit():
    adapter = moead()
    def mutate(x, context):
        x[:] = 99
        return x
    def repair(x, context):
        x[:] = 5
        return x
    cached = adapter.algorithm_unit.pairwise_distances()
    proposals = adapter.propose(SimpleNamespace(mutate_candidate=mutate, repair_candidate=repair), {})
    assert proposals[0][0] == 99  # Proposal is repaired by the control plane later.
    np.testing.assert_array_equal(adapter.pop_X[:, 0], [10., 20., 30., 40.])
    assert adapter.algorithm_unit.pairwise_distances() is cached
    adapter.algorithm_unit.require_current_feedback()


@pytest.mark.parametrize("adapter_type", [NSGA2Adapter, NSGA3Adapter, SPEA2Adapter])
def test_environmental_selection_rejects_stale_existing_feedback(adapter_type):
    adapter = adapter_type(population_size=2)
    adapter.set_population_snapshot(np.array([[0.], [1.]]), np.array([[0.], [1.]]), np.zeros(2))
    adapter.population[0] = 99
    with pytest.raises(FeatureContractError, match="reevaluate"):
        adapter.update(SimpleNamespace(), [[2.]], (np.array([[2.]]), np.zeros(1)), {})
    np.testing.assert_array_equal(adapter.population, [[99.], [1.]])


@pytest.mark.parametrize("adapter_type", [NSGA2Adapter, NSGA3Adapter, SPEA2Adapter, DifferentialEvolutionAdapter, MOEADAdapter])
def test_population_feedback_remains_current_after_real_run_and_restore(adapter_type):
    from nsgablack.core import BlackBoxProblem, ComposableSolver
    class Problem(BlackBoxProblem):
        def __init__(self):
            super().__init__(dimension=2, objectives=["minimize", "minimize"], bounds=[(-2, 2)] * 2)
        def evaluate(self, x):
            return [float(np.sum(x ** 2)), float(np.sum((x - 1) ** 2))]
    adapter = adapter_type(population_size=4)
    assert ComposableSolver(Problem(), adapter=adapter).run(max_steps=2)["status"] == "ok"
    expected = adapter.algorithm_unit.feature(SELECTION_RANKING)
    clone = adapter_type(population_size=4)
    clone.set_state(json.loads(json.dumps(adapter.get_state())))
    for actual, wanted in zip(clone.algorithm_unit.feature(SELECTION_RANKING), expected):
        np.testing.assert_array_equal(actual, wanted)
