import json

import numpy as np
import pytest

from blackbase.context import InMemorySnapshotStore
from blackbase.types import CandidateBatch, Feedback
from nsgablack.adapters import AlgorithmAdapter, NSGA2Adapter
from nsgablack.bias import (BiasModule, DiversityBias, OptimizationContext, TabuSearchBias,
                           PreferenceQuery, PreferenceScope, PreferenceScore, PreferenceContractError,
                           PopulationDiversityPreference, UnitPreferenceBias)
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.units import PopulationUnit, PopulationView, UnitBinding, UnitView
from nsgablack.representation.structure_builders import PopulationUnitBuilder


def view(rows, *, path=("search",), tokens=None):
    rows = np.asarray(rows, dtype=float).reshape(-1, 1)
    unit = PopulationUnit("population", rows, candidate_tokens=tuple(tokens or [f"m{i}" for i in range(len(rows))]))
    return PopulationView.capture(unit, UnitBinding(PopulationUnitBuilder()), owner_path=path)


def test_instance_revision_and_immutable_view():
    a, b = view([0, 2]), view([0, 2], path=("nested", "second"))
    assert a.identity != b.identity
    assert a.revision == view([0, 2]).revision
    assert a.revision != view([0, 3]).revision
    with pytest.raises(ValueError):
        a.population.setflags(write=True)
    with pytest.raises(TypeError):
        a.payload["new"] = 1


def test_four_comparison_scopes_and_transition_identity():
    candidate = PreferenceQuery("candidate", candidate=[3], candidate_token="new")
    assert candidate.scope is PreferenceScope.CANDIDATE
    pref = PopulationDiversityPreference()
    a, b = view([0, 1]), view([0, 3])
    assert pref.evaluate(PreferenceQuery("unit", unit=a)).value == 1
    assert pref.evaluate(PreferenceQuery("unit", unit=b)).value == 3
    gain = pref.evaluate(PreferenceQuery("unit_transition", unit=a, proposed_unit=b))
    assert gain.value == 2 and gain.minimization_delta() == -2
    assert pref.evaluate(PreferenceQuery("candidate_in_unit", candidate=[4], unit=b)).value == 1
    with pytest.raises(PreferenceContractError, match="preserve"):
        PreferenceQuery("unit_transition", unit=a, proposed_unit=view([0, 3], path=("another",)))
    with pytest.raises(PreferenceContractError):
        pref.evaluate(candidate)
    with pytest.raises(PreferenceContractError):
        PreferenceScore(float("nan"), "maximize", "invalid")


def test_candidate_subject_preserves_semantics_alongside_numeric_projection():
    from blackbase.types import UnknownState
    state = UnknownState([3.], {"domain_label": "branch-a"})
    query = PreferenceQuery("candidate_in_unit", candidate=state, unit=view([0, 10]))
    assert query.candidate.metadata["domain_label"] == "branch-a"
    assert PopulationDiversityPreference().evaluate(query).value == 3
    with pytest.raises(ValueError):
        query.numeric_candidate.setflags(write=True)


def test_duplicate_values_keep_identity_and_exclude_only_named_member():
    pref = PopulationDiversityPreference()
    population = view([0, 10], tokens=("old", "far"))
    assert pref.evaluate(PreferenceQuery("candidate_in_unit", candidate=[0], candidate_token="new", unit=population)).value == 0
    assert pref.evaluate(PreferenceQuery("candidate_in_unit", candidate=[0], candidate_token="old", unit=population)).value == 10
    assert pref.evaluate(PreferenceQuery("unit", unit=view([0, 0]))).value == 0


def test_duplicate_candidate_tokens_keep_distinct_slots_without_fabricated_identity():
    population = view([0, 0, 10], tokens=("shared", "shared", "far"))
    assert population.candidate_tokens == ("shared", "shared", "far")
    pref = PopulationDiversityPreference()
    assert pref.evaluate(PreferenceQuery("candidate_in_unit", candidate=[0],
        candidate_token="shared", unit=population)).value == 10
    assert pref.evaluate(PreferenceQuery("candidate_in_unit", candidate=[0],
        candidate_token="new", unit=population)).value == 0
    # Whole-population diversity measures occupied slots, including copies.
    assert pref.evaluate(PreferenceQuery("unit", unit=population)).value == pytest.approx(10 / 3)


