"""Causal Discovery: nsgablack DE discovers DAG structure from observational data.

Two modes:
  pc    - binary adjacency (PC algorithm style), minimize BIC
  lingam - continuous edge weights (LiNGAM style), minimize residual dependence

Component composition (all from framework, no custom bias files):
  - Adapter: DifferentialEvolutionAdapter
  - Representation: IntegerMatrixInitializer + ContextGaussianMutation + ClipRepair
  - Bias: CallableBias (acyclicity via Kahn alg) + CallableBias (sparsity via L1)
  - Problem: PCDiscoveryProblem / LiNGAMDiscoveryProblem (custom, domain-specific)
"""
from __future__ import annotations

import numpy as np

from nsgablack.adapters import DEConfig, DifferentialEvolutionAdapter
from nsgablack.bias import BiasModule
from nsgablack.bias.domain.callable_bias import CallableBias
from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.representation import RepresentationPipeline
from nsgablack.representation.continuous import ClipRepair, ContextGaussianMutation
from nsgablack.representation.matrix import IntegerMatrixInitializer

from problem.causal_discovery_problem import PCDiscoveryProblem, LiNGAMDiscoveryProblem


def acyclicity_penalty(x: np.ndarray, n_vars: int, cycle_weight: float = 100.0) -> float:
    """Kahn topological sort: return penalty proportional to nodes/edges in cycles."""
    adj = np.asarray(x, dtype=float).reshape(n_vars, n_vars)
    binary = (np.abs(adj) > 1e-8).astype(int)
    np.fill_diagonal(binary, 0)

    in_deg = binary.sum(axis=0).tolist()
    queue = [i for i in range(n_vars) if in_deg[i] == 0]
    visited = set()
    while queue:
        u = queue.pop(0)
        visited.add(u)
        for v in range(n_vars):
            if binary[u, v]:
                in_deg[v] -= 1
                if in_deg[v] == 0:
                    queue.append(v)

    remaining = [i for i in range(n_vars) if i not in visited]
    if not remaining:
        return 0.0

    n_cycle_edges = sum(1 for i in remaining for j in remaining if binary[i, j])
    n_cycle_nodes = len(remaining)
    return float((n_cycle_nodes + n_cycle_edges) * cycle_weight)


