"""Custom member semantics survive real selection, replacement and rollback."""
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from types import SimpleNamespace

import numpy as np
import pytest

from nsgablack.adapters import (
    CompositeAdapter, DifferentialEvolutionAdapter, MOEADAdapter,
    NSGA2Adapter, NSGA3Adapter, SPEA2Adapter,
)
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.project.scaffold.case_template_solver.pipeline.population_example import (
    AgePopulationUnit, AgePopulationBuilder,
)
from nsgablack.representation import (
    ReferencePopulationBuilder, DifferentialPopulationBuilder, DecompositionUnitBuilder,
)
from nsgablack.units import (
    PopulationChange, PopulationUnit, ReferencePopulationUnit, DifferentialPopulationUnit,
    DecompositionUnit, UnitBinding, UnitSchema, SELECTION_RANKING,
)


@dataclass
class AgeReferenceUnit(AgePopulationUnit):
    reference_points: np.ndarray = field(default_factory=lambda: np.zeros((0, 0)))
    schema = UnitSchema("test.age_reference", required_fields=(
        *ReferencePopulationUnit.schema.required_fields, "age"), candidate_projection=False)


class AgeReferenceBuilder(ReferencePopulationBuilder):
    unit_type = AgeReferenceUnit
    compatible_schemas = (ReferencePopulationUnit.schema, PopulationUnit.schema)


@dataclass
class AgeDEUnit(DifferentialPopulationUnit, AgePopulationUnit):
    schema = UnitSchema("test.age_de", required_fields=(
        *DifferentialPopulationUnit.schema.required_fields, "age"), candidate_projection=False)


class AgeDEBuilder(DifferentialPopulationBuilder):
    unit_type = AgeDEUnit
    compatible_schemas = (DifferentialPopulationUnit.schema,)


@dataclass
class AgeDecompositionUnit(DecompositionUnit, AgePopulationUnit):
    schema = UnitSchema("test.age_decomposition", required_fields=(
        *DecompositionUnit.schema.required_fields, "age"), candidate_projection=False)


class AgeDecompositionBuilder(DecompositionUnitBuilder):
    unit_type = AgeDecompositionUnit
    compatible_schemas = (DecompositionUnit.schema,)


def seed(unit=None):
    unit = unit or AgePopulationUnit("population")
    unit.initialize_population([[1.], [2.], [3.]], [[2.], [3.], [0.]], [0., 0., 0.],
                               candidate_tokens=("a", "b", "c"))
    unit.age = np.asarray([10, 4, 7])
    return unit


def test_discussed_selection_tracks_old_members_and_initializes_new_ones():
    unit = seed()
    x, f = np.array([[4.]]), np.array([[1.]])
    cached = unit.pairwise_distances()
    change = unit.apply_selection([2, 3, 0], x, f, [0.], candidate_tokens=("d",))
    assert change.previous_member_indices == (2, None, 0)
    assert change.incoming_member_indices == (None, 0, None)
    np.testing.assert_array_equal(unit.age, [8, 0, 11])
    np.testing.assert_array_equal(unit.population, [[3.], [4.], [1.]])
    np.testing.assert_array_equal(unit.objectives, [[0.], [1.], [2.]])
    assert unit.candidate_tokens == ("c", "d", "a")
    x[:], f[:] = 99., 99.
    assert unit.population[1, 0] == 4 and unit.objectives[1, 0] == 1
    assert cached[0, 2] == 2
    np.testing.assert_array_equal(unit.pairwise_distances(),
        np.linalg.norm(unit.population[:, None] - unit.population[None, :], axis=2))
    unit.require_current_feedback()


def test_equal_numeric_candidates_have_different_member_sources():
    unit = seed()
    unit.apply_selection([0, 3], [[1.]], [[2.]], [0.], candidate_tokens=("new-a",))
    assert unit.candidate_tokens == ("a", "new-a")
    np.testing.assert_array_equal(unit.population, [[1.], [1.]])
    np.testing.assert_array_equal(unit.age, [11, 0])