def test_moead_duplicate_replacement_can_be_read_and_scored_by_bound_bias():
    from nsgablack.adapters import MOEADAdapter
    from nsgablack.core.state.incumbent import CandidateProvenance
    adapter = MOEADAdapter(population_size=3, nr=2)
    module = BiasModule()
    module.add(UnitPreferenceBias.from_adapter(PopulationDiversityPreference(), adapter,
                                               owner_path=("search",), weight=1))
    solver = ComposableSolver(Problem(), adapter=adapter, bias_module=module)
    adapter._n, adapter._m = 3, 2
    adapter.weights = np.array([[1., 0.], [0., 1.], [.5, .5]])
    adapter.neighbors = np.tile(np.arange(3), (3, 1))
    adapter.ideal = np.array([10., 20.])
    adapter.algorithm_unit.initialize_population([[3.], [4.], [5.]],
        [[10., 20.]] * 3, [0.] * 3, candidate_tokens=("a", "b", "c"))
    adapter._pending_indices, adapter._pending_modes = [0], ["global"]
    candidate = np.array([0.])
    # Direct update tests must supply the same published/accepted pool sources
    # that the normal control-plane evaluation path establishes.
    from blackbase.types import CandidateBatch
    for token, value in zip(("a", "b", "c", "shared"), (3., 4., 5., 0.)):
        solver.store_solutions(CandidateBatch.from_candidates([[value]], candidate_tokens=(token,)),
                              stage="accepted", provenance=(CandidateProvenance(token),))
    solver.bind_candidate_provenance([candidate], [CandidateProvenance("shared")])
    adapter.update(solver, [candidate], (np.array([[0., 0.]]), np.zeros(1)), {})
    assert adapter.get_population_candidate_tokens().count("shared") == 2
    assert adapter.preference_view(owner_path=("search",)).candidate_tokens.count("shared") == 2
    values, _ = solver.evaluate_individual(np.array([1.]))
    np.testing.assert_allclose(values, [9., 19.])


def test_provisional_members_are_compared_without_fabricated_identity():
    unit = PopulationUnit("draft", np.array([[0.], [10.]]))
    draft = PopulationView.capture(unit, UnitBinding(PopulationUnitBuilder()), owner_path=("search",))
    assert not draft.membership_identity_complete
    assert draft.candidate_tokens == (None, None)
    score = PopulationDiversityPreference().evaluate(PreferenceQuery("candidate_in_unit", candidate=[0.], unit=draft))
    assert score.value == 0


def test_legacy_diversity_rewards_distance_without_guessing_identity():
    pref = DiversityBias(weight=0.1)
    context = OptimizationContext(0, np.array([1.]), population=[np.array([0.])])
    assert pref.compute(np.array([3.]), context) < pref.compute(np.array([1.]), context)
    assert pref.compute(np.array([0.]), context) == 0


def test_unit_binding_refreshes_same_generation_without_cache_staleness():
    current = [view([0, 10])]
    bias = BiasModule()
    bias.add(UnitPreferenceBias(PopulationDiversityPreference(), lambda ctx: current[0], weight=1))
    assert bias.compute_bias(np.array([3.]), 10) == 7
    current[0] = view([3, 10])
    assert bias.compute_bias(np.array([3.]), 10) == 10


def test_legacy_population_dependency_rejects_missing_and_partitioned_source():
    module = BiasModule()
    module.add(DiversityBias())
    with pytest.raises(PreferenceContractError):
        module.compute_bias(np.array([1.]), 10)
    store = InMemorySnapshotStore()
    module.set_snapshot_store(store)
    handle = store.write({"population_authority": {"mode": "partitioned"}, "population_partitions": {}}, key="partitions")
    with pytest.raises(PreferenceContractError):
        module.compute_bias(np.array([1.]), 10, context={"population_ref": handle.key})


