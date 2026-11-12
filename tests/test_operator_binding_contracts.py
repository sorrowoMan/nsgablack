"""Direct operator ownership is checked by assembly and the shared Doctor path."""
from types import SimpleNamespace

import numpy as np
import pytest

from nsgablack.adapters import AlgorithmAdapter, CompositeAdapter, NSGA2Adapter, RoleAdapter
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.representation import RepresentationPipeline
from nsgablack.units import UnitFeature, UnitInputSpec
from nsgablack.utils.extension_contracts import inspect_adapter_operator_bindings
from nsgablack.utils.runtime_contracts import inspect_runtime_contracts


class Problem(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, objectives=["minimize"], bounds=[(-1.0, 1.0)])
        self.calls = 0

    def evaluate(self, candidate):
        self.calls += 1
        return [float(candidate[0]) ** 2]


class StatefulOperator:
    stateless = False

    def __init__(self):
        self.calls = 0

    def checkpoint_identity(self):
        return {"name": "test-stateful-operator", "version": 1}

    def get_state(self):
        return {"calls": self.calls}

    def set_state(self, state):
        self.calls = int(state["calls"])

    def mutate(self, candidate, context=None):
        self.calls += 1
        return np.asarray(candidate).copy()

    def select(self, request, *, pool, rng):
        self.calls += 1
        return (request.population_refs[0],) * request.count


class StatelessMutation:
    stateless = True

    def checkpoint_identity(self):
        return {"name": "test-stateless-mutation", "version": 1}

    def mutate(self, candidate, context=None):
        return np.asarray(candidate).copy()


class UnitMutation(StatelessMutation):
    unit_inputs = UnitInputSpec(fields=("population",))

    def mutate(self, candidate, context, *, unit):
        return np.asarray(candidate).copy()


def bound_adapter(name, component):
    adapter = NSGA2Adapter(name=name, population_size=2, offspring_size=1)
    adapter.set_mutator(component)
    return adapter


def test_constructor_rejects_stateful_operator_owned_by_two_adapters():
    shared = StatefulOperator()
    adapter = CompositeAdapter([bound_adapter("left", shared), bound_adapter("right", shared)])
    problem = Problem()
    with pytest.raises(ValueError, match="operator-binding-owner-conflict"):
        ComposableSolver(problem, adapter=adapter)
    assert problem.calls == shared.calls == 0


def test_set_adapter_rejects_new_shared_state_without_replacing_existing_adapter():
    previous = bound_adapter("previous", StatefulOperator())
    solver = ComposableSolver(Problem(), adapter=previous)
    shared = StatefulOperator()
    replacement = CompositeAdapter([bound_adapter("left", shared), bound_adapter("right", shared)])
    with pytest.raises(ValueError, match="operator-binding-owner-conflict"):
        solver.set_adapter(replacement)
    assert solver.adapter is previous


def test_two_local_bindings_cannot_checkpoint_the_same_stateful_component():
    shared = StatefulOperator()
    adapter = bound_adapter("search", shared)
    adapter.set_parent_selector(shared)
    with pytest.raises(ValueError, match="operator-binding-owner-conflict"):
        ComposableSolver(Problem(), adapter=adapter)


def test_stateless_reuse_through_transparent_wrappers_has_no_duplicate_owner():
    shared = StatelessMutation()
    adapter = CompositeAdapter([
        RoleAdapter("left", bound_adapter("left_search", shared)),
        RoleAdapter("right", bound_adapter("right_search", shared)),
    ])
    solver = ComposableSolver(Problem(), adapter=adapter)
    assert inspect_adapter_operator_bindings(adapter) == ()
    assert not any(code.startswith("operator-binding-") for code, _ in inspect_runtime_contracts(solver))


@pytest.mark.parametrize("slot", ["mutator", "mutation_operators", "repair", "initializers"])
def test_stateful_direct_and_pipeline_ownership_conflict_at_assembly(slot):
    class MultiRoleOperator(StatefulOperator):
        def repair(self, candidate, context=None):
            self.calls += 1
            return np.asarray(candidate).copy()

        def init(self, context=None):
            self.calls += 1
            return np.zeros(1)

    shared = MultiRoleOperator()
    component = ({"other": shared} if slot == "mutation_operators"
                 else [(shared, 1.0)] if slot == "initializers" else shared)
    pipeline = RepresentationPipeline(**{slot: component})
    with pytest.raises(ValueError, match="operator-binding-owner-conflict"):
        ComposableSolver(Problem(), adapter=bound_adapter("search", shared),
                         representation_pipeline=pipeline)
    assert shared.calls == 0


def test_setup_rechecks_pipeline_ownership_after_post_construction_binding():
    shared = StatefulOperator()
    adapter = NSGA2Adapter(population_size=2, offspring_size=1)
    solver = ComposableSolver(Problem(), adapter=adapter,
                             representation_pipeline=RepresentationPipeline(mutator=shared))
    adapter.set_mutator(shared)
    assert any(code == "operator-binding-owner-conflict"
               for code, _ in inspect_runtime_contracts(solver))
    with pytest.raises(ValueError, match="operator-binding-owner-conflict"):
        solver.setup()
    assert solver.problem.calls == shared.calls == 0


def test_setup_checks_operator_owners_in_newly_materialized_children():
    shared = StatefulOperator()

    class DeferredChildren(AlgorithmAdapter):
        def __init__(self):
            super().__init__("deferred")
            self.children = ()

        def setup(self, control):
            self.children = (bound_adapter("left", shared), bound_adapter("right", shared))

        def step_transaction_children(self):
            return self.children

        def propose(self, control, context):
            return []

        def update(self, control, candidates, feedback, context):
            pass

    solver = ComposableSolver(Problem(), adapter=DeferredChildren())
    with pytest.raises(ValueError, match="operator-binding-owner-conflict"):
        solver.setup()
    assert solver.problem.calls == 0


def test_direct_mutator_is_valid_without_a_default_named_pipeline_choice():
    feature = UnitFeature("doctor_must_not_compute", ("population",),
                          lambda _: pytest.fail("Doctor executed a Unit feature"))
    direct = UnitMutation()
    direct.unit_inputs = UnitInputSpec(features=(feature,))
    solver = ComposableSolver(Problem(), adapter=bound_adapter("search", direct),
        representation_pipeline=RepresentationPipeline(mutation_operators={"other": StatelessMutation()}))
    assert not any(code == "unit-operator-contract-invalid"
                   for code, _ in inspect_runtime_contracts(solver))
    direct.unit_inputs = UnitInputSpec(fields=("missing_field",))
    assert any(code == "unit-operator-contract-invalid"
               for code, _ in inspect_runtime_contracts(solver))


def test_ownership_inspection_does_not_capture_user_state_again():
    component = StatefulOperator()
    adapter = bound_adapter("search", component)
    component.get_state = lambda: pytest.fail("ownership inspection captured state")
    assert inspect_adapter_operator_bindings(adapter) == ()


@pytest.mark.parametrize("bindings", [[], {"mutator": SimpleNamespace(component=object(), stateless=True)}])
def test_invalid_local_binding_declaration_has_a_diagnostic(bindings):
    adapter = NSGA2Adapter(population_size=2, offspring_size=1)
    adapter.get_local_operator_bindings = lambda: bindings
    assert any(code == "operator-binding-contract-invalid"
               for code, _ in inspect_adapter_operator_bindings(adapter))