@pytest.mark.parametrize("adapter_type,builder", [
    (NSGA2Adapter, AgePopulationBuilder), (SPEA2Adapter, AgePopulationBuilder),
    (NSGA3Adapter, AgeReferenceBuilder),
])
def test_real_adapter_selects_without_knowing_custom_age(adapter_type, builder):
    adapter = adapter_type(population_size=3, unit_binding=UnitBinding(builder()))
    seed(adapter.algorithm_unit)
    control = SimpleNamespace(candidate_provenance_for=lambda candidate: SimpleNamespace(candidate_token="d"))
    adapter.update(control, [[4.]], (np.array([[1.]]), np.zeros(1)), {})
    assert adapter.get_population_candidate_tokens() == ("c", "d", "a")
    np.testing.assert_array_equal(adapter.algorithm_unit.age, [8, 0, 11])


def test_replacement_resets_changed_rows_once_and_keeps_slot_provenance():
    unit = seed()
    change = unit.replace_evaluated_rows([1, 1, 2], [[9.], [8.], [8.]], [[9.], [8.], [8.]],
                                         [0., 0., 0.], candidate_tokens=("x", "y", "y"))
    assert change.previous_member_indices == (0, None, None)
    assert change.incoming_member_indices == (None, 1, 2)
    np.testing.assert_array_equal(unit.age, [10, 0, 0])
    assert unit.candidate_tokens == ("a", "y", "y")


@pytest.mark.parametrize("operation", ["initialize", "selection", "replacement", "clear"])
@pytest.mark.parametrize("failure", ["raise", "missing", "base-field", "shape", "service"])
def test_hook_failure_never_publishes_partial_population_or_extension(operation, failure):
    class Broken(AgePopulationUnit):
        fail = False
        def on_members_changed(self, change):
            if not self.fail:
                return super().on_members_changed(change)
            if failure == "raise":
                raise RuntimeError("extension failure")
            if failure == "missing":
                return {}
            if failure == "base-field":
                return {"age": [], "population": [[99.]]}
            if failure == "shape":
                return {"age": np.zeros(change.count + 1)}
            return {"age": SimpleNamespace(session="live")}
    unit = seed(Broken("p"))
    binding = UnitBinding(AgePopulationBuilder())
    before = binding.dump(unit)
    cached = unit.pairwise_distances()
    unit.fail = True
    with pytest.raises((TypeError, ValueError, RuntimeError)):
        if operation == "initialize":
            unit.initialize_population([[4.]], [[1.]], [0.], candidate_tokens=("d",))
        elif operation == "selection":
            unit.apply_selection([2, 3, 0], [[4.]], [[1.]], [0.], candidate_tokens=("d",))
        elif operation == "replacement":
            unit.replace_evaluated_rows([1], [[4.]], [[1.]], [0.], candidate_tokens=("d",))
        else:
            unit.clear_population()
    assert binding.dump(unit) == before
    assert unit.pairwise_distances() is cached


@pytest.mark.parametrize("indices", [[-1], [4], [0.5], [[0]], [True]])
def test_invalid_selection_has_no_member_effect(indices):
    unit = seed()
    with pytest.raises(ValueError):
        unit.apply_selection(indices, [[4.]], [[1.]], [0.], candidate_tokens=("d",))
    np.testing.assert_array_equal(unit.age, [10, 4, 7])
    assert unit.candidate_tokens == ("a", "b", "c")


def test_empty_selection_and_clear_are_explicit_structural_operations():
    unit = seed()
    unit.apply_selection([], [[4.]], [[1.]], [0.], candidate_tokens=("d",))
    assert unit.population.shape == (0, 1) and unit.age.shape == (0,)
    unit.clear_population()
    assert unit.population is None and unit.candidate_tokens == ()


@pytest.mark.parametrize("updates", [
    {"population": [[4., 5.]]}, {"objectives": [[1., 2.]]},
    {"violations": []}, {"candidate_tokens": ()}, {"candidate_tokens": (object(),)},
])
def test_invalid_incoming_selection_rows_cannot_drop_alignment(updates):
    unit = seed()
    args = dict(population=[[4.]], objectives=[[1.]], violations=[0.], candidate_tokens=("d",))
    args.update(updates)
    with pytest.raises((ValueError, TypeError)):
        unit.apply_selection([0, 3], **args)
    assert unit.candidate_tokens == ("a", "b", "c")
    np.testing.assert_array_equal(unit.age, [10, 4, 7])


