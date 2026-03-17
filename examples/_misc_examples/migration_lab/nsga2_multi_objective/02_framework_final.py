"""Framework-native NSGA-II multi-objective example / 框架原生 NSGA-II 多目标示例"""

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
from nsgablack.adapters import NSGA2Adapter, NSGA2Config
from nsgablack.representation import RepresentationPipeline
from nsgablack.representation.continuous import ClipRepair, GaussianMutation, UniformInitializer
from nsgablack.utils.performance.fast_non_dominated_sort import FastNonDominatedSort


@dataclass
class FrameworkNSGA2Config:
    dimension: int = 12
    lower_bound: float = -5.0
    upper_bound: float = 5.0
    population_size: int = 80
    generations: int = 80
    crossover_rate: float = 0.9
    mutation_sigma: float = 0.25
    seed: int = 11


class BiObjectiveShiftedSphere(BlackBoxProblem):
    """Two-objective toy problem / 双目标玩具问题"""

    def __init__(self, cfg: FrameworkNSGA2Config):
        bounds = {f'x{i}': (cfg.lower_bound, cfg.upper_bound) for i in range(cfg.dimension)}
        super().__init__(
            name='BiObjectiveShiftedSphere',
            dimension=cfg.dimension,
            bounds=bounds,
            objectives=['f1_sphere', 'f2_shifted_sphere'],
        )

    def evaluate(self, x):
        arr = np.asarray(x, dtype=float)
        f1 = float(np.sum(arr ** 2))
        f2 = float(np.sum((arr - 2.0) ** 2))
        return np.array([f1, f2], dtype=float)


def build_solver(cfg: FrameworkNSGA2Config) -> ComposableSolver:
    problem = BiObjectiveShiftedSphere(cfg)

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


def run_framework(cfg: FrameworkNSGA2Config) -> None:
    solver = build_solver(cfg)
    result = solver.run()

    adapter = solver.adapter
    objectives = np.asarray(getattr(adapter, 'objectives', []), dtype=float)
    violations = np.asarray(getattr(adapter, 'violations', []), dtype=float)

    if objectives.ndim == 1 and objectives.size > 0:
        objectives = objectives.reshape(-1, 1)

    if objectives.size == 0:
        print('[framework-nsga2] status:', result.get('status'))
        print('[framework-nsga2] no objectives produced')
        return

    fronts, _ = FastNonDominatedSort.sort(objectives, violations)
    front0 = fronts[0] if len(fronts) > 0 else []

    print('[framework-nsga2] status:', result.get('status'))
    print('[framework-nsga2] steps:', result.get('steps'))
    print('[framework-nsga2] final front0 size:', len(front0))
    if len(front0) > 0:
        sample = objectives[int(front0[0])]
        print(f"[framework-nsga2] front sample objective: [{float(sample[0]):.4f}, {float(sample[1]):.4f}]")


if __name__ == '__main__':
    run_framework(FrameworkNSGA2Config())
