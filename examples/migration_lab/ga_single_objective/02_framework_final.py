"""Framework-native GA example / 框架版单目标 GA 示例。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

import numpy as np


def _ensure_repo_importable(start: Path | None = None) -> None:
    """Ensure `import nsgablack` works when this file is run directly."""
    cur = (start or Path(__file__)).resolve()
    for _ in range(12):
        if (cur / 'pyproject.toml').exists() and (cur / '__init__.py').exists():
            parent = cur.parent
            if str(parent) not in sys.path:
                sys.path.insert(0, str(parent))
            return
        cur = cur.parent


_ensure_repo_importable(Path(__file__))

from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.core.adapters import NSGA2Adapter, NSGA2Config
from nsgablack.representation import RepresentationPipeline
from nsgablack.representation.continuous import ClipRepair, GaussianMutation, UniformInitializer


@dataclass
class FrameworkConfig:
    dimension: int = 12
    lower_bound: float = -5.0
    upper_bound: float = 5.0
    population_size: int = 80
    generations: int = 60
    crossover_rate: float = 0.9
    mutation_sigma: float = 0.25
    seed: int = 7


class ShiftedSphereProblem(BlackBoxProblem):
    """Single-objective test problem / 单目标测试问题。"""

    def __init__(self, cfg: FrameworkConfig):
        bounds = {f'x{i}': (cfg.lower_bound, cfg.upper_bound) for i in range(cfg.dimension)}
        super().__init__(
            name='ShiftedSphere',
            dimension=cfg.dimension,
            bounds=bounds,
            objectives=['shifted_sphere'],
        )

    def evaluate(self, x):
        arr = np.asarray(x, dtype=float)
        return float(np.sum((arr - 2.0) ** 2))


def build_solver(cfg: FrameworkConfig) -> ComposableSolver:
    problem = ShiftedSphereProblem(cfg)

    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=cfg.lower_bound, high=cfg.upper_bound),
        mutator=GaussianMutation(sigma=cfg.mutation_sigma, low=cfg.lower_bound, high=cfg.upper_bound),
        repair=ClipRepair(low=cfg.lower_bound, high=cfg.upper_bound),
    )

    adapter = NSGA2Adapter(
        NSGA2Config(
            population_size=cfg.population_size,
            offspring_size=cfg.population_size,
            crossover_rate=cfg.crossover_rate,
            objective_aggregation='sum',
        )
    )

    solver = ComposableSolver(problem=problem, adapter=adapter, representation_pipeline=pipeline)
    solver.set_max_steps(cfg.generations)
    solver.set_random_seed(cfg.seed)
    return solver


def run_framework(cfg: FrameworkConfig) -> None:
    solver = build_solver(cfg)
    result = solver.run()

    print('[framework] status:', result.get('status'))
    print('[framework] steps:', result.get('steps'))
    print(f'[framework] best objective: {float(solver.best_objective):.6f}')
    best_x = np.asarray(solver.best_x, dtype=float)
    print(f'[framework] best x (first 5 dims): {best_x[:5]}')


if __name__ == '__main__':
    run_framework(FrameworkConfig())