def test_custom_validator_cannot_bypass_base_member_alignment():
    class Invalid(AgePopulationUnit):
        def validate(self):
            pass
        def on_members_changed(self, change):
            return {"age": np.zeros(change.count + 1)}
    unit = Invalid("p")
    with pytest.raises(ValueError, match="age.*align"):
        unit.initialize_population([[1.]], [[1.]], [0.])
    assert unit.population is None


@pytest.mark.parametrize("adapter_type,builder", [
    (NSGA2Adapter, AgePopulationBuilder), (SPEA2Adapter, AgePopulationBuilder),
    (NSGA3Adapter, AgeReferenceBuilder), (DifferentialEvolutionAdapter, AgeDEBuilder),
    (MOEADAdapter, AgeDecompositionBuilder),
])
def test_codec_and_nested_transaction_restore_exact_age_without_replaying_hook(adapter_type, builder):
    adapter = adapter_type(unit_binding=UnitBinding(builder()))
    seed(adapter.algorithm_unit)
    saved = json.loads(json.dumps(adapter.get_state()))
    transaction = CompositeAdapter([adapter]).begin_step_transaction()
    adapter.algorithm_unit.apply_selection([3], [[4.]], [[1.]], [0.], candidate_tokens=("d",))
    transaction.rollback()
    np.testing.assert_array_equal(adapter.algorithm_unit.age, [10, 4, 7])
    adapter.set_state(saved)
    np.testing.assert_array_equal(adapter.algorithm_unit.age, [10, 4, 7])
    assert adapter.get_population_candidate_tokens() == ("a", "b", "c")


def test_snapshot_feedback_refresh_is_not_a_selection_but_new_population_is_initialization():
    adapter = NSGA2Adapter(unit_binding=UnitBinding(AgePopulationBuilder()))
    seed(adapter.algorithm_unit)
    adapter.set_population_snapshot([[1.], [2.], [3.]], [[4.], [9.], [1.]], [0., 0., 0.])
    np.testing.assert_array_equal(adapter.algorithm_unit.age, [10, 4, 7])
    adapter.set_population_snapshot([[9.]], [[81.]], [0.])
    np.testing.assert_array_equal(adapter.algorithm_unit.age, [0])


@pytest.mark.parametrize("adapter_type,builder", [
    (NSGA2Adapter, AgePopulationBuilder), (DifferentialEvolutionAdapter, AgeDEBuilder),
])
def test_legacy_numeric_state_without_unit_envelope_initializes_member_extensions(adapter_type, builder):
    adapter = adapter_type(unit_binding=UnitBinding(builder()))
    seed(adapter.algorithm_unit)
    state = json.loads(json.dumps(adapter.get_state()))
    state["algorithm_unit"] = None
    clone = adapter_type(unit_binding=UnitBinding(builder()))
    clone.set_state(state)
    assert clone.get_population_candidate_tokens() == ("a", "b", "c")
    np.testing.assert_array_equal(clone.population, adapter.population)
    np.testing.assert_array_equal(clone.algorithm_unit.age, [0, 0, 0])


def test_doctor_rejects_invalid_member_contract_without_running_hook():
    from nsgablack.project.doctor_core.model import add_diagnostic
    from nsgablack.project.doctor_core.rules.build_solver import check_unit_bindings
    adapter = NSGA2Adapter()
    adapter.algorithm_unit.member_fields = ("population",)
    diagnostics = []
    check_unit_bindings(solver=SimpleNamespace(adapter=adapter), build_file=None,
                        diags=diagnostics, add=add_diagnostic)
    assert diagnostics[0].code == "adapter-unit-binding-invalid"


@pytest.mark.parametrize("values", [
    {"previous_member_indices": (None,), "incoming_member_indices": (None,)},
    {"previous_member_indices": (0,), "incoming_member_indices": (0,)},
    {"previous_member_indices": (3,), "incoming_member_indices": (None,)},
    {"previous_member_indices": (None,), "incoming_member_indices": (True,)},
])
def test_population_change_rejects_ambiguous_or_invalid_sources(values):
    with pytest.raises(ValueError):
        PopulationChange("selection", 3, 1, **values)


