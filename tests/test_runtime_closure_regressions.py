from __future__ import annotations

import concurrent.futures
import threading

import numpy as np
import pytest

from nsgablack.adapters import AlgorithmAdapter
from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.blank_solver import SolverBase
from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.core.control_plane import (
    BaseController,
    BudgetController,
    ControlDecision,
    EvaluationBudgetExceeded,
)
from nsgablack.core.evolution_solver import EvolutionSolver
from nsgablack.core.runtime_governance import resolve_population_snapshot
from nsgablack.plugins import Plugin
from nsgablack.utils.extension_contracts import ContractError


class _Problem(BlackBoxProblem):
    def __init__(self, *, objectives: int = 1) -> None:
        super().__init__(
            name="runtime-closure",
            dimension=1,
            bounds={"x0": (-100.0, 100.0)},
            objectives=[f"f{i}" for i in range(objectives)],
        )

    def evaluate(self, candidate):
        value = float(np.asarray(candidate, dtype=float).reshape(-1)[0])
        return np.array([value * value], dtype=float)


class _CountingSolver(SolverBase):
    def step(self) -> None:
        self.evaluate_individual(np.array([1.0], dtype=float))


def test_budget_controller_uses_evaluation_count_and_requests_stop() -> None:
    solver = _CountingSolver(_Problem())
    solver.register_controller(BudgetController(max_evaluations=1))

    result = solver.run(max_steps=5)

    assert result["status"] == "stopped"
    assert result["steps_executed"] == 1
    assert result["evaluation_count"] == 1


class _StrategyController(BaseController):
    domain = "strategy"
    slots = ("gen_end",)

    def __init__(self) -> None:
        super().__init__(name="strategy")

    def propose(self, solver, slot, context):
        del solver, context
        return ControlDecision(
            domain=self.domain,
            slot=slot,
            controller=self.name,
            payload={"strategy": "exploit"},
        )


class _StrategyAwareSolver(SolverBase):
    def __init__(self) -> None:
        super().__init__(_Problem())
        self.applied_strategy = None

    def apply_strategy_control(self, decision) -> None:
        self.applied_strategy = dict(decision.payload or {}).get("strategy")


def test_runtime_controller_applies_non_stopping_domain_handler() -> None:
    solver = _StrategyAwareSolver()
    solver.register_controller(_StrategyController())

    solver.run(max_steps=1)

    assert solver.applied_strategy == "exploit"


class _BatchProvider:
    name = "batch"
    semantic_mode = "equivalent"

    def __init__(self, *, invalid: bool = False) -> None:
        self.invalid = bool(invalid)

    def can_handle_individual(self, solver, x, context):
        del solver, x, context
        return False

    def evaluate_individual(self, solver, x, context, individual_id=None):
        del solver, x, context, individual_id
        return None

    def can_handle_population(self, solver, population, context):
        del solver, population, context
        return True

    def evaluate_population(self, solver, population, context):
        del solver, context
        count = int(np.asarray(population).shape[0])
        if self.invalid:
            return np.ones((count - 1, 1), dtype=float), np.zeros((count - 1,), dtype=float)
        return np.ones((count, 1), dtype=float), np.zeros((count,), dtype=float)


class _EvaluationHooks(Plugin):
    def __init__(self) -> None:
        super().__init__(name="evaluation-hooks")
        self.starts = 0
        self.ends = 0

    def on_evaluate_start(self, candidate, context=None):
        del candidate, context
        self.starts += 1

    def on_evaluate_end(self, candidate, feedback, context=None):
        del candidate, feedback, context
        self.ends += 1


def test_batch_provider_validates_shape_counts_hooks_and_commits_snapshot() -> None:
    solver = SolverBase(_Problem(objectives=2))
    solver.register_evaluation_provider(_BatchProvider())
    hooks = _EvaluationHooks()
    solver.add_plugin(hooks)
    population = np.array([[1.0], [2.0], [3.0]], dtype=float)

    with pytest.warns(RuntimeWarning):
        objectives, violations = solver.evaluate_population(population)

    assert objectives.shape == (3, 2)
    assert np.all(np.isinf(objectives[:, 1]))
    assert violations.shape == (3,)
    assert solver.evaluation_count == 3
    assert (hooks.starts, hooks.ends) == (3, 3)
    snapshot = solver.read_snapshot()
    assert snapshot is not None
    assert np.asarray(snapshot["population"]).shape == (3, 1)


