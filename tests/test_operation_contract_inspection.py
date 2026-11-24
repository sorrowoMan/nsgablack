"""Operation declarations are inspected without running user components."""
from __future__ import annotations

import pytest

from nsgablack.adapters import CompositeAdapter, FixedCandidateAdapter, NSGA2Adapter, RoleAdapter, VNSAdapter
from nsgablack.adapters.operator_binding import OperatorBinding
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.units import UnitFeature, UnitInputSpec
from nsgablack.utils.extension_contracts import inspect_adapter_operator_bindings
from nsgablack.utils.runtime_contracts import inspect_runtime_contracts


METHODS = {"initializer": "initialize", "mutator": "mutate", "selector": "select",
           "parent_selector": "select", "repair": "repair", "change": "change",
           "pool_maintenance": "maintain"}


class Problem(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, objectives=["min"], bounds=[(-2., 2.)])
        self.calls = 0

    def evaluate(self, candidate):
        self.calls += 1
        return [float(candidate[0]) ** 2]


class StatelessOperations:
    stateless = True

    def checkpoint_identity(self):
        return {"schema": "inspection-only-operations/v1"}

    def initialize(self, problem, context=None):
        pytest.fail("inspector executed initialize")

    def mutate(self, candidate, context=None):
        pytest.fail("inspector executed mutate")

    def select(self, request, *, rng, pool=None):
        pytest.fail("inspector executed select")

    def repair(self, unit, evidence, context):
        pytest.fail("inspector executed repair")

    def change(self, request, *, rng):
        pytest.fail("inspector executed change")

    def maintain(self, request, *, rng):
        pytest.fail("inspector executed pool maintenance")

    def validate(self, unit, evidence, context):
        pytest.fail("inspector executed validate")


class UnitSelector(StatelessOperations):
    unit_inputs = UnitInputSpec(fields=("population",))

    def select(self, request, *, rng, unit):
        pytest.fail("inspector executed a Unit-aware selector")


def bound(role, component=None):
    component = StatelessOperations() if component is None else component
    adapter = NSGA2Adapter(population_size=2, offspring_size=1)
    adapter.set_operation(role, component)
    return adapter, component


def invalid(issues):
    return any(code == "operator-binding-contract-invalid" for code, _ in issues)


@pytest.mark.parametrize("role", METHODS)
def test_valid_signatures_do_not_run_operator_or_identity_hooks(role):
    adapter, component = bound(role)
    component.checkpoint_identity = lambda: pytest.fail("inspector recaptured identity")
    component.get_state = lambda: pytest.fail("inspector recaptured state")
    assert inspect_adapter_operator_bindings(adapter) == ()


@pytest.mark.parametrize("role", METHODS)
def test_invalid_signature_is_reported_without_invocation(role):
    adapter, component = bound(role)
    setattr(component, METHODS[role], lambda: pytest.fail("invalid signature was invoked"))
    assert invalid(inspect_adapter_operator_bindings(adapter))


@pytest.mark.parametrize("role", ("initializer", "mutator"))
@pytest.mark.parametrize("shape", ("positional_context", "keyword_context", "without_context"))
def test_supported_optional_context_call_shapes_are_recognized(role, shape):
    adapter, component = bound(role)
    if shape == "positional_context":
        function = lambda value, context, /: pytest.fail("executed component")
    elif shape == "keyword_context":
        function = lambda value, *, context: pytest.fail("executed component")
    else:
        function = lambda value: pytest.fail("executed component")
    setattr(component, METHODS[role], function)
    assert inspect_adapter_operator_bindings(adapter) == ()


@pytest.mark.parametrize("declaration", (None, [], {"unknown": "select"},
    {"mutator": ""}, {"selector": "mutate"}, {1: "initialize"}))
def test_invalid_class_operation_declarations_have_a_diagnostic(declaration):
    adapter = NSGA2Adapter(population_size=2)
    adapter.operation_methods = declaration
    assert invalid(inspect_adapter_operator_bindings(adapter))


def test_unbound_delegated_wrappers_do_not_need_leaf_operation_declarations():
    adapter = CompositeAdapter([RoleAdapter("role", FixedCandidateAdapter())])
    assert inspect_adapter_operator_bindings(adapter) == ()