class Sphere(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=2, objectives=["minimize", "minimize"], bounds=[(-2, 2)] * 2)
    def evaluate(self, x):
        return [float(np.sum(x ** 2)), float(np.sum((x - 1) ** 2))]


@pytest.mark.parametrize("adapter_type,builder", [
    (NSGA2Adapter, AgePopulationBuilder), (SPEA2Adapter, AgePopulationBuilder),
    (NSGA3Adapter, AgeReferenceBuilder), (DifferentialEvolutionAdapter, AgeDEBuilder),
    (MOEADAdapter, AgeDecompositionBuilder),
])
def test_custom_members_survive_full_run_checkpoint_and_fresh_setup(adapter_type, builder):
    adapter = adapter_type(population_size=4, unit_binding=UnitBinding(builder()))
    solver = ComposableSolver(Sphere(), adapter=adapter)
    assert solver.run(max_steps=2)["status"] == "ok"
    adapter.algorithm_unit.validate()
    saved = json.loads(json.dumps(adapter.get_state()))
    expected = adapter.algorithm_unit.age.copy()
    clone = adapter_type(population_size=4, unit_binding=UnitBinding(builder()))
    clone.set_state(saved)
    np.testing.assert_array_equal(clone.algorithm_unit.age, expected)
    assert clone.get_population_candidate_tokens() == adapter.get_population_candidate_tokens()
    before = clone.algorithm_unit.feature(SELECTION_RANKING)
    clone.algorithm_unit.validate()
    assert clone.algorithm_unit.feature(SELECTION_RANKING) is before
    assert solver.run(max_steps=1)["status"] == "ok"
    adapter.algorithm_unit.validate()


def test_documented_age_example_runs_verbatim():
    from nsgablack.project.starter import build_starter_solver
    document = Path(__file__).resolve().parents[1] / "docs/architecture/UNIT_MEMBER_OPERATIONS_CN.md"
    code = next(s for s in re.findall(r"```python\s*\n(.*?)```", document.read_text(encoding="utf-8"), re.S)
                if "class AgePopulationUnit" in s)
    scope = {"__name__": __name__}
    exec(compile(code, str(document), "exec"), scope)
    solver = build_starter_solver(component_overrides={"adapter": scope["adapter"]}, max_steps=2)
    assert solver.run()["status"] == "ok"
    scope["adapter"].algorithm_unit.validate()
    assert len(scope["adapter"].algorithm_unit.age) == len(scope["adapter"].population)


def test_generated_case_can_select_custom_population_through_formal_override(tmp_path):
    from blackbase.project import load_case_builder, build_case, run_case
    from nsgablack.project.scaffold import create_project, add_case
    root = create_project(tmp_path / "members")
    add_case("search", "solver", project_root=root)
    build_file = root / "cases/search/build_solver.py"
    # This is the ordinary Case authoring surface. Import the generated Unit
    # inside the canonical builder, under the loader's scoped import context.
    build_file.write_text('''from nsgablack.project.starter import build_starter_solver
from nsgablack.adapters import NSGA2Adapter
from nsgablack.units import UnitBinding
from .pipeline.population_example import AgePopulationBuilder

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    adapter = NSGA2Adapter(population_size=4, offspring_size=4,
                          unit_binding=UnitBinding(AgePopulationBuilder()))
    overrides = {"adapter": adapter, **(component_overrides or {})}
    return build_starter_solver(resource_context=resource_context,
                                component_overrides=overrides, max_steps=2)
''', encoding="utf-8")
    builder = load_case_builder(root, "search")
    solver = build_case(builder, resource_context={"threads": 1, "workers": 1})
    assert run_case(solver) is not None
    assert isinstance(solver.adapter, NSGA2Adapter)
    assert solver.adapter.unit_binding.schema.name == "case.age_population"
    solver.adapter.algorithm_unit.validate()
    assert len(solver.adapter.algorithm_unit.age) == 4