def test_batch_provider_bad_cardinality_fails_in_strict_mode() -> None:
    solver = SolverBase(_Problem(objectives=2), plugin_strict=True)
    solver.register_evaluation_provider(_BatchProvider(invalid=True))

    with pytest.raises(ContractError, match="population size mismatch"):
        solver.evaluate_population(np.array([[1.0], [2.0]], dtype=float))


def test_evaluation_rejects_candidate_dimension_mismatch() -> None:
    solver = SolverBase(_Problem())

    with pytest.raises(ContractError, match="evaluate_individual.x"):
        solver.evaluate_individual(np.array([1.0, 2.0], dtype=float))


class _AuthoritativeAdapter(AlgorithmAdapter):
    def __init__(self) -> None:
        super().__init__(name="authoritative")
        self.population = np.empty((0, 1), dtype=float)
        self.objectives = np.empty((0, 1), dtype=float)
        self.violations = np.empty((0,), dtype=float)

    def propose(self, control, context):
        del control, context
        return [np.array([1.0]), np.array([2.0])]

    def update(self, control, candidates, feedback, context):
        del candidates, feedback, context
        value = 10.0 + float(control.generation)
        self.population = np.array([[value]], dtype=float)
        self.objectives = np.array([[value * value]], dtype=float)
        self.violations = np.array([0.0], dtype=float)

    def get_population_snapshot(self):
        return self.population, self.objectives, self.violations

    def set_population_snapshot(self, population, objectives, violations):
        self.population = np.asarray(population, dtype=float).copy()
        self.objectives = np.asarray(objectives, dtype=float).copy()
        self.violations = np.asarray(violations, dtype=float).reshape(-1).copy()
        return True


