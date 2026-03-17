"""Traditional multi-objective NSGA-II baseline (no framework abstractions)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple

import numpy as np


@dataclass
class BaselineNSGA2Config:
    dimension: int = 12
    lower_bound: float = -5.0
    upper_bound: float = 5.0
    population_size: int = 80
    generations: int = 80
    crossover_rate: float = 0.9
    mutation_rate: float = 0.2
    mutation_sigma: float = 0.25
    tournament_size: int = 2
    seed: int = 11


def evaluate_individual(x: np.ndarray) -> np.ndarray:
    arr = np.asarray(x, dtype=float)
    f1 = float(np.sum(arr ** 2))
    f2 = float(np.sum((arr - 2.0) ** 2))
    return np.array([f1, f2], dtype=float)


def evaluate_population(population: np.ndarray) -> np.ndarray:
    return np.asarray([evaluate_individual(ind) for ind in population], dtype=float)


def dominates(a: np.ndarray, b: np.ndarray) -> bool:
    return bool(np.all(a <= b) and np.any(a < b))


def fast_non_dominated_sort(objectives: np.ndarray) -> Tuple[List[List[int]], np.ndarray]:
    n = objectives.shape[0]
    dominate_set: List[List[int]] = [[] for _ in range(n)]
    dominated_count = np.zeros(n, dtype=int)
    rank = np.zeros(n, dtype=int)
    fronts: List[List[int]] = [[]]

    for p in range(n):
        for q in range(n):
            if p == q:
                continue
            if dominates(objectives[p], objectives[q]):
                dominate_set[p].append(q)
            elif dominates(objectives[q], objectives[p]):
                dominated_count[p] += 1
        if dominated_count[p] == 0:
            rank[p] = 0
            fronts[0].append(p)

    current = 0
    while current < len(fronts) and fronts[current]:
        nxt: List[int] = []
        for p in fronts[current]:
            for q in dominate_set[p]:
                dominated_count[q] -= 1
                if dominated_count[q] == 0:
                    rank[q] = current + 1
                    nxt.append(q)
        if len(nxt) > 0:
            fronts.append(nxt)
        current += 1

    return fronts, rank


def crowding_distance(objectives: np.ndarray, front: Sequence[int]) -> np.ndarray:
    n = objectives.shape[0]
    dist = np.zeros(n, dtype=float)
    if len(front) == 0:
        return dist
    if len(front) <= 2:
        for idx in front:
            dist[idx] = float('inf')
        return dist

    m = objectives.shape[1]
    front_list = list(front)
    for j in range(m):
        front_sorted = sorted(front_list, key=lambda idx: objectives[idx, j])
        low = objectives[front_sorted[0], j]
        high = objectives[front_sorted[-1], j]
        dist[front_sorted[0]] = float('inf')
        dist[front_sorted[-1]] = float('inf')
        if high <= low:
            continue
        scale = high - low
        for k in range(1, len(front_sorted) - 1):
            prev_idx = front_sorted[k - 1]
            next_idx = front_sorted[k + 1]
            cur_idx = front_sorted[k]
            dist[cur_idx] += (objectives[next_idx, j] - objectives[prev_idx, j]) / scale
    return dist


def initialize_population(cfg: BaselineNSGA2Config, rng: np.random.Generator) -> np.ndarray:
    return rng.uniform(cfg.lower_bound, cfg.upper_bound, size=(cfg.population_size, cfg.dimension))


def crossover(p1: np.ndarray, p2: np.ndarray, cfg: BaselineNSGA2Config, rng: np.random.Generator) -> np.ndarray:
    if rng.random() > cfg.crossover_rate:
        return np.array(p1, copy=True)
    alpha = rng.random(p1.shape[0])
    return (alpha * p1) + ((1.0 - alpha) * p2)


def mutate(x: np.ndarray, cfg: BaselineNSGA2Config, rng: np.random.Generator) -> np.ndarray:
    out = np.array(x, copy=True)
    mask = rng.random(out.shape[0]) < cfg.mutation_rate
    if np.any(mask):
        out[mask] += rng.normal(0.0, cfg.mutation_sigma, size=int(np.sum(mask)))
    return np.clip(out, cfg.lower_bound, cfg.upper_bound)


def tournament_select(rank: np.ndarray, crowd: np.ndarray, cfg: BaselineNSGA2Config, rng: np.random.Generator) -> int:
    candidates = rng.integers(0, rank.shape[0], size=max(1, cfg.tournament_size))
    best = int(candidates[0])
    for c in candidates[1:]:
        c = int(c)
        if rank[c] < rank[best]:
            best = c
        elif rank[c] == rank[best] and crowd[c] > crowd[best]:
            best = c
    return best


def environmental_selection(population: np.ndarray, objectives: np.ndarray, keep_n: int) -> Tuple[np.ndarray, np.ndarray, List[List[int]]]:
    fronts, _ = fast_non_dominated_sort(objectives)
    keep_indices: List[int] = []

    for front in fronts:
        if len(keep_indices) + len(front) <= keep_n:
            keep_indices.extend(front)
            continue
        dist = crowding_distance(objectives, front)
        ranked_front = sorted(front, key=lambda idx: dist[idx], reverse=True)
        remain = max(0, keep_n - len(keep_indices))
        keep_indices.extend(ranked_front[:remain])
        break

    keep = np.asarray(keep_indices, dtype=int)
    next_pop = population[keep]
    next_obj = objectives[keep]
    next_fronts, _ = fast_non_dominated_sort(next_obj)
    return next_pop, next_obj, next_fronts


def run_baseline(cfg: BaselineNSGA2Config) -> Tuple[np.ndarray, np.ndarray, List[List[int]]]:
    rng = np.random.default_rng(cfg.seed)
    population = initialize_population(cfg, rng)
    objectives = evaluate_population(population)

    for gen in range(cfg.generations):
        fronts, rank = fast_non_dominated_sort(objectives)
        crowd = np.zeros(population.shape[0], dtype=float)
        for front in fronts:
            crowd += crowding_distance(objectives, front)

        offspring = []
        for _ in range(cfg.population_size):
            i = tournament_select(rank, crowd, cfg, rng)
            j = tournament_select(rank, crowd, cfg, rng)
            child = crossover(population[i], population[j], cfg, rng)
            child = mutate(child, cfg, rng)
            offspring.append(child)
        offspring = np.asarray(offspring, dtype=float)
        offspring_obj = evaluate_population(offspring)

        merged_pop = np.vstack([population, offspring])
        merged_obj = np.vstack([objectives, offspring_obj])
        population, objectives, fronts = environmental_selection(merged_pop, merged_obj, cfg.population_size)

        if gen % 10 == 0 or gen == cfg.generations - 1:
            front0 = fronts[0] if fronts else []
            rep = objectives[front0[0]] if len(front0) > 0 else np.array([np.nan, np.nan])
            print(
                f"[baseline-nsga2] gen={gen:03d} front0_size={len(front0)} "
                f"rep_obj=[{float(rep[0]):.4f}, {float(rep[1]):.4f}]"
            )

    return population, objectives, fronts


if __name__ == '__main__':
    cfg = BaselineNSGA2Config()
    pop, obj, fronts = run_baseline(cfg)
    front0 = fronts[0] if fronts else []
    print('\n[baseline-nsga2] done')
    print('[baseline-nsga2] final front0 size:', len(front0))
    if len(front0) > 0:
        print('[baseline-nsga2] first front objective sample:', obj[front0[0]])
