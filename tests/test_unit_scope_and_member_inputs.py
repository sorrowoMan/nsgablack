"""Candidate scopes and member inputs use semantic identity, never numeric guesses."""
from dataclasses import dataclass, field
import json

import numpy as np
import pytest
from blackbase.types import UnknownState

from nsgablack.adapters import (AlgorithmAdapter, CompositeAdapter, DifferentialEvolutionAdapter,
    MOEADAdapter, MultiStrategyConfig, NSGA2Adapter, StrategyRouterAdapter, StrategySpec, StrategyTask)
from nsgablack.adapters.strategy_task import attach_strategy_origin
from nsgablack.bias import (BiasModule, OptimizationContext, PopulationDiversityPreference,
    PreferenceContractError, UnitPreferenceBias)
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.core.state.incumbent import CandidateProvenance
from nsgablack.representation import (DecompositionUnitBuilder, DifferentialPopulationBuilder,
    PopulationUnitBuilder)
from nsgablack.units import (DecompositionUnit, DifferentialPopulationUnit, PopulationChange,
    PopulationUnit, UnitBinding, UnitSchema)


@dataclass
class AnnotatedPopulation(PopulationUnit):
    labels: list = field(default_factory=list)
    parents: list = field(default_factory=list)
    births: list = field(default_factory=list)
    member_fields = ("labels", "parents", "births")
    schema = UnitSchema("test.annotated_population", required_fields=(
        *PopulationUnit.schema.required_fields, *member_fields), candidate_projection=False)

    def on_members_changed(self, change):
        labels, parents, births = [], [], []
        for old, new in zip(change.previous_member_indices, change.incoming_member_indices):
            if old is not None:
                labels.append(self.labels[old])
                parents.append(self.parents[old])
                births.append(self.births[old])
            else:
                labels.append(change.incoming_metadata[new].get("label", "unknown"))
                provenance = change.incoming_provenance[new]
                parents.append(None if provenance is None else provenance["parent_token"])
                births.append(float(change.incoming_population[new, 0]))
        return dict(labels=labels, parents=parents, births=births)


class AnnotatedBuilder(PopulationUnitBuilder):
    unit_type = AnnotatedPopulation
    compatible_schemas = (PopulationUnit.schema,)


@dataclass
class AnnotatedDE(DifferentialPopulationUnit, AnnotatedPopulation):
    schema = UnitSchema("test.annotated_de", required_fields=(
        *DifferentialPopulationUnit.schema.required_fields, *AnnotatedPopulation.member_fields),
        candidate_projection=False)


class AnnotatedDEBuilder(DifferentialPopulationBuilder):
    unit_type = AnnotatedDE
    compatible_schemas = (DifferentialPopulationUnit.schema,)


@dataclass
class AnnotatedDecomposition(DecompositionUnit, AnnotatedPopulation):
    schema = UnitSchema("test.annotated_decomposition", required_fields=(
        *DecompositionUnit.schema.required_fields, *AnnotatedPopulation.member_fields),
        candidate_projection=False)


class AnnotatedDecompositionBuilder(DecompositionUnitBuilder):
    unit_type = AnnotatedDecomposition
    compatible_schemas = (DecompositionUnit.schema,)


def test_member_hook_can_read_new_rows_and_metadata_without_publishing_them_first():
    unit = AnnotatedPopulation("p")
    metadata = [{"label": "first"}, {"label": "second"}]
    unit.initialize_population([[1.], [2.]], [[1.], [4.]], [0., 0.],
        candidate_tokens=("a", "b"), candidate_metadata=metadata)
    x, f, v = np.array([[3.]]), np.array([[9.]]), np.zeros(1)
    provenance = CandidateProvenance("c", parent_token="b").as_dict()
    change = unit.apply_selection([1, 2, 0], x, f, v, candidate_tokens=("c",),
        candidate_metadata=({"label": "third"},), candidate_provenance=(provenance,))
    assert unit.labels == ["second", "third", "first"]
    assert unit.parents == [None, "b", None] and unit.births == [2., 3., 1.]
    x[:], f[:], v[:], provenance["parent_token"] = 100., 100., 100., "changed"
    assert change.incoming_population[0, 0] == 3.
    assert change.incoming_objectives[0, 0] == 9. and change.incoming_violations[0] == 0.
    assert change.incoming_provenance[0]["parent_token"] == "b"
    for array in (change.incoming_population, change.incoming_objectives, change.incoming_violations):
        with pytest.raises(ValueError):
            array.setflags(write=True)
    with pytest.raises(TypeError):
        change.incoming_metadata[0]["label"] = "changed"
    unit.replace_evaluated_rows([1, 1, 2], [[4.], [5.], [5.]], [[16.], [25.], [25.]], [0.] * 3,
        candidate_tokens=("d", "e", "e"), candidate_metadata=({"label": "fourth"}, {"label": "fifth"}, {"label": "fifth"}))
    assert unit.labels == ["second", "fifth", "fifth"] and unit.births == [2., 5., 5.]
    unit.clear_population()
    assert unit.labels == unit.parents == unit.births == []