class _ContextCapturingAdapter(_AuthoritativeAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.propose_evaluation_count = -1
        self.update_evaluation_count = -1
        self.update_candidate_count = -1

    def propose(self, control, context):
        self.propose_evaluation_count = int(context["evaluation_count"])
        return super().propose(control, context)

    def update(self, control, candidates, feedback, context):
        self.update_evaluation_count = int(context["evaluation_count"])
        self.update_candidate_count = len(candidates)
        return super().update(control, candidates, feedback, context)


class _BrokenPopulationSnapshotAdapter(_AuthoritativeAdapter):
    def get_population_snapshot(self):
        raise RuntimeError("authoritative snapshot failed")


class _SingleTrajectoryAdapter(AlgorithmAdapter):
    state_recovery_level = "L1"

    def __init__(self) -> None:
        super().__init__(name="single-trajectory")
        self.current_candidate_reads = 0

    def propose(self, control, context):
        del control, context
        return [np.array([1.0])]

    def update(self, control, candidates, feedback, context):
        del control, candidates, feedback, context

    def get_current_candidates(self):
        self.current_candidate_reads += 1
        return (np.array([99.0]),)


def test_composable_step_commits_adapter_authoritative_generation_snapshot() -> None:
    solver = ComposableSolver(_Problem(), adapter=_AuthoritativeAdapter())

    solver.run(max_steps=2)

    snapshot = solver.read_snapshot()
    assert snapshot is not None
    assert float(np.asarray(snapshot["population"])[0, 0]) == 11.0
    assert float(np.asarray(solver.population)[0, 0]) == 11.0
    assert solver._snapshot_generation == 1


def test_authoritative_population_snapshot_failure_is_not_silently_masked() -> None:
    solver = ComposableSolver(
        _Problem(),
        adapter=_BrokenPopulationSnapshotAdapter(),
    )

    with pytest.raises(RuntimeError, match="authoritative snapshot failed"):
        resolve_population_snapshot(solver, prefer_adapter=True)


def test_single_trajectory_candidate_state_is_not_treated_as_population_snapshot() -> None:
    adapter = _SingleTrajectoryAdapter()
    solver = ComposableSolver(_Problem(), adapter=adapter)
    solver.population = np.array([[3.0]], dtype=float)
    solver.objectives = np.array([[9.0]], dtype=float)
    solver.constraint_violations = np.array([0.0], dtype=float)

    population, objectives, violations = resolve_population_snapshot(
        solver,
        prefer_adapter=True,
    )

    assert adapter.current_candidate_reads == 0
    np.testing.assert_allclose(population, [[3.0]])
    np.testing.assert_allclose(objectives, [[9.0]])
    np.testing.assert_allclose(violations, [0.0])


def test_composable_update_receives_post_evaluation_context() -> None:
    adapter = _ContextCapturingAdapter()
    solver = ComposableSolver(_Problem(), adapter=adapter)

    solver.run(max_steps=1)

    assert adapter.propose_evaluation_count == 0
    assert adapter.update_evaluation_count == 2


def test_composable_hard_budget_truncates_before_evaluation_and_update() -> None:
    adapter = _ContextCapturingAdapter()
    solver = ComposableSolver(_Problem(), adapter=adapter)
    solver.register_controller(BudgetController(max_evaluations=1))

    result = solver.run(max_steps=5)

    assert result["status"] == "stopped"
    assert result["steps_executed"] == 1
    assert result["evaluation_count"] == 1
    assert adapter.update_candidate_count == 1
    assert adapter.update_evaluation_count == 1
    assert solver.last_step_summary["num_proposed"] == 2
    assert solver.last_step_summary["budget_truncated"] is True


def test_direct_population_evaluation_rejects_budget_overrun_before_hooks() -> None:
    solver = SolverBase(_Problem())
    solver.register_controller(BudgetController(max_evaluations=2))
    hooks = _EvaluationHooks()
    solver.add_plugin(hooks)

    with pytest.raises(EvaluationBudgetExceeded, match="requested=3, allowed=2"):
        solver.evaluate_population(np.array([[1.0], [2.0], [3.0]], dtype=float))

    assert solver.evaluation_count == 0
    assert (hooks.starts, hooks.ends) == (0, 0)


def test_hard_budget_reservation_is_atomic_across_concurrent_calls() -> None:
    started = threading.Event()
    release = threading.Event()

    class _BlockingProblem(_Problem):
        def evaluate(self, candidate):
            started.set()
            if not release.wait(timeout=2.0):
                raise TimeoutError("test evaluation was not released")
            return super().evaluate(candidate)

    solver = SolverBase(_BlockingProblem())
    solver.register_controller(BudgetController(max_evaluations=1))

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(solver.evaluate_individual, np.array([1.0]))
        assert started.wait(timeout=1.0)
        second = executor.submit(solver.evaluate_individual, np.array([2.0]))
        with pytest.raises(EvaluationBudgetExceeded):
            second.result(timeout=1.0)
        release.set()
        first.result(timeout=1.0)

    assert solver.evaluation_count == 1
    assert solver.evaluation_budget_reserved == 0


class _ErrorHooks(Plugin):
    def __init__(self) -> None:
        super().__init__(name="error-hooks")
        self.calls = 0
        self.contexts = []

    def on_error(self, error, context=None):
        del error
        self.calls += 1
        self.contexts.append(dict(context or {}))


class _FailingProblem(_Problem):
    def evaluate(self, candidate):
        del candidate
        raise RuntimeError("evaluation failed")


class _FailingEvaluationSolver(SolverBase):
    def step(self) -> None:
        self.evaluate_population(np.array([[1.0], [2.0]], dtype=float))


def test_evaluation_error_is_dispatched_once_by_run_lifecycle() -> None:
    solver = _FailingEvaluationSolver(_FailingProblem())
    hooks = _ErrorHooks()
    solver.add_plugin(hooks)

    with pytest.raises(RuntimeError, match="evaluation failed"):
        solver.run(max_steps=1)

    assert hooks.calls == 1
    assert hooks.contexts[0]["error_phase"] == "evaluate_individual"


def test_teardown_failure_does_not_mask_primary_run_error() -> None:
    class _FailingRunAndTeardown(_FailingEvaluationSolver):
        def teardown(self) -> None:
            raise RuntimeError("teardown failed")

    solver = _FailingRunAndTeardown(_FailingProblem())

    with pytest.raises(RuntimeError, match="evaluation failed") as captured:
        solver.run(max_steps=1)

    assert getattr(captured.value, "_nsgablack_teardown_error") == {
        "type": "RuntimeError",
        "message": "teardown failed",
    }
    assert solver._teardown_error == {
        "type": "RuntimeError",
        "message": "teardown failed",
    }


def test_direct_public_evaluation_dispatches_on_error_exactly_once() -> None:
    solver = SolverBase(_FailingProblem())
    hooks = _ErrorHooks()
    solver.add_plugin(hooks)

    with pytest.raises(RuntimeError, match="evaluation failed"):
        solver.evaluate_population(np.array([[1.0], [2.0]], dtype=float))

    assert hooks.calls == 1
    assert hooks.contexts[0]["error_phase"] == "evaluate_individual"


def test_direct_public_validation_error_dispatches_on_error_exactly_once() -> None:
    solver = SolverBase(_Problem())
    hooks = _ErrorHooks()
    solver.add_plugin(hooks)

    with pytest.raises(ContractError):
        solver.evaluate_individual(np.array([1.0, 2.0], dtype=float))

    assert hooks.calls == 1
    assert hooks.contexts[0]["error_phase"] == "evaluate_individual"


class _LargeContextPlugin(Plugin):
    def __init__(self) -> None:
        super().__init__(name="large-context")

    def on_context_build(self, context):
        context["population"] = [[99.0]]
        context["objectives"] = [[1.0]]
        context["history"] = [{"large": True}]
        return context


def test_context_build_strips_and_purges_large_runtime_objects() -> None:
    solver = SolverBase(_Problem())
    solver.context_store.set("population", [[1.0]])
    solver.context_store.set("objectives", [[2.0]])
    solver.context_store.set("history", [{"old": True}])
    solver.add_plugin(_LargeContextPlugin())

    context = solver.build_context()
    persisted = solver.context_store.snapshot()

    for key in ("population", "objectives", "history"):
        assert key not in context
        assert key not in persisted


class _FakeParallelEvaluator:
    def __init__(self, *, invalid: bool = False) -> None:
        self.invalid = bool(invalid)

    def evaluate_population(self, *, population, **kwargs):
        del kwargs
        pop = np.asarray(population, dtype=float)
        count = int(pop.shape[0]) - (1 if self.invalid else 0)
        return np.square(pop[:count, :1]), np.zeros((count,), dtype=float)


def test_evolution_parallel_evaluation_closes_solver_contract() -> None:
    solver = EvolutionSolver(
        _Problem(),
        pop_size=3,
        max_generations=1,
        enable_parallel=True,
        parallel_backend="thread",
    )
    solver.parallel_evaluator = _FakeParallelEvaluator()
    hooks = _EvaluationHooks()
    solver.add_plugin(hooks)
    population = np.array([[1.0], [2.0], [3.0]], dtype=float)

    objectives, violations = solver.evaluate_population(population)

    assert objectives.shape == (3, 1)
    assert violations.shape == (3,)
    assert solver.evaluation_count == 3
    assert (hooks.starts, hooks.ends) == (3, 3)
    snapshot = solver.read_snapshot()
    assert snapshot is not None
    assert np.asarray(snapshot["objectives"]).shape == (3, 1)


def test_evolution_parallel_evaluation_rejects_bad_cardinality() -> None:
    solver = EvolutionSolver(
        _Problem(),
        pop_size=2,
        max_generations=1,
        enable_parallel=True,
        parallel_backend="thread",
        plugin_strict=True,
    )
    solver.parallel_evaluator = _FakeParallelEvaluator(invalid=True)

    with pytest.raises(ContractError, match="population size mismatch"):
        solver.evaluate_population(np.array([[1.0], [2.0]], dtype=float))


class _RunLifecycleHooks(_EvaluationHooks):
    def __init__(self) -> None:
        super().__init__()
        self.events: list[str] = []

    def on_solver_init(self, solver):
        del solver
        self.events.append("solver_init")

    def on_evaluate_start(self, candidate, context=None):
        super().on_evaluate_start(candidate, context)
        self.events.append("evaluate_start")


def test_evolution_run_counts_initialization_and_commits_derived_state() -> None:
    solver = EvolutionSolver(_Problem(), pop_size=3, max_generations=1, random_seed=7)
    hooks = _RunLifecycleHooks()
    solver.add_plugin(hooks)

    result = solver.run(return_dict=True)

    assert result["evaluation_count"] == 6
    assert hooks.events.index("solver_init") < hooks.events.index("evaluate_start")
    snapshot = solver.read_snapshot()
    assert snapshot is not None
    assert np.asarray(snapshot["population"]).shape == (3, 1)
    assert np.asarray(snapshot["pareto_objectives"]).shape[1] == 1
    assert len(snapshot["history"]) == 2


def test_evaluation_budget_stops_before_offspring_after_initialization() -> None:
    solver = EvolutionSolver(_Problem(), pop_size=3, max_generations=5, random_seed=7)
    solver.register_controller(BudgetController(max_evaluations=3))

    result = solver.run(return_dict=True)

    assert result["status"] == "stopped"
    assert result["steps_executed"] == 0
    assert result["evaluation_count"] == 3


def test_evolution_hard_budget_allows_only_remaining_offspring() -> None:
    solver = EvolutionSolver(_Problem(), pop_size=3, max_generations=5, random_seed=7)
    solver.register_controller(BudgetController(max_evaluations=5))

    result = solver.run(return_dict=True)

    assert result["status"] == "stopped"
    assert result["steps_executed"] == 1
    assert result["evaluation_count"] == 5
    assert solver.last_step_summary["num_proposed"] == 3
    assert solver.last_step_summary["num_candidates"] == 2
    assert solver.last_step_summary["budget_truncated"] is True
