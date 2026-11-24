from dataclasses import dataclass
import json
from types import SimpleNamespace

import numpy as np
import pytest

from nsgablack.adapters import (
    CompositeAdapter, MASAdapter, MOEADAdapter, NSGA2Adapter, NSGA3Adapter,
    SPEA2Adapter, VNSAdapter,
)
from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.representation import (
    DecompositionUnitBuilder, DifferentialPopulationBuilder, NeighborhoodUnitBuilder,
    PopulationUnitBuilder, ReferencePopulationBuilder, build_pipeline_kernel,
)
from nsgablack.representation.structure_builders import StructureUnitBuilder
from nsgablack.units import (
    DecompositionUnit, DifferentialPopulationUnit, ModelSearchUnit, PopulationUnit,
    StructureBuildRequest, UnitBinding, UnitSchema,
)


class Problem(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=2, objectives=["minimize", "minimize"], bounds=[(-2, 2)] * 2)

    def evaluate(self, x):
        return np.array([np.sum(x ** 2), np.sum((x - 1) ** 2)])


@pytest.mark.parametrize("kwargs", [
    {"version": True}, {"candidate_projection": 1},
    {"required_fields": "population"}, {"required_fields": ("population", "population")},
])
def test_schema_rejects_ambiguous_declarations(kwargs):
    with pytest.raises((TypeError, ValueError)):
        UnitSchema("test.schema", **kwargs)


@pytest.mark.parametrize("adapter_type", [NSGA2Adapter, SPEA2Adapter, NSGA3Adapter])
def test_one_reference_builder_serves_compatible_adapters_and_restores(adapter_type):
    binding = UnitBinding(ReferencePopulationBuilder())
    adapter = adapter_type(population_size=4, offspring_size=4, unit_binding=binding)
    result = ComposableSolver(problem=Problem(), adapter=adapter).run(max_steps=2)
    assert result["status"] == "ok"
    report = adapter.get_unit_contracts()[adapter.name]["alignment"]["primary"]
    assert report["match"] == ("exact" if adapter_type is NSGA3Adapter else "declared-compatible")
    assert report["requires"] == adapter.unit_schema.as_dict()
    saved = json.loads(json.dumps(adapter.get_state()))
    clone = adapter_type(unit_binding=binding)
    clone.set_state(saved)
    np.testing.assert_array_equal(clone.population, adapter.population)
    assert clone.get_population_candidate_tokens() == adapter.get_population_candidate_tokens()
    np.testing.assert_array_equal(clone.algorithm_unit.reference_points, adapter.algorithm_unit.reference_points)


@dataclass
class TaggedPopulation(PopulationUnit):
    tag: str = "domain-layout"
    schema = UnitSchema("test.extended_population", required_fields=(*PopulationUnit.schema.required_fields, "tag"),
                        candidate_projection=False)


class TaggedBuilder(PopulationUnitBuilder):
    unit_type = TaggedPopulation
    compatible_schemas = (PopulationUnit.schema,)


def test_declared_custom_schema_keeps_extra_state_through_rollback():
    adapter = NSGA2Adapter(unit_binding=UnitBinding(TaggedBuilder()))
    assert adapter.ensure_unit().schema != adapter.unit_schema
    transaction = adapter.begin_step_transaction()
    adapter.algorithm_unit.tag = "changed"
    transaction.rollback()
    assert adapter.algorithm_unit.tag == "domain-layout"


def test_same_fields_without_explicit_compatibility_do_not_authorize_reuse():
    class Undeclared(TaggedBuilder):
        compatible_schemas = ()
    with pytest.raises(ValueError, match="schema mismatch"):
        NSGA2Adapter(unit_binding=UnitBinding(Undeclared()))


def test_compatibility_is_directional_and_version_exact():
    richer = UnitBinding(ReferencePopulationBuilder())
    richer.require(PopulationUnit.schema)
    with pytest.raises(ValueError, match="schema mismatch"):
        UnitBinding(PopulationUnitBuilder()).require(richer.schema)
    newer = UnitSchema(PopulationUnit.schema.name, version=2,
                       required_fields=PopulationUnit.schema.required_fields, candidate_projection=False)
    with pytest.raises(ValueError, match="schema mismatch"):
        richer.require(newer)


@pytest.mark.parametrize("target, error", [
    (UnitSchema("needs_more", required_fields=("unknown_field",), candidate_projection=False), "absent"),
    (UnitSchema("candidate"), "projection"),
    ("nsgablack.population", "UnitSchema"),
])
def test_inconsistent_compatibility_declarations_are_rejected(target, error):
    class Invalid(PopulationUnitBuilder):
        compatible_schemas = (target,)
    with pytest.raises((TypeError, ValueError), match=error):
        UnitBinding(Invalid())


