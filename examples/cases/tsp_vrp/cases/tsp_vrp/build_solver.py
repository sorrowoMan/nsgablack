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

import numpy as np

from nsgablack.representation.permutation import PermutationInitializer
from nsgablack.representation.continuous import ContextGaussianMutation
from nsgablack.representation import RepresentationPipeline
from nsgablack.adapters import SAConfig, SimulatedAnnealingAdapter
from nsgablack.bias.specialized.graph.constraints import TSPConstraintBias, HamiltonianPathConstraintBias
from nsgablack.bias import BiasModule
from nsgablack.core.composable_solver import ComposableSolver
from .problem.tsp_problem import TSPProblem


def build_solver(
    *,
    pop_size: int = 20,
    max_steps: int = 2000,
    random_seed: int = 2,
    resource_context=None,
    component_overrides=None,
) -> ComposableSolver:
    """Canonical scaffold entry: assemble TSP solver (SA).

    Uses synthetic 20-city random coordinates by default.
    Override the problem via component_overrides={"problem": my_problem}.
    """
    overrides = dict(component_overrides or {})
    config = dict(overrides.pop("config", {}) or {})
    pop_size = int(config.pop("pop_size", pop_size))
    max_steps = int(config.pop("max_steps", max_steps))
    random_seed = int(config.pop("random_seed", random_seed))
    n_cities = int(config.pop("n_cities", 20))
    if config:
        raise ValueError("unsupported tsp_vrp config overrides: " + str(sorted(config)))
    problem = overrides.pop("problem", None)
    if problem is None:
        rng = np.random.default_rng(42)
        coords = rng.uniform(0, 100, size=(n_cities, 2))
        dm = np.sqrt(np.sum((coords[:, None, :] - coords[None, :, :]) ** 2, axis=-1))
        problem = TSPProblem(dm)
    n_cities = int(problem.n_cities)

    sigma = float(n_cities) / 6.0

    initializer = PermutationInitializer()
    initializer._rng = np.random.default_rng(random_seed)

    mutator = ContextGaussianMutation(
        base_sigma=sigma,
        low=0.0,
        high=float(n_cities - 1),
    )
    mutator._rng = np.random.default_rng(random_seed + 1)

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
        random_seed=random_seed,
    )
    sa_adapter = SimulatedAnnealingAdapter(sa_config)

    solver = ComposableSolver(
        problem=problem,
        adapter=sa_adapter,
        representation_pipeline=pipeline,
        bias_module=bias,
    )
    solver.set_max_steps(max_steps)
    solver.set_random_seed(random_seed)
    from nsgablack.project import apply_solver_component_overrides

    apply_solver_component_overrides(solver, overrides)
    solver.set_resource_context(resource_context)
    return solver
