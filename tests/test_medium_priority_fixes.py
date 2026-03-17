from __future__ import annotations

import numpy as np

from nsgablack.adapters.moead import MOEADAdapter, MOEADConfig
from nsgablack.adapters.vns import VNSAdapter, VNSConfig
from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.evolution_solver import EvolutionSolver
from nsgablack.plugins.runtime.pareto_archive import ParetoArchiveConfig, ParetoArchivePlugin


def test_pareto_archive_truncates_with_crowding() -> None:
    plugin = ParetoArchivePlugin(config=ParetoArchiveConfig(keep_infeasible=True, max_size=2))
    X = np.array([[0.0], [1.0], [2.0]], dtype=float)
    F = np.array([[0.0, 2.0], [1.0, 1.0], [2.0, 0.0]], dtype=float)
    V = np.zeros(3, dtype=float)

    plugin._update_archive(X, F, V)
    kept = {tuple(row.tolist()) for row in plugin.archive_F}
    assert (0.0, 2.0) in kept
    assert (2.0, 0.0) in kept
    assert len(kept) == 2


class _ToyProblem(BlackBoxProblem):
    def __init__(self, dim: int = 2) -> None:
        super().__init__(name="toy", dimension=int(dim), objectives=["f1", "f2"])

    def evaluate(self, x):
        arr = np.asarray(x, dtype=float)
        return np.array([arr[0], arr[1]], dtype=float)


def test_solver_sbx_can_generate_non_linear_offspring_when_eta_small() -> None:
    solver = EvolutionSolver(
        _ToyProblem(dim=64),
        pop_size=2,
        sbx_eta_c=0.1,
        crossover_rate=1.0,
        random_seed=7,
    )
    parents = np.vstack([np.zeros(64, dtype=float), np.ones(64, dtype=float)])
    offspring = solver.crossover(parents)
    # SBX should not degenerate to identity when eta is very small.
    assert not np.allclose(offspring, parents)


def test_update_pareto_solutions_keeps_front_boundaries_with_crowding() -> None:
    solver = EvolutionSolver(_ToyProblem(), pop_size=60, max_pareto_solutions=50)
    xs = np.linspace(0.0, 59.0, 60)
    solver.population = np.column_stack([xs, xs])
    solver.objectives = np.column_stack([xs, 59.0 - xs])
    solver.constraint_violations = np.zeros(60, dtype=float)
    solver.update_pareto_solutions()
    kept_first_dim = set(np.asarray(solver.pareto_solutions["individuals"])[:, 0].astype(float).tolist())
    assert 0.0 in kept_first_dim
    assert 59.0 in kept_first_dim
    assert len(kept_first_dim) == 50


def test_moead_equal_decomposition_value_does_not_replace() -> None:
    adapter = MOEADAdapter(MOEADConfig())
    adapter.pop_F = np.array([[1.0, 1.0]], dtype=float)
    adapter.pop_V = np.array([0.0], dtype=float)
    adapter.weights = np.array([[0.5, 0.5]], dtype=float)
    adapter.ideal = np.array([0.0, 0.0], dtype=float)
    assert adapter._is_better_for_subproblem(np.array([1.0, 1.0], dtype=float), 0.0, 0) is False


def test_vns_sigma_is_capped() -> None:
    adapter = VNSAdapter(VNSConfig(base_sigma=0.5, scale=10.0, max_sigma=1.0))
    adapter.k = 4
    assert np.isclose(adapter._current_sigma(), 1.0)
