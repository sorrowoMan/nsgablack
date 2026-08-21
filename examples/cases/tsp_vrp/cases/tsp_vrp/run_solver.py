# -*- coding: utf-8 -*-
"""TSP/VRP benchmark CLI for the canonical Case assembly."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

if __package__ in {None, ""}:
    _CASE_ROOT = Path(__file__).resolve().parent
    sys.path.insert(0, str(_CASE_ROOT.parent.parent))
    from cases.tsp_vrp.build_solver import build_solver  # noqa: E402
    from cases.tsp_vrp.problem.tsp_problem import TSPProblem  # noqa: E402
else:
    from .build_solver import build_solver
    from .problem.tsp_problem import TSPProblem

from nsgablack.project.scaffold import print_solver_check


def _nearest_neighbor_route(distance_matrix: np.ndarray, start: int = 0) -> np.ndarray:
    matrix = np.asarray(distance_matrix, dtype=float)
    unvisited = set(range(matrix.shape[0]))
    route = [start]
    unvisited.discard(start)
    while unvisited:
        current = route[-1]
        route.append(min(unvisited, key=lambda city: matrix[current, city]))
        unvisited.discard(route[-1])
    return np.asarray(route, dtype=int)


def _route_length(distance_matrix: np.ndarray) -> float:
    route = _nearest_neighbor_route(distance_matrix)
    matrix = np.asarray(distance_matrix, dtype=float)
    return float(sum(matrix[route[i], route[(i + 1) % len(route)]] for i in range(len(route))))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="TSP/VRP route optimization with nsgablack SA")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n-cities", type=int, default=20)
    parser.add_argument("--pop-size", type=int, default=20)
    parser.add_argument("--max-steps", type=int, default=2000)
    parser.add_argument("--vrp", action="store_true")
    parser.add_argument("--n-vehicles", type=int, default=3)
    parser.add_argument("--capacity", type=float, default=50.0)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    rng = np.random.default_rng(args.seed)
    coords = rng.uniform(0, 100, size=(args.n_cities, 2))
    distances = np.sqrt(np.sum((coords[:, None, :] - coords[None, :, :]) ** 2, axis=-1))
    problem = TSPProblem(
        distances,
        n_vehicles=args.n_vehicles if args.vrp else 1,
        capacity=args.capacity if args.vrp else None,
        demands=rng.uniform(5, 20, size=args.n_cities) if args.vrp else None,
    )
    solver = build_solver(
        pop_size=args.pop_size,
        max_steps=args.max_steps,
        random_seed=args.seed,
        component_overrides={"problem": problem},
    )
    if args.check:
        print_solver_check(solver)
        return 0

    baseline_length = _route_length(distances)
    started = time.perf_counter()
    solver.run()
    elapsed = time.perf_counter() - started
    best_route = (
        solver.problem.decode_permutation(solver.best_x)
        if solver.best_x is not None
        else np.arange(args.n_cities, dtype=int)
    )
    best_length = float(getattr(solver, "best_objective", float("inf")))
    improvement = (
        (baseline_length - best_length) / baseline_length * 100
        if baseline_length > 0
        else 0.0
    )
    print(f"Nearest-Neighbor heuristic : {baseline_length:.2f}")
    print(f"nsgablack SA best          : {best_length:.2f}")
    print(f"Improvement                : {improvement:+.1f}%")
    print(f"Elapsed                    : {elapsed:.2f}s")
    print(f"Best route                 : {best_route.tolist()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
