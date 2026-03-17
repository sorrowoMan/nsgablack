"""Traditional single-objective GA baseline (no framework abstractions)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np


@dataclass
class BaselineGAConfig:
    dimension: int = 12
    lower_bound: float = -5.0
    upper_bound: float = 5.0
    population_size: int = 80
    generations: int = 60
    crossover_rate: float = 0.9
    mutation_rate: float = 0.2
    mutation_sigma: float = 0.25
    tournament_size: int = 2
    seed: int = 7


def objective(x: np.ndarray) -> float:
    """Minimize shifted sphere: f(x)=sum((x-2)^2)."""
    arr = np.asarray(x, dtype=float)
    return float(np.sum((arr - 2.0) ** 2))


def initialize_population(cfg: BaselineGAConfig, rng: np.random.Generator) -> np.ndarray:
    return rng.uniform(cfg.lower_bound, cfg.upper_bound, size=(cfg.population_size, cfg.dimension))


def evaluate_population(population: np.ndarray) -> np.ndarray:
    return np.asarray([objective(ind) for ind in population], dtype=float)


def tournament_select(scores: np.ndarray, cfg: BaselineGAConfig, rng: np.random.Generator) -> int:
    candidates = rng.integers(0, scores.shape[0], size=max(1, cfg.tournament_size))
    best_local = int(candidates[np.argmin(scores[candidates])])
    return best_local


def crossover(p1: np.ndarray, p2: np.ndarray, cfg: BaselineGAConfig, rng: np.random.Generator) -> np.ndarray:
    if rng.random() > cfg.crossover_rate:
        return np.array(p1, copy=True)
    alpha = rng.random(p1.shape[0])
    return (alpha * p1) + ((1.0 - alpha) * p2)


def mutate(child: np.ndarray, cfg: BaselineGAConfig, rng: np.random.Generator) -> np.ndarray:
    out = np.array(child, copy=True)
    mask = rng.random(out.shape[0]) < cfg.mutation_rate
    if np.any(mask):
        out[mask] += rng.normal(0.0, cfg.mutation_sigma, size=int(np.sum(mask)))
    return np.clip(out, cfg.lower_bound, cfg.upper_bound)


def evolve_one_generation(population: np.ndarray, scores: np.ndarray, cfg: BaselineGAConfig, rng: np.random.Generator) -> np.ndarray:
    next_pop = []
    for _ in range(cfg.population_size):
        i = tournament_select(scores, cfg, rng)
        j = tournament_select(scores, cfg, rng)
        child = crossover(population[i], population[j], cfg, rng)
        child = mutate(child, cfg, rng)
        next_pop.append(child)
    return np.asarray(next_pop, dtype=float)


def run_baseline(cfg: BaselineGAConfig) -> Tuple[np.ndarray, float]:
    rng = np.random.default_rng(cfg.seed)
    population = initialize_population(cfg, rng)

    best_x = np.array(population[0], copy=True)
    best_score = float('inf')

    for gen in range(cfg.generations):
        scores = evaluate_population(population)
        best_idx = int(np.argmin(scores))
        if float(scores[best_idx]) < best_score:
            best_score = float(scores[best_idx])
            best_x = np.array(population[best_idx], copy=True)

        if gen % 10 == 0 or gen == cfg.generations - 1:
            print(f'[baseline] gen={gen:03d} best={best_score:.6f}')

        population = evolve_one_generation(population, scores, cfg, rng)

    return best_x, best_score


if __name__ == '__main__':
    config = BaselineGAConfig()
    x_best, f_best = run_baseline(config)
    print('\n[baseline] done')
    print(f'[baseline] best objective: {f_best:.6f}')
    print(f'[baseline] best x (first 5 dims): {x_best[:5]}')