@pytest.mark.parametrize("extra", [
    dict(incoming_population=[[1.], [2.]]),
    dict(incoming_population=[[1.]], incoming_tokens=("a", "b")),
    dict(incoming_population=[[1.]], incoming_metadata=(object(),)),
    dict(incoming_population=[[1.]], incoming_objectives=[[1.]]),
    dict(incoming_population=[[1.]], incoming_tokens=("a",), incoming_provenance=({"candidate_token": "b"},)),
])
def test_bad_member_inputs_are_rejected_before_hook_or_publication(extra):
    with pytest.raises(ValueError):
        PopulationChange("initialize", 0, 1, (None,), (0,), **extra)


@pytest.mark.parametrize("kind,builder", [
    (NSGA2Adapter, AnnotatedBuilder), (DifferentialEvolutionAdapter, AnnotatedDEBuilder),
    (MOEADAdapter, AnnotatedDecompositionBuilder),
])
def test_real_adapter_passes_provenance_to_unknown_member_fields_and_codec_rolls_it_back(kind, builder):
    adapter = kind(population_size=2, unit_binding=UnitBinding(builder()))
    unit = adapter.algorithm_unit
    unit.initialize_population([[5.], [6.]], [[25., 25.], [36., 36.]], [0., 0.],
        candidate_tokens=("old-a", "old-b"), candidate_metadata=({"label": "a"}, {"label": "b"}))
    if kind is NSGA2Adapter:
        adapter.cfg.population_size = 1
    elif kind is DifferentialEvolutionAdapter:
        adapter._last_target_indices, adapter._last_target_scores = [0], np.array([50.])
    else:
        adapter._n, adapter._m = 2, 2
        adapter.weights = np.eye(2)
        adapter.neighbors = np.tile(np.arange(2), (2, 1))
        adapter.ideal = np.array([25., 25.])
        adapter._pending_indices, adapter._pending_modes = [0], ["global"]
    control = ComposableSolver(ConstantProblem(), adapter=adapter)
    candidate = UnknownState([0.], {"label": "offspring"})
    record = CandidateProvenance("new", parent_token="old-a")
    control.bind_candidate_provenance([candidate], [record])
    records = control.prepare_candidate_provenance([candidate])
    from blackbase.types import CandidateBatch
    control.store_solutions(CandidateBatch.from_candidates([candidate], candidate_tokens=("new",)),
                            stage="accepted", provenance=records)
    control.store_solutions(CandidateBatch.from_candidates([[5.], [6.]],
                            candidate_tokens=("old-a", "old-b")), stage="accepted",
                            provenance=(CandidateProvenance("old-a"), CandidateProvenance("old-b")))
    numeric = candidate.as_array()
    control.bind_candidate_provenance([numeric], records)
    saved = json.loads(json.dumps(adapter.get_state()))
    transaction = CompositeAdapter([adapter]).begin_step_transaction()
    adapter.update(control, [numeric], (np.zeros((1, 2)), np.zeros(1)), {})
    assert "offspring" in adapter.algorithm_unit.labels
    assert adapter.algorithm_unit.parents[adapter.algorithm_unit.labels.index("offspring")] == "old-a"
    after = json.loads(json.dumps(adapter.get_state()))
    transaction.rollback()
    assert adapter.get_state()["algorithm_unit"] == saved["algorithm_unit"]
    adapter.set_state(after)
    assert adapter.get_state()["algorithm_unit"] == after["algorithm_unit"]


class ConstantProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, objectives=["minimize", "minimize"], bounds=[(-20., 20.)])
    def evaluate(self, x):
        return [10., 20.]


