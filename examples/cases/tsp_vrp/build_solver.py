"""
TSP / VRP: nsgablack Simulated Annealing vs Nearest-Neighbor heuristic.

Demonstrates combinatorial route optimization using framework components only:
  - repr.permutation (PermutationInitializer)
  - repr.context_gaussian (ContextGaussianMutation)
  - adapter.sa (SimulatedAnnealingAdapter)
  - bias.graph_tsp_constraint (TSPConstraintBias)
  - bias.graph_hamiltonian_constraint (HamiltonianPathConstraintBias)

City coordinates are randomly generated in 2D; distance matrix is Euclidean.
"""
from __future__ import annotations
import argparse
import sys
import time
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

_cur = _THIS_DIR
for _i in range(10):
    if (_cur / "pyproject.toml").exists() and (_cur / "__init__.py").exists():
        _parent = _cur.parent
        if str(_parent) not in sys.path:
            sys.path.insert(0, str(_parent))
        break
    _cur = _cur.parent

import numpy as np

from nsgablack.representation.permutation import PermutationInitializer
from nsgablack.representation.continuous import ContextGaussianMutation
from nsgablack.representation import RepresentationPipeline
from nsgablack.adapters import SAConfig, SimulatedAnnealingAdapter
from nsgablack.bias.specialized.graph.constraints import TSPConstraintBias, HamiltonianPathConstraintBias
from nsgablack.bias import BiasModule
from nsgablack.core.composable_solver import ComposableSolver
from problem.tsp_problem import TSPProblem


def nearest_neighbor_route(distance_matrix: np.ndarray, start: int = 0) -> np.ndarray:
    dm = np.asarray(distance_matrix, dtype=float)
    n = dm.shape[0]
    unvisited = set(range(n))
    route = [start]
    unvisited.discard(start)
    current = start
    while unvisited:
        next_city = min(unvisited, key=lambda j: dm[current, j])
        route.append(next_city)
        unvisited.discard(next_city)
        current = next_city
    return np.array(route, dtype=int)


def nn_route_length(distance_matrix: np.ndarray, start: int = 0) -> float:
    route = nearest_neighbor_route(distance_matrix, start)
    dm = np.asarray(distance_matrix, dtype=float)
    total = 0.0
    n = len(route)
    for k in range(n - 1):
        total += dm[route[k], route[k + 1]]
    total += dm[route[-1], route[0]]
    return total


def build_solver(
    distance_matrix: np.ndarray,
    *,
    pop_size: int = 20,
    max_steps: int = 2000,
    n_vehicles: int = 1,
    capacity: float | None = None,
    demands: np.ndarray | None = None,
) -> ComposableSolver:
    dm = np.asarray(distance_matrix, dtype=float)
    n_cities = dm.shape[0]

    prob = TSPProblem(
        dm,
        n_vehicles=n_vehicles,
        capacity=capacity,
        demands=demands,
    )

    sigma = float(n_cities) / 6.0

    initializer = PermutationInitializer()
    initializer._rng = np.random.default_rng(2)

    mutator = ContextGaussianMutation(
        base_sigma=sigma,
        low=0.0,
        high=float(n_cities - 1),
    )
    mutator._rng = np.random.default_rng(3)

    pipeline = RepresentationPipeline(
        initializer=initializer,
        mutator=mutator,
    )

    bias = BiasModule()
    bias.add(TSPConstraintBias(num_cities=n_cities, penalty_scale=0.01))
    bias.add(HamiltonianPathConstraintBias(num_nodes=n_cities, is_cycle=True, penalty_scale=0.01))

    sa_config = SAConfig(
        batch_size=pop_size,
        initial_temperature=50.0,
        cooling_rate=0.997,
        min_temperature=0.001,
        base_sigma=sigma,
        sigma_temperature_scale=0.8,
        random_seed=2,
    )
    sa_adapter = SimulatedAnnealingAdapter(sa_config)

    solver = ComposableSolver(
        problem=prob,
        adapter=sa_adapter,
        representation_pipeline=pipeline,
        bias_module=bias,
    )
    solver.set_max_steps(max_steps)
    return solver


def main():
    p = argparse.ArgumentParser(
        description="TSP/VRP route optimization with nsgablack SA.",
    )
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--n-cities", type=int, default=20)
    p.add_argument("--pop-size", type=int, default=20)
    p.add_argument("--max-steps", type=int, default=2000)
    p.add_argument("--vrp", action="store_true", help="Run VRP mode with capacity constraints.")
    p.add_argument("--n-vehicles", type=int, default=3)
    p.add_argument("--capacity", type=float, default=50.0)
    args = p.parse_args()

    rng = np.random.default_rng(args.seed)
    n = args.n_cities

    coords = rng.uniform(0, 100, size=(n, 2))
    dm = np.sqrt(np.sum((coords[:, None, :] - coords[None, :, :]) ** 2, axis=-1))

    np.random.seed(args.seed)

    is_vrp = args.vrp
    demands = rng.uniform(5, 20, size=n).astype(float) if is_vrp else None

    solver = build_solver(
        dm,
        pop_size=args.pop_size,
        max_steps=args.max_steps,
        n_vehicles=args.n_vehicles if is_vrp else 1,
        capacity=args.capacity if is_vrp else None,
        demands=demands,
    )
    solver.set_random_seed(2)

    nn_len = nn_route_length(dm)
    nn_route = nearest_neighbor_route(dm)

    t0 = time.perf_counter()
    solver.run()
    t1 = time.perf_counter()
    elapsed = t1 - t0

    best_len = float("inf")
    best_perm = np.arange(n, dtype=int)
    if solver.best_x is not None:
        best_perm = solver.problem.decode_permutation(solver.best_x)
        best_len = float(getattr(solver, "best_objective", float("inf")))

    print(f"\n{'='*60}")
    print(f"  TSP{'/VRP' if is_vrp else ''}  |  n_cities={n}  |  pop={args.pop_size}  |  steps={args.max_steps}")
    print(f"{'='*60}")
    print(f"  Nearest-Neighbor heuristic : {nn_len:.2f}")
    print(f"  nsgablack SA best          : {best_len:.2f}")
    improvement = (nn_len - best_len) / nn_len * 100 if nn_len > 0 else 0.0
    print(f"  Improvement                : {improvement:+.1f}%")
    print(f"  Elapsed                    : {elapsed:.2f}s")
    print(f"  Best route                 : {best_perm.tolist()}")

    expected = set(range(n))
    actual = set(int(c) for c in best_perm)
    if expected != actual:
        missing = expected - actual
        extra = actual - expected
        print(f"  WARNING: sub-tour detected! missing={missing}, extra={extra}")


if __name__ == "__main__":
    main()