def test_tabu_scoring_is_pure_across_objectives_cache_and_repeated_calls():
    module = BiasModule()
    tabu = TabuSearchBias()
    module.add(tabu)
    for cache in (True, False):
        module.cache_enabled = cache
        assert module.compute_bias_vector(np.array([0.]), [10, 20]).tolist() == [10, 20]
        assert module.compute_bias_vector(np.array([0.]), [20, 10]).tolist() == [20, 10]
    assert tabu.get_state()["tokens"] == []
    admitted = CandidateBatch.from_candidates([[0.]], candidate_tokens=("committed",))
    module.record_accepted(admitted)
    module.record_accepted(admitted)
    assert tabu.get_state()["tokens"] == ["committed"]
    np.testing.assert_allclose(module.compute_bias_vector(np.array([0.]), [10, 20]), [10.075, 20.075])
    restored = BiasModule()
    restored.add(TabuSearchBias())
    restored.set_state(json.loads(json.dumps(module.get_state())))
    np.testing.assert_allclose(restored.compute_bias_vector(np.array([0.]), [10, 20]), [10.075, 20.075])


class Problem(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, objectives=["a", "b"], bounds=[(-10, 10)])

    def evaluate(self, candidate):
        return Feedback(objectives=[10., 20.])


class Proposer(AlgorithmAdapter):
    def __init__(self):
        super().__init__(name="preference_test")

    def propose(self, control, context):
        return [np.array([0.])]

    def update(self, control, candidates, feedback, context):
        pass


def test_committed_step_updates_memory_and_failure_restores_it(monkeypatch):
    module = BiasModule()
    tabu = TabuSearchBias()
    module.add(tabu)
    solver = ComposableSolver(Problem(), adapter=Proposer(), bias_module=module)
    assert solver.step().committed
    before = module.get_state()
    assert len(tabu.get_state()["tokens"]) == 1
    assert solver.checkpoint_components()["bias"] is module
    def fail(*args, **kwargs):
        raise RuntimeError("failure after preference memory update")
    monkeypatch.setattr(solver, "_finalize_evaluation_disposition", fail)
    with pytest.raises(RuntimeError, match="after preference"):
        solver.step()
    assert module.get_state() == before


def test_real_unit_preference_wiring_preserves_raw_feedback():
    adapter = NSGA2Adapter(population_size=4, offspring_size=4)
    module = BiasModule()
    module.add(UnitPreferenceBias.from_adapter(PopulationDiversityPreference(), adapter, owner_path=("search",)))
    solver = ComposableSolver(Problem(), adapter=adapter, bias_module=module)
    solver.run(max_steps=2)
    feedback = solver.get_last_feedback_batch()
    np.testing.assert_allclose(feedback.raw_objectives, np.tile([10., 20.], (4, 1)))
    assert np.all(feedback.objectives <= feedback.raw_objectives)


def test_invalid_unit_dependency_cannot_be_silently_disabled():
    module = BiasModule()
    module.add(UnitPreferenceBias(PopulationDiversityPreference(), lambda ctx: object()))
    solver = ComposableSolver(Problem(), adapter=Proposer(), bias_module=module)
    with pytest.raises(PreferenceContractError):
        solver.evaluate_individual(np.array([0.]))


@pytest.mark.parametrize("provider", [False, True])
@pytest.mark.parametrize("batch", [False, True])
def test_unit_preference_single_batch_and_provider_paths(provider, batch):
    from nsgablack.plugins import EvaluationModelConfig, EvaluationModelProviderPlugin
    module = BiasModule()
    module.add(UnitPreferenceBias(PopulationDiversityPreference(), lambda ctx: view([0, 10]), weight=1))
    solver = ComposableSolver(Problem(), adapter=Proposer(), bias_module=module)
    if provider:
        class Backend:
            def solve(self, request):
                return {"status": "ok", "objectives": [10., 20.], "violation": 0.}
        solver.register_evaluation_provider(EvaluationModelProviderPlugin(
            config=EvaluationModelConfig(scope="outer", warn_on_failure=False),
            backend_factory=lambda problem, context: Backend(),
        ).create_provider())
        solver.problem.evaluate = lambda x: pytest.fail("provider must short-circuit Problem")
    values, _ = solver.evaluate_population([[3.]]) if batch else solver.evaluate_individual(np.array([3.]))
    np.testing.assert_allclose(np.asarray(values).reshape(-1), [7., 17.])


