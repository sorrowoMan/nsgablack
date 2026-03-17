from __future__ import annotations

import numpy as np
import pytest

from nsgablack.core.acceleration import AccelerationRegistry, NoopAccelerationBackend
from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.control_plane import BaseController, ControlDecision, RuntimeController
from nsgablack.core.evaluation_runtime import EvaluationMediator, EvaluationMediatorConfig
from nsgablack.core.evolution_solver import EvolutionSolver
from nsgablack.core.nested_solver import InnerRuntimeEvaluator


class _Problem(BlackBoxProblem):
    def __init__(self) -> None:
        super().__init__(
            name="p",
            dimension=2,
            bounds={"x0": [-1.0, 1.0], "x1": [-1.0, 1.0]},
            objectives=["f1"],
        )

    def evaluate(self, x):
        arr = np.asarray(x, dtype=float).reshape(-1)
        return np.array([float(np.sum(arr * arr))], dtype=float)

    def evaluate_constraints(self, x):
        _ = x
        return np.zeros(0, dtype=float)


class _StopCtl(BaseController):
    domain = "stopping"
    slots = ("gen_end",)

    def __init__(self, name: str = "stop") -> None:
        super().__init__(name=name, priority=0)

    def propose(self, solver, slot: str, context):
        _ = solver
        _ = context
        return ControlDecision(
            domain="stopping",
            slot=slot,
            controller=self.name,
            payload={"stop": True},
            reason="unit-test",
        )


class _ExactProvider:
    name = "exact-provider"
    semantic_mode = "equivalent"

    def can_handle_individual(self, solver, x, context):
        _ = solver
        _ = x
        _ = context
        return True

    def evaluate_individual(self, solver, x, context, individual_id=None):
        _ = solver
        _ = context
        _ = individual_id
        return np.array([123.0], dtype=float), 0.0

    def can_handle_population(self, solver, population, context):
        _ = solver
        _ = population
        _ = context
        return False

    def evaluate_population(self, solver, population, context):
        _ = solver
        _ = population
        _ = context
        return None


class _ApproxProvider(_ExactProvider):
    name = "approx-provider"
    semantic_mode = "approximate"

    def evaluate_individual(self, solver, x, context, individual_id=None):
        _ = solver
        _ = x
        _ = context
        _ = individual_id
        return np.array([999.0], dtype=float), 0.0


class _InnerSolver:
    accepted_parent_contracts = ("outer.v1",)

    def run(self, return_dict: bool = False):
        _ = return_dict
        return {
            "status": "ok",
            "objective": np.array([7.0], dtype=float),
            "violation": 0.0,
            "cost_units": 2.0,
        }


def test_acceleration_registry_default_backend():
    registry = AccelerationRegistry()
    backend = registry.get(scope="evaluation", backend="missing")
    assert isinstance(backend, NoopAccelerationBackend)


def test_runtime_controller_domain_owner_conflict():
    ctl = RuntimeController()
    ctl.register_controller(_StopCtl(name="a"))
    with pytest.raises(ValueError):
        ctl.register_controller(_StopCtl(name="b"))


def test_evaluation_mediator_disallow_approximate():
    solver = EvolutionSolver(_Problem(), pop_size=4, max_generations=2)
    solver.evaluation_mediator = EvaluationMediator(
        EvaluationMediatorConfig(allow_approximate=False, strict_conflict=True)
    )
    solver.register_evaluation_provider(_ApproxProvider())
    obj, vio = solver.evaluate_individual(np.array([0.1, 0.1], dtype=float), individual_id=0)
    assert float(obj[0]) != 999.0
    assert float(vio) == 0.0


def test_solver_uses_l4_provider_instead_of_plugin_short_circuit():
    solver = EvolutionSolver(_Problem(), pop_size=4, max_generations=2)
    solver.register_evaluation_provider(_ExactProvider())
    obj, vio = solver.evaluate_individual(np.array([0.2, 0.3], dtype=float), individual_id=0)
    assert float(obj[0]) == 123.0
    assert float(vio) == 0.0


def test_problem_inner_runtime_evaluator_contract_and_budget():
    solver = EvolutionSolver(_Problem(), pop_size=4, max_generations=2)
    evaluator = InnerRuntimeEvaluator(
        solver_factory=lambda outer, req: _InnerSolver(),
        parent_contract="outer.v1",
        default_budget_units=1.0,
        max_total_budget_units=10.0,
    )
    solver.problem.inner_runtime_evaluator = evaluator
    obj, vio = solver.evaluate_individual(np.array([0.0, 0.0], dtype=float), individual_id=0)
    assert float(obj[0]) == 7.0
    assert float(vio) == 0.0
    assert float(evaluator.stats["budget_spent"]) == 2.0
