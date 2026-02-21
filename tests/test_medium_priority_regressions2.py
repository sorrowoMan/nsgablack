from __future__ import annotations

import numpy as np

from nsgablack.bias.core.base import AlgorithmicBias, DomainBias
from nsgablack.bias.core.manager import DomainBiasManager, UniversalBiasManager
from nsgablack.bias.managers.adaptive_manager import AdaptiveAlgorithmicManager, OptimizationState
from nsgablack.core.adapters.moead import MOEADAdapter, MOEADConfig
from nsgablack.utils.context.context_keys import KEY_MOEAD_NEIGHBOR_MODE, KEY_MOEAD_SUBPROBLEM
from nsgablack.utils.parallel.evaluator import ParallelEvaluator
from nsgablack.utils.performance.memory_manager import OptimizationMemoryOptimizer


class _AlgoBias(AlgorithmicBias):
    def __init__(self, name: str = "diversity_dummy") -> None:
        super().__init__(name=name, weight=1.0)

    def compute(self, x: np.ndarray, context) -> float:  # type: ignore[override]
        _ = x, context
        return 0.0


class _DomainBias(DomainBias):
    def __init__(self, value: float = 1.0) -> None:
        super().__init__(name="domain_dummy", weight=1.0)
        self._value = float(value)

    def compute(self, x: np.ndarray, context) -> float:  # type: ignore[override]
        _ = x, context
        return self._value


class _Ctx:
    def __init__(self, generation: int = 0) -> None:
        self.generation = int(generation)
        self.constraint_violation = False

    def set_constraint_violation(self, is_violating: bool) -> None:
        self.constraint_violation = bool(is_violating)


def test_moead_update_uses_per_candidate_modes_and_projection_is_batch() -> None:
    adapter = MOEADAdapter(MOEADConfig(population_size=3, nr=10))
    adapter._n = 3
    adapter._m = 2
    adapter.pop_X = np.array([[0.0], [1.0], [2.0]], dtype=float)
    adapter.pop_F = np.array([[5.0, 5.0], [6.0, 6.0], [7.0, 7.0]], dtype=float)
    adapter.pop_V = np.zeros(3, dtype=float)
    adapter.weights = np.array([[0.5, 0.5], [0.5, 0.5], [0.5, 0.5]], dtype=float)
    adapter.neighbors = np.array([[0, 1], [1, 2], [0, 2]], dtype=int)
    adapter.ideal = np.array([0.0, 0.0], dtype=float)
    adapter._pending_indices = [0, 1]
    adapter._pending_modes = ["global", "neighborhood"]

    candidates = np.array([[10.0], [11.0]], dtype=float)
    objectives = np.array([[1.0, 1.0], [9.0, 9.0]], dtype=float)
    violations = np.zeros(2, dtype=float)
    adapter.update(solver=None, candidates=candidates, objectives=objectives, violations=violations, context={})

    # First candidate must run in global mode and replace all three entries.
    assert np.allclose(adapter.pop_F, np.array([[1.0, 1.0], [1.0, 1.0], [1.0, 1.0]], dtype=float))

    projection = adapter.get_runtime_context_projection(None)
    assert KEY_MOEAD_SUBPROBLEM in projection
    assert KEY_MOEAD_NEIGHBOR_MODE in projection
    assert len(np.asarray(projection[KEY_MOEAD_SUBPROBLEM]).reshape(-1)) == 2
    assert list(projection[KEY_MOEAD_NEIGHBOR_MODE]) == ["global", "neighborhood"]


def test_adaptive_manager_caps_exploration_weights() -> None:
    manager = AdaptiveAlgorithmicManager(window_size=5, adaptation_interval=1)
    manager.add_bias(_AlgoBias(), initial_weight=0.98)
    state = OptimizationState(
        generation=1,
        diversity=0.1,
        convergence_rate=0.0,
        improvement_rate=0.0,
        population_density=0.0,
        exploration_ratio=0.1,
        exploitation_ratio=0.9,
    )
    manager._balance_exploration_exploitation(state)
    assert manager.biases["diversity_dummy"].weight <= 1.0


def test_adaptive_manager_diversity_large_population_uses_sampling_path() -> None:
    manager = AdaptiveAlgorithmicManager(window_size=5, adaptation_interval=1)
    manager.max_diversity_pairs = 10
    population = [np.array([float(i)], dtype=float) for i in range(200)]
    diversity = manager._compute_diversity(population)
    assert np.isfinite(diversity)
    assert diversity > 0.0


def test_memory_optimizer_keeps_history_in_chronological_order() -> None:
    class _Solver:
        def __init__(self) -> None:
            self.history = [(i, [float(i)]) for i in range(100)]

    solver = _Solver()
    optimizer = OptimizationMemoryOptimizer(solver)
    optimizer.optimize_history_storage(max_generations=20)
    generations = [int(item[0]) for item in solver.history]
    assert generations == sorted(generations)


def test_domain_bias_violation_rate_uses_real_evaluation_count() -> None:
    mgr = DomainBiasManager()
    mgr.add_domain_bias(_DomainBias(value=1.0))
    ctx = _Ctx()
    for i in range(20):
        ctx.generation = i
        mgr.compute_total_bias(np.array([0.0], dtype=float), ctx)
    assert np.isclose(mgr.compute_constraint_violation_rate(), 1.0)


def test_universal_bias_history_is_bounded() -> None:
    mgr = UniversalBiasManager()
    mgr.add_algorithmic_bias(_AlgoBias(name="algo"))
    mgr.add_domain_bias(_DomainBias(value=0.0))
    ctx = _Ctx()
    for i in range(6000):
        ctx.generation = i
        mgr.compute_total_bias(np.array([0.0], dtype=float), ctx)
    assert len(mgr.bias_history) == 5000


def test_parallel_evaluator_non_balanced_path_does_not_enter_executor_context() -> None:
    class _DummyExecutor:
        def __init__(self) -> None:
            self.entered = 0

        def __enter__(self):  # pragma: no cover - should not be called
            self.entered += 1
            raise AssertionError("should not use context-manager path")

        def __exit__(self, exc_type, exc, tb):  # pragma: no cover - should not be called
            _ = exc_type, exc, tb
            return False

        def map(self, fn, tasks, timeout=None):
            _ = timeout
            for task in tasks:
                yield fn(task)

    evaluator = ParallelEvaluator(backend="thread", enable_load_balancing=False, max_workers=2)
    dummy = _DummyExecutor()
    evaluator._create_executor = lambda: dummy  # type: ignore[assignment]
    evaluator._evaluate_individual_task = lambda task: (task[1], np.array([0.0]), 0.0, None)  # type: ignore[assignment]

    out = evaluator._evaluate_with_executor([("x0", 0), ("x1", 1)])
    assert len(out) == 2
    assert dummy.entered == 0
