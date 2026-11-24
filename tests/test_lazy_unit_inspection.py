"""Inspection and preference assembly must not activate an Adapter's Unit."""
import numpy as np
import pytest

from nsgablack.adapters import NSGA2Adapter
from nsgablack.bias import (OptimizationContext, PopulationDiversityPreference,
                           PreferenceContractError, UnitPreferenceBias)
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.representation import (JointRepairPolicy, PopulationUnitBuilder,
                                     RepresentationPipeline)
from nsgablack.units import UnitBinding, UnitFeature, UnitInputSpec
from nsgablack.utils.runtime_contracts import inspect_runtime_contracts


class Problem(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, objectives=["min"], bounds=[(-2., 2.)])

    def evaluate(self, candidate):
        pytest.fail("inspection evaluated a candidate")


def inactive_adapter(**kwargs):
    calls = []
    builder = PopulationUnitBuilder()

    def build(request, context):
        calls.append(request)
        return builder.build(request, context)

    binding = UnitBinding(builder, runner=build, name="inspection-counting-builder")
    return NSGA2Adapter(unit_binding=binding, **kwargs), calls


def test_contract_snapshot_and_readers_leave_unit_absent():
    adapter, calls = inactive_adapter()
    solver = ComposableSolver(Problem(), adapter=adapter)
    assert inspect_runtime_contracts(solver) == ()
    assert adapter.get_operator_unit() is None
    assert adapter.preference_view(owner_path=("search",)) is None
    assert adapter.get_state()["algorithm_unit"] is None
    assert adapter.snapshot_step_state()["algorithm_unit"] is None
    assert adapter.get_runtime_context_projection(solver) == {}
    assert adapter.get_population_snapshot()[0].size == 0
    assert adapter.get_population_partitions() == ()
    assert adapter.algorithm_unit is None and calls == []


def test_feature_declarations_are_checked_without_unit_or_computation():
    adapter, calls = inactive_adapter()
    solver = ComposableSolver(Problem(), adapter=adapter)
    adapter.unit_features = (UnitFeature("missing", ("unknown_field",),
        lambda _: pytest.fail("inspection computed a feature")),)
    issues = inspect_runtime_contracts(solver)
    assert any(code == "unit-feature-contract-invalid" for code, _ in issues)
    assert adapter.algorithm_unit is None and calls == []


@pytest.mark.parametrize("role", ("mutator", "selector"))
def test_operator_field_declarations_are_checked_without_unit(role):
    class Operator:
        stateless = True
        unit_inputs = UnitInputSpec(fields=("unknown_field",))

        def checkpoint_identity(self):
            return {"schema": "inspection-only-unit-operation/v1"}

        def mutate(self, candidate, context, *, unit):
            pytest.fail("inspection mutated a candidate")

        def select(self, request, *, rng, unit):
            pytest.fail("inspection selected a candidate")

    adapter, calls = inactive_adapter()
    solver = ComposableSolver(Problem(), adapter=adapter)
    adapter.set_operation(role, Operator())
    assert any(code == "unit-operator-contract-invalid" for code, _ in inspect_runtime_contracts(solver))
    assert adapter.algorithm_unit is None and calls == []


def test_unit_repair_can_bind_before_structure_exists():
    class ProblemRepair:
        def repair(self, candidate, context):
            pytest.fail("inspection repaired a candidate")

        def validate(self, candidate, context):
            pytest.fail("inspection validated a candidate")

    class UnitRepair:
        def repair(self, unit, evidence, context):
            pytest.fail("inspection repaired a Unit")

        def validate(self, unit, evidence, context):
            pytest.fail("inspection validated a Unit")

    adapter, calls = inactive_adapter()
    adapter.set_unit_repair(UnitRepair())
    solver = ComposableSolver(Problem(), adapter=adapter,
        representation_pipeline=RepresentationPipeline(repair=ProblemRepair()),
        joint_repair_policy=JointRepairPolicy())
    assert inspect_runtime_contracts(solver) == ()
    adapter.admission_unit_fields = ("unknown_field",)
    assert any(code == "joint-repair-contract-invalid" for code, _ in inspect_runtime_contracts(solver))
    assert adapter.algorithm_unit is None and calls == []


def test_preference_binding_is_lazy_and_actual_consumption_requires_activation():
    adapter, calls = inactive_adapter()
    bias = UnitPreferenceBias.from_adapter(PopulationDiversityPreference(), adapter,
                                          owner_path=("search",))
    assert bias.get_state()["binding"]["unit_id"] == adapter.get_unit_id()
    context = OptimizationContext(0, np.array([0.]))
    with pytest.raises(PreferenceContractError, match="active Unit"):
        bias.compute(np.array([0.]), context)
    assert adapter.algorithm_unit is None and calls == []

    scoped = UnitPreferenceBias.from_adapter(PopulationDiversityPreference(), adapter,
        owner_path=("search",), apply_to_paths=(("other",),))
    assert scoped.compute(np.array([0.]), context) == 0.
    assert adapter.algorithm_unit is None and calls == []
    adapter.ensure_unit()
    assert bias.compute(np.array([0.]), context) == 0.
    assert len(calls) == 1