def test_compatible_schema_does_not_authorize_codec_conversion():
    binding = UnitBinding(TaggedBuilder(), name="same-codec-name/v1")
    unit = binding.build(StructureBuildRequest("population"))
    saved = json.loads(json.dumps(binding.dump(unit)))
    with pytest.raises(ValueError, match="binding/schema differs"):
        UnitBinding(PopulationUnitBuilder(), name="same-codec-name/v1").restore(saved)
    # Existing checkpoints keep the actual schema/binding envelope; assembly
    # requirements and operation capabilities are not new codec identity keys.
    assert set(saved["contract"]) == {"schema", "binding"}
    assert saved["contract"]["schema"] == TaggedPopulation.schema.as_dict()


def test_builder_must_return_its_actual_schema_even_when_base_is_compatible():
    class Wrong(ReferencePopulationBuilder):
        def build(self, request, context=None):
            return PopulationUnit(request.unit_id)
    binding = UnitBinding(Wrong())
    binding.require(PopulationUnit.schema)
    with pytest.raises(ValueError, match="does not match"):
        binding.build(StructureBuildRequest("population"))


def test_missing_operation_fails_before_any_construction_side_effect():
    class Incomplete(ReferencePopulationBuilder):
        supported_operations = ("initialize",)
        def build(self, request, context=None):
            pytest.fail("assembly must fail before invoking the builder")
    with pytest.raises(ValueError, match="nsga3/primary.*reference_directions"):
        NSGA3Adapter(unit_binding=UnitBinding(Incomplete()))


def test_missing_model_factory_is_an_assembly_error():
    class NoModel(StructureUnitBuilder):
        unit_type = ModelSearchUnit
    with pytest.raises(TypeError, match="create_model"):
        MASAdapter(unit_binding=UnitBinding(NoModel()))


def test_kernel_runner_may_declare_a_stricter_operation_surface():
    builder = ReferencePopulationBuilder()
    kernel = build_pipeline_kernel(
        {"slots": [{"slot": "build_unit", "operators": ["unit"], "method": "build"}]},
        operator_registry={"unit": builder})
    binding = kernel.bind_units(builder, name="restricted/v1", operations=("initialize",))
    NSGA2Adapter(unit_binding=binding)
    with pytest.raises(ValueError, match="reference_directions"):
        NSGA3Adapter(unit_binding=binding)
    with pytest.raises(ValueError, match="does not declare"):
        binding.build(StructureBuildRequest("refs", operation="reference_directions"))


def test_additional_and_nested_requirements_use_the_same_doctor_check():
    from nsgablack.project.doctor_core.model import add_diagnostic
    from nsgablack.project.doctor_core.rules.build_solver import check_unit_bindings
    class Incomplete(NeighborhoodUnitBuilder):
        supported_operations = ()
    child = VNSAdapter()
    child.neighborhood_binding = UnitBinding(Incomplete())
    root = CompositeAdapter([child])
    diagnostics = []
    check_unit_bindings(solver=SimpleNamespace(adapter=root), build_file=None,
                        diags=diagnostics, add=add_diagnostic)
    assert diagnostics[0].code == "adapter-unit-binding-invalid"
    with pytest.raises(ValueError, match="vns/neighborhood.*initialize"):
        ComposableSolver(problem=Problem(), adapter=root)


@pytest.mark.parametrize("indices,scores", [([2], [0.]), ([0.5], [0.]), ([0], [[0.]])])
def test_de_targets_must_address_population_rows(indices, scores):
    unit = DifferentialPopulationUnit("de", population=np.zeros((2, 1)),
        target_indices=indices, target_scores=np.asarray(scores))
    with pytest.raises(ValueError, match="DE targets"):
        UnitBinding(DifferentialPopulationBuilder()).dump(unit)


@pytest.mark.parametrize("updates", [
    {"neighbors": np.array([[0.5], [1.]])},
    {"weights": np.ones((1, 2))},
    {"ideal": np.zeros(3)},
    {"pending_indices": [2], "pending_modes": ["global"]},
])
def test_decomposition_relations_are_validated_before_persistence(updates):
    values = dict(population=np.zeros((2, 1)), objectives=np.ones((2, 2)), violations=np.zeros(2),
        weights=np.eye(2), neighbors=np.array([[0], [1]]), ideal=np.zeros(2))
    values.update(updates)
    with pytest.raises(ValueError):
        UnitBinding(DecompositionUnitBuilder()).dump(DecompositionUnit("moead", **values))


def test_population_bootstrap_before_moead_setup_remains_restorable():
    adapter = MOEADAdapter()
    assert adapter.set_population_snapshot(np.array([[1.], [2.]]), np.array([[1.], [4.]]), np.zeros(2))
    assert adapter.weights is None
    clone = MOEADAdapter()
    clone.set_state(json.loads(json.dumps(adapter.get_state())))
    np.testing.assert_array_equal(clone.pop_X, adapter.pop_X)
    np.testing.assert_array_equal(clone.ideal, adapter.ideal)


@pytest.mark.parametrize("values", [
    {"objectives": np.zeros((1, 1))},
    {"candidate_tokens": ("orphan",)},
    {"population": np.zeros((1, 1)), "objectives": np.zeros((1, 1))},
])
def test_population_rejects_orphan_feedback_and_incomplete_evaluation(values):
    with pytest.raises(ValueError):
        UnitBinding(PopulationUnitBuilder()).dump(PopulationUnit("population", **values))