def test_initial_environmental_selection_keeps_unknown_member_inputs_aligned(monkeypatch):
    adapter = NSGA2Adapter(population_size=2, unit_binding=UnitBinding(AnnotatedBuilder()))
    control = ComposableSolver(ConstantProblem(), adapter=adapter)
    states = [UnknownState([value], {"label": label})
              for value, label in zip((5., 1., 4., 2.), ("a", "b", "c", "d"))]
    records = [CandidateProvenance(label, parent_token="parent-"+label)
               for label in ("a", "b", "c", "d")]
    control.bind_candidate_provenance(states, records)
    records = control.prepare_candidate_provenance(states)
    candidates = [state.as_array() for state in states]
    control.bind_candidate_provenance(candidates, records)
    changes = []
    ordinary = adapter.algorithm_unit.on_members_changed
    def capture(change):
        changes.append(change)
        return ordinary(change)
    monkeypatch.setattr(adapter.algorithm_unit, "on_members_changed", capture)
    adapter.update(control, candidates, (np.asarray(candidates), np.zeros(4)), {})
    assert len(changes) == 1
    assert adapter.get_population_candidate_tokens() == ("b", "d")
    assert adapter.algorithm_unit.labels == ["b", "d"]
    assert adapter.algorithm_unit.parents == ["parent-b", "parent-d"]
    assert adapter.algorithm_unit.births == [1., 2.]
    np.testing.assert_array_equal(adapter.population, [[1.], [2.]])
    np.testing.assert_array_equal(adapter.objectives, [[1.], [2.]])
    adapter.algorithm_unit.require_current_feedback()


def reference():
    adapter = NSGA2Adapter()
    adapter.algorithm_unit.initialize_population([[0.], [10.]], [[10., 20.]] * 2, [0., 0.],
                                                  candidate_tokens=("old", "far"))
    return adapter


def tagged_candidate(path):
    task = StrategyTask(path, "same-role", 0, 0, "same-name", 0, "search", 0, 1)
    return attach_strategy_origin(UnknownState([3.], {"label": "proposal"}), task, 0, object())


@pytest.mark.parametrize("batch", [False, True])
@pytest.mark.parametrize("provider", [False, True])
def test_candidate_scope_is_independent_of_reference_unit_and_global_role_aliases(batch, provider):
    module = BiasModule()
    module.add(UnitPreferenceBias.from_adapter(PopulationDiversityPreference(), reference(),
        owner_path=("reference",), apply_to_paths=(("unit:left:0",),), weight=1))
    solver = ComposableSolver(ConstantProblem(), bias_module=module)
    if provider:
        from nsgablack.plugins import EvaluationModelConfig, EvaluationModelProviderPlugin
        class Backend:
            def solve(self, request):
                return dict(status="ok", objectives=[10., 20.], violation=0.)
        solver.register_evaluation_provider(EvaluationModelProviderPlugin(
            config=EvaluationModelConfig(scope="outer", warn_on_failure=False),
            backend_factory=lambda problem, context: Backend()).create_provider())
        solver.problem.evaluate = lambda x: pytest.fail("Provider must short-circuit")
    for path, expected in [(("unit:left:0", "unit:same:0"), [7., 17.]),
                            (("unit:right:1", "unit:same:0"), [10., 20.])]:
        candidate = tagged_candidate(path)
        records = solver.prepare_candidate_provenance([candidate])
        population = np.array([candidate.as_array()], dtype=float)
        solver.activate_candidate_provenance(population, records)
        values, _ = solver.evaluate_population(population) if batch else solver.evaluate_individual(population[0])
        np.testing.assert_allclose(np.asarray(values).reshape(-1), expected)
    # Standalone evaluations lack an origin and do not inherit the last scope.
    solver.context_store.set("role", "same-role")
    values, _ = solver.evaluate_individual(np.array([3.]))
    np.testing.assert_allclose(values, [10., 20.])


class SameProposal(AlgorithmAdapter):
    def __init__(self):
        super().__init__(name="same")
    def propose(self, control, context):
        return [UnknownState([3.], {"label": "same-numeric"})]
    def update(self, control, candidates, feedback, context):
        pass


def router(*children):
    return StrategyRouterAdapter(strategies=[StrategySpec(child, f"role{i}") for i, child in enumerate(children)],
        config=MultiStrategyConfig(total_batch_size=2 * len(children), adapt_weights=False))