def test_checkpoint_plugin_roundtrip_and_fresh_run_reset():
    from nsgablack.plugins import CheckpointResumePlugin
    module = BiasModule()
    module.add(TabuSearchBias())
    solver = ComposableSolver(Problem(), adapter=Proposer(), bias_module=module)
    solver.step()
    plugin = CheckpointResumePlugin()
    state = json.loads(json.dumps(plugin._collect_component_states(solver)))
    before = module.get_state()
    solver.prepare_fresh_run()
    assert module.get_bias("tabu_search_bias").get_state()["tokens"] == []
    plugin._apply_component_states(solver, state)
    assert module.get_state() == before
    corrupt = json.loads(json.dumps(state))
    corrupt["bias"]["state"]["components"]["algorithmic/tabu_search_bias"]["state"]["schema"] = "invalid"
    with pytest.raises(ValueError, match="Tabu checkpoint"):
        plugin._apply_component_states(solver, corrupt)
    del state["bias"]
    with pytest.raises(ValueError, match="missing required component"):
        plugin._apply_component_states(solver, state)


def test_restore_rejects_different_unit_instance_binding():
    a, b = NSGA2Adapter(), NSGA2Adapter()
    p = PopulationDiversityPreference()
    first = UnitPreferenceBias.from_adapter(p, a, owner_path=("first",))
    second = UnitPreferenceBias.from_adapter(p, b, owner_path=("second",))
    with pytest.raises(PreferenceContractError, match="binding"):
        second.set_state(first.get_state())
    a.algorithm_unit.unit_id = "changed"
    with pytest.raises(PreferenceContractError, match="bound identity"):
        first.compute(np.array([0.]), OptimizationContext(0, np.array([0.])))


def test_doctor_reports_missing_preference_state_codec():
    from nsgablack.utils.runtime_contracts import inspect_runtime_contracts
    bias = DiversityBias()
    bias.stateful_preference = True
    module = BiasModule()
    module.add(bias)
    solver = ComposableSolver(Problem(), adapter=Proposer(), bias_module=module)
    codes = {code for code, message in inspect_runtime_contracts(solver)}
    assert "bias-unit-preference-contract-invalid" in codes


def test_restore_failure_does_not_partially_update_other_biases():
    first, second = TabuSearchBias(), TabuSearchBias()
    second.name = "second"
    module = BiasModule()
    module.add(first)
    module.add(second)
    before = module.get_state()
    altered = json.loads(json.dumps(before))
    altered["components"]["algorithmic/tabu_search_bias"]["weight"] = .8
    altered["components"]["algorithmic/second"]["state"]["schema"] = "invalid"
    with pytest.raises(ValueError):
        module.set_state(altered)
    assert module.get_state() == before


def test_standard_bias_gallery_case_assembles_and_runs_real_preferences():
    from pathlib import Path
    from blackbase.project import build_case, load_case_builder, run_case
    root = Path(__file__).resolve().parents[1] / "examples/cases/bias_gallery"
    solver = build_case(load_case_builder(root, "bias_gallery"), resource_context={"threads": 1})
    assert isinstance(solver.bias_module.get_bias("population_novelty"), UnitPreferenceBias)
    assert isinstance(solver.bias_module.get_bias("tabu_search_bias"), TabuSearchBias)
    solver.set_max_steps(1)
    run_case(solver)
    assert solver.bias_module.get_bias("tabu_search_bias").get_state()["tokens"]
    assert solver.bias_module.get_bias("population_novelty").usage_count > 0