def build_solver(
    *,
    mode: str = "pc",
    n_vars: int = 6,
    pop_size: int = 40,
    max_steps: int = 400,
    random_seed: int = 42,
    resource_context=None,
    component_overrides=None,
) -> ComposableSolver:
    """Canonical scaffold entry for PC or LiNGAM structure search.

    Uses synthetic 6-variable DAG data by default.
    Override the problem via component_overrides={"problem": my_problem}.
    """
    overrides = dict(component_overrides or {})
    config = dict(overrides.pop("config", {}) or {})
    mode = str(config.pop("mode", mode))
    n_vars = int(config.pop("n_vars", n_vars))
    pop_size = int(config.pop("pop_size", pop_size))
    max_steps = int(config.pop("max_steps", max_steps))
    random_seed = int(config.pop("random_seed", random_seed))
    if config:
        raise ValueError("unsupported causal_discovery config overrides: " + str(sorted(config)))
    mode = str(mode).strip().lower()
    if mode not in {"pc", "lingam"}:
        raise ValueError("mode must be 'pc' or 'lingam'")
    n_vars = int(n_vars)

    problem = overrides.pop("problem", None)
    if problem is None:
        _weights, data, _correlation = _generate_random_dag(n_vars, seed=random_seed)
        problem = (
            PCDiscoveryProblem(data, n_samples=data.shape[0], sparsity_lambda=0.5)
            if mode == "pc"
            else LiNGAMDiscoveryProblem(data, sparsity_lambda=0.1)
        )

    if mode == "pc":
        initializer = IntegerMatrixInitializer(rows=n_vars, cols=n_vars, low=0, high=1)
        repair = ClipRepair(low=0.0, high=1.0)
        cycle_weight = 1000.0
    else:
        initializer = IntegerMatrixInitializer(rows=n_vars, cols=n_vars, low=-2, high=2)
        repair = ClipRepair(low=-2.0, high=2.0)
        cycle_weight = 500.0
    mutator = ContextGaussianMutation(base_sigma=0.25 if mode == "pc" else 0.3)

    pipeline = RepresentationPipeline(
        initializer=initializer,
        mutator=mutator,
        repair=repair,
    )

    bias = BiasModule()

    def _acyclicity(x, constraints, context):
        penalty = acyclicity_penalty(x, n_vars, cycle_weight=cycle_weight)
        return {"penalty": float(penalty)}

    bias.add(CallableBias(name="acyclicity", func=_acyclicity, weight=1.0, mode="penalty"))

    def _sparsity(x, constraints, context):
        # Bias evaluation is observational: mutating ``x`` would desynchronise
        # the Solver-owned CandidateBatch semantic and numeric views.
        adj = np.asarray(x, dtype=float).reshape(n_vars, n_vars).copy()
        np.fill_diagonal(adj, 0)
        return {"penalty": float(np.abs(adj).sum() * 10.0)}

    bias.add(CallableBias(name="sparsity", func=_sparsity, weight=1.0, mode="penalty"))

    solver = ComposableSolver(
        problem=problem,
        adapter=DifferentialEvolutionAdapter(DEConfig(batch_size=pop_size)),
        representation_pipeline=pipeline,
        bias_module=bias,
    )
    solver.set_max_steps(max_steps)
    solver.set_random_seed(random_seed)
    from nsgablack.project import apply_solver_component_overrides

    apply_solver_component_overrides(solver, overrides)
    solver.set_resource_context(resource_context)
    return solver


def _generate_random_dag(
    n_vars: int,
    edge_prob: float = 0.3,
    weight_range: tuple[float, float] = (0.5, 2.0),
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generate a random DAG and sample linear SEM data.

    Returns
    -------
    W : np.ndarray  (n_vars, n_vars)  true weight matrix
    data : np.ndarray  (n_samples, n_vars)
    corr : np.ndarray  (n_vars, n_vars)  correlation matrix
    """
    rng = np.random.default_rng(seed)
    n_samples = n_vars * 50

    permutation = rng.permutation(n_vars)
    inv_perm = np.argsort(permutation)

    W = np.zeros((n_vars, n_vars))
    for i in range(n_vars):
        for j in range(i + 1, n_vars):
            if rng.random() < edge_prob:
                lo, hi = weight_range
                w = rng.uniform(lo, hi) * rng.choice([-1, 1])
                W[permutation[i], permutation[j]] = w

    noise = rng.standard_normal((n_samples, n_vars))
    data = np.zeros((n_samples, n_vars))
    for i in range(n_vars):
        data[:, i] = noise[:, i]
    for j in range(n_vars):
        for i in range(n_vars):
            if np.abs(W[i, j]) > 1e-8:
                data[:, j] += W[i, j] * data[:, i]

    data_centered = data - data.mean(axis=0)
    corr = np.corrcoef(data_centered.T)

    W_ordered = np.zeros((n_vars, n_vars))
    for a in range(n_vars):
        for b in range(n_vars):
            W_ordered[inv_perm[a], inv_perm[b]] = W[a, b]

    return W_ordered, data, corr


def _adj_from_solution(x: np.ndarray, n_vars: int, mode: str) -> np.ndarray:
    adj = np.asarray(x, dtype=float).ravel().reshape(n_vars, n_vars)
    if mode == "pc":
        adj = (adj >= 0.5).astype(float)
    adj[np.diag_indices(n_vars)] = 0
    return adj


def _shd(A_true: np.ndarray, A_est: np.ndarray) -> int:
    """Structural Hamming Distance between two binary adjacency matrices."""
    diff = np.abs(A_true - A_est)
    return int(diff.sum())