def test_nested_same_type_candidates_are_scoped_through_real_step_and_snapshot():
    inner = router(SameProposal(), SameProposal())
    outer = router(inner, SameProposal())
    module = BiasModule()
    module.add(UnitPreferenceBias.from_adapter(PopulationDiversityPreference(), reference(),
        owner_path=("reference",), apply_to_paths=(("unit:role0:0", "unit:role1:1"),), weight=1))
    solver = ComposableSolver(ConstantProblem(), adapter=outer, bias_module=module)
    solver.setup()
    assert solver.step().committed
    feedback = solver.get_last_feedback_batch()
    np.testing.assert_allclose(feedback.objectives, [[10., 20.], [7., 17.], [10., 20.]])
    np.testing.assert_allclose(feedback.raw_objectives, [[10., 20.]] * 3)
    evidence = solver.read_snapshot(solver._last_evaluation_event_snapshot_key)
    assert evidence is not None


def test_scope_decline_does_not_read_other_unit_and_restore_rejects_changed_scope():
    bias = UnitPreferenceBias(PopulationDiversityPreference(), lambda ctx: pytest.fail("out-of-scope view read"),
                              apply_to_paths=(("left",),))
    assert bias.compute(np.array([3.]), OptimizationContext(0, np.array([3.]))) == 0.
    first = UnitPreferenceBias.from_adapter(PopulationDiversityPreference(), reference(),
        owner_path=("reference",), apply_to_paths=(("left",),))
    second = UnitPreferenceBias.from_adapter(PopulationDiversityPreference(), reference(),
        owner_path=("reference",), apply_to_paths=(("right",),))
    with pytest.raises(PreferenceContractError, match="binding"):
        second.set_state(json.loads(json.dumps(first.get_state())))
    invalid = UnknownState([3.], {"nsgablack.strategy_origins": [{"schema": "invalid"}]})
    with pytest.raises(PreferenceContractError):
        first.compute(np.array([3.]), OptimizationContext(0, np.array([3.]), candidate_state=invalid))


@pytest.mark.parametrize("reverse", [False, True])
def test_exact_batch_row_identity_does_not_bind_equal_standalone_copy(reverse):
    solver = ComposableSolver(ConstantProblem())
    source = [tagged_candidate(("left",)), tagged_candidate(("right",))]
    records = solver.prepare_candidate_provenance(source)
    values = np.array([[3.], [3.]])
    if reverse:
        values = values[::-1]
    solver.activate_candidate_provenance(values, records)
    for index, record in enumerate(records):
        assert solver.candidate_provenance_for(values[index]).candidate_token == record.candidate_token
    assert solver.candidate_provenance_for(values[0].copy()) is None
    bias = UnitPreferenceBias.from_adapter(PopulationDiversityPreference(), reference(),
        owner_path=("reference",), apply_to_paths=(("left",),), weight=1)
    module = BiasModule()
    module.add(bias)
    solver.set_bias_module(module)
    np.testing.assert_allclose(solver.evaluate_individual(values[0])[0], [7., 17.])
    np.testing.assert_allclose(solver.evaluate_individual(values[1])[0], [10., 20.])
    np.testing.assert_allclose(solver.evaluate_individual(values[0].copy())[0], [10., 20.])


def test_semantic_reader_failure_cannot_silently_disable_scoped_bias(monkeypatch):
    module = BiasModule()
    module.add(UnitPreferenceBias.from_adapter(PopulationDiversityPreference(), reference(),
        owner_path=("reference",), apply_to_paths=(("left",),)))
    solver = ComposableSolver(ConstantProblem(), bias_module=module)
    def broken(candidate):
        raise ValueError("corrupt semantic record")
    monkeypatch.setattr(solver, "semantic_candidate_state", broken)
    with pytest.raises(PreferenceContractError, match="semantic record"):
        solver.evaluate_individual(np.array([3.]))


def test_doctor_checks_scope_shape_without_computing_preference():
    from nsgablack.utils.runtime_contracts import inspect_runtime_contracts
    module = BiasModule()
    bias = UnitPreferenceBias.from_adapter(PopulationDiversityPreference(), reference(), owner_path=("reference",))
    module.add(bias)
    bias.apply_to_paths = ("flat/path",)
    solver = ComposableSolver(ConstantProblem(), bias_module=module)
    assert "bias-unit-preference-contract-invalid" in {code for code, message in inspect_runtime_contracts(solver)}