def test_manually_advertised_unsupported_binding_is_rejected():
    adapter = FixedCandidateAdapter()
    adapter._operation_bindings = {"mutator": OperatorBinding(StatelessOperations(), method="mutate")}
    assert invalid(inspect_adapter_operator_bindings(adapter))


def test_binding_invocation_method_must_match_the_consumer_declaration():
    adapter = NSGA2Adapter(population_size=2)
    adapter._operation_bindings = {"mutator": OperatorBinding(StatelessOperations(), method="initialize")}
    issues = inspect_adapter_operator_bindings(adapter)
    assert invalid(issues) and "binding method" in issues[0][1]


def test_direct_unit_repair_drift_is_detected_against_the_checkpoint_owner():
    adapter, first = bound("repair")
    adapter.unit_repair = StatelessOperations()
    issues = inspect_adapter_operator_bindings(adapter)
    assert invalid(issues) and "active UnitRepair" in issues[0][1]
    assert adapter.get_bound_operator("repair") is first


def test_legacy_repair_rebind_releases_the_previous_direct_binding():
    adapter, _ = bound("repair")
    adapter.set_unit_repair(StatelessOperations())
    assert adapter.get_bound_operator("repair") is None
    assert inspect_adapter_operator_bindings(adapter) == ()


@pytest.mark.parametrize("role", ("initializer", "parent_selector", "change", "pool_maintenance"))
def test_unimplemented_implicit_unit_inputs_are_rejected(role):
    adapter, component = bound(role)
    component.unit_inputs = UnitInputSpec(fields=("population",))
    assert invalid(inspect_adapter_operator_bindings(adapter))


def test_unit_aware_selector_signature_is_checked_without_running_it():
    adapter, component = bound("selector", UnitSelector())
    assert inspect_adapter_operator_bindings(adapter) == ()
    component.select = lambda request, *, rng: pytest.fail("selector was executed")
    assert invalid(inspect_adapter_operator_bindings(adapter))


def test_unit_selector_dependency_inspection_does_not_compute_features():
    component = UnitSelector()
    component.unit_inputs = UnitInputSpec(features=(UnitFeature(
        "selection.doctor_must_not_compute", ("population",),
        lambda _: pytest.fail("Doctor calculated a selector feature")),))
    adapter, _ = bound("selector", component)
    solver = ComposableSolver(Problem(), adapter=adapter)
    assert not any(code == "unit-operator-contract-invalid" for code, _ in inspect_runtime_contracts(solver))
    component.unit_inputs = UnitInputSpec(fields=("nonexistent_selector_dependency",))
    assert any(code == "unit-operator-contract-invalid" and ".selector" in message
               for code, message in inspect_runtime_contracts(solver))
    assert solver.problem.calls == 0


def test_fresh_vns_selector_is_checked_without_constructing_a_lazy_unit():
    selector = UnitSelector()
    selector.unit_inputs = UnitInputSpec(fields=("candidate",))
    adapter = VNSAdapter(selector=selector)
    assert adapter.get_operator_unit() is None
    solver = ComposableSolver(Problem(), adapter=adapter)
    assert not any(code == "unit-operator-contract-invalid" for code, _ in inspect_runtime_contracts(solver))
    assert adapter.get_operator_unit() is None
    assert solver.problem.calls == 0


def test_bad_unit_selector_spec_gets_a_contract_diagnostic():
    adapter, component = bound("selector")
    component.unit_inputs = {"fields": ("population",)}
    assert invalid(inspect_adapter_operator_bindings(adapter))


def test_invalid_operation_is_rejected_by_real_solver_assembly_before_evaluation():
    adapter, component = bound("initializer")
    component.initialize = lambda: pytest.fail("assembly executed initializer")
    problem = Problem()
    with pytest.raises(ValueError, match="operator-binding-contract-invalid"):
        ComposableSolver(problem, adapter=adapter)
    assert problem.calls == 0


def test_unit_mutation_declaration_still_uses_its_strict_signature():
    adapter, component = bound("mutator")
    component.unit_inputs = UnitInputSpec(fields=("population",))
    assert invalid(inspect_adapter_operator_bindings(adapter))
    component.mutate = lambda candidate, context, *, unit: pytest.fail("executed mutator")
    assert inspect_adapter_operator_bindings(adapter) == ()
