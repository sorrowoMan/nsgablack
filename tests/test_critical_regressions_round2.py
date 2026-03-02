from __future__ import annotations

import numpy as np

from nsgablack.bias.bias_module import BiasModule
from nsgablack.bias.managers.adaptive_manager import AdaptiveAlgorithmicManager
from nsgablack.bias.managers.analytics import BiasEffectivenessMetrics
from nsgablack.bias.managers.meta_learning_selector import MetaLearningBiasSelector, ProblemFeatures
from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.evolution_solver import EvolutionSolver
from nsgablack.utils.performance.fast_non_dominated_sort import FastNonDominatedSort
from nsgablack.utils.performance.memory_manager import OptimizationMemoryOptimizer


class _ToyMOProblem(BlackBoxProblem):
    def __init__(self) -> None:
        super().__init__(name="toy-moo", dimension=2, objectives=["f1", "f2"])

    def evaluate(self, x):
        arr = np.asarray(x, dtype=float)
        return np.array([float(arr[0] ** 2), float((arr[1] - 1.0) ** 2)], dtype=float)


def test_environmental_selection_uses_full_front_ranking() -> None:
    solver = EvolutionSolver(_ToyMOProblem())
    solver.pop_size = 5

    combined_pop = np.array(
        [
            [0.0, 0.0],  # id 0 front-0
            [1.0, 1.0],  # id 1 front-0
            [2.0, 2.0],  # id 2 front-0
            [3.0, 3.0],  # id 3 front-0
            [4.0, 4.0],  # id 4 (rank-2, intentionally placed before rank-1)
            [5.0, 5.0],  # id 5 (rank-1)
        ],
        dtype=float,
    )
    combined_obj = np.array(
        [
            [0.0, 3.0],
            [1.0, 2.0],
            [2.0, 1.0],
            [3.0, 0.0],
            [4.0, 4.0],   # worse than id 5
            [2.5, 2.5],   # dominates id 4
        ],
        dtype=float,
    )
    combined_violations = np.zeros((6,), dtype=float)

    solver.environmental_selection(combined_pop, combined_obj, combined_violations)

    selected_ids = {int(v) for v in solver.population[:, 0].tolist()}
    assert 5 in selected_ids
    assert 4 not in selected_ids


def test_crowding_distance_marks_true_boundaries() -> None:
    objectives = np.array(
        [
            [0.0, 10.0],  # boundary on obj0(min) and obj1(max)
            [5.0, 0.0],   # boundary on obj1(min)
            [10.0, 5.0],  # boundary on obj0(max)
            [6.0, 6.0],   # interior
        ],
        dtype=float,
    )
    front = [0, 1, 2, 3]
    dist = FastNonDominatedSort.calculate_crowding_distance(objectives, front)
    assert np.isinf(dist[0])
    assert np.isinf(dist[1])
    assert np.isinf(dist[2])
    assert np.isfinite(dist[3])


def test_adaptive_manager_diversity_and_improvement_are_non_degenerate() -> None:
    mgr = AdaptiveAlgorithmicManager(window_size=8, adaptation_interval=2)

    diversity = mgr._compute_diversity(
        [np.array([0.0, 0.0]), np.array([3.0, 0.0]), np.array([0.0, 4.0])]
    )
    assert np.isclose(diversity, 4.0)

    first = mgr._compute_improvement_rate([5.0, 6.0, 7.0])
    second = mgr._compute_improvement_rate([3.0, 4.0, 5.0])
    assert np.isclose(first, 0.0)
    assert second > 0.0


def test_memory_optimizer_report_does_not_raise_on_cache_recommendation() -> None:
    class _DummySolver:
        history = []
        population = np.zeros((2, 2), dtype=float)
        objectives = np.zeros((2, 1), dtype=float)
        temp_data = {}

    report = OptimizationMemoryOptimizer(_DummySolver()).get_optimization_report()
    assert "recommendations" in report
    assert isinstance(report["recommendations"], list)


def test_meta_learning_selector_handles_dict_scores_and_aligned_training_data(tmp_path) -> None:
    selector = MetaLearningBiasSelector(model_save_path=str(tmp_path / "meta_model"))

    def _features(pid: str) -> ProblemFeatures:
        return ProblemFeatures(
            problem_id=pid,
            problem_type="test",
            dimension=4,
            num_objectives=2,
            constraint_count=0,
            multimodality=0.2,
            separability=0.8,
            ruggedness=0.3,
            landscape_noise=0.0,
            search_space_size=100.0,
            constraint_density=0.0,
            feasible_region_ratio=1.0,
            evaluation_cost=1.0,
            max_evaluations=1000,
        )

    selector.problem_database = [{"features": _features("p1")}, {"features": _features("p2")}]
    metrics = BiasEffectivenessMetrics(
        bias_name="b",
        bias_type="algorithmic",
        convergence_improvement=5.0,
        solution_quality_boost=3.0,
        diversity_score=0.2,
    )

    selector._get_best_bias_metrics_for_problem = lambda pid: metrics if pid == "p2" else None
    x_scaled, y_dict = selector._prepare_training_data()
    assert x_scaled is not None
    assert x_scaled.shape[0] == 1
    assert all(arr.shape[0] == 1 for arr in y_dict.values())

    weights = selector._compute_bias_weights(
        [("bias_a", {"overall": 2.0}), ("bias_b", {"overall": 1.0})]
    )
    assert weights["bias_a"] > weights["bias_b"]


def test_bias_module_clear_resets_context_cache() -> None:
    mod = BiasModule()
    mod._context_cache = object()
    mod.clear()
    assert mod._context_cache is None
