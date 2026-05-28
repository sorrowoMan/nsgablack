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

import sys
import time
import argparse
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))
from _bootstrap import ensure_nsgablack_importable

ensure_nsgablack_importable(Path(__file__))

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
    data: np.ndarray,
    n_vars: int,
    mode: str = "pc",
    *,
    pop_size: int = 40,
    max_steps: int = 400,
    n_samples: int | None = None,
) -> ComposableSolver:
    """Build a DE-powered causal discovery solver.

    Parameters
    ----------
    data : np.ndarray
        Raw data matrix (n_samples, n_vars) or correlation matrix (n_vars, n_vars).
    n_vars : int
        Number of variables.
    mode : str
        "pc" for binary adjacency (BIC score) or "lingam" for continuous weights.
    pop_size : int
        DE population size.
    max_steps : int
        Maximum DE iterations.
    n_samples : int
        Number of samples (required for "pc" mode if data is a correlation matrix).
    """
    mode = str(mode).strip().lower()
    dim = n_vars * n_vars

    if mode == "pc":
        prob = PCDiscoveryProblem(data, n_samples=(n_samples or 100), sparsity_lambda=0.5)
        initializer = IntegerMatrixInitializer(rows=n_vars, cols=n_vars, low=0, high=1)
        mutator = ContextGaussianMutation(base_sigma=0.25)
        repair = ClipRepair(low=0.0, high=1.0)
        cycle_weight = 1000.0
    elif mode == "lingam":
        prob = LiNGAMDiscoveryProblem(data, sparsity_lambda=0.1)
        wb = 2.0
        initializer = IntegerMatrixInitializer(rows=n_vars, cols=n_vars, low=int(-wb), high=int(wb))
        mutator = ContextGaussianMutation(base_sigma=0.3)
        repair = ClipRepair(low=-wb, high=wb)
        cycle_weight = 500.0
    else:
        raise ValueError(f"Unknown mode: {mode}. Use 'pc' or 'lingam'.")

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
        adj = np.asarray(x, dtype=float).reshape(n_vars, n_vars)
        np.fill_diagonal(adj, 0)
        return {"penalty": float(np.abs(adj).sum() * 10.0)}

    bias.add(CallableBias(name="sparsity", func=_sparsity, weight=1.0, mode="penalty"))

    solver = ComposableSolver(
        problem=prob,
        adapter=DifferentialEvolutionAdapter(DEConfig(batch_size=pop_size)),
        representation_pipeline=pipeline,
        bias_module=bias,
    )
    solver.set_max_steps(max_steps)
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


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        description="Causal Discovery via nsgablack DE optimization",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--mode", default="pc", choices=["pc", "lingam"], help="Discovery mode")
    p.add_argument("--n-vars", type=int, default=6, help="Number of variables")
    p.add_argument("--edge-prob", type=float, default=0.35, help="Edge probability in true DAG")
    p.add_argument("--pop-size", type=int, default=40, help="DE population size")
    p.add_argument("--max-steps", type=int, default=400, help="DE iterations")
    p.add_argument("--seed", type=int, default=42, help="Random seed")
    args = p.parse_args(argv)

    print(f"[causal-discovery] mode={args.mode}  n_vars={args.n_vars}  seed={args.seed}")
    print(f"[causal-discovery] pop_size={args.pop_size}  max_steps={args.max_steps}")

    W_true, data, corr = _generate_random_dag(
        args.n_vars, edge_prob=args.edge_prob, seed=args.seed
    )
    true_adj = (np.abs(W_true) > 1e-8).astype(float)
    n_edges_true = int(true_adj.sum())
    print(f"[causal-discovery] true DAG edges: {n_edges_true}")
    print(f"[causal-discovery] true adjacency:\n{true_adj.astype(int)}")

    if args.mode == "pc":
        solver_input = data
        solver_n_samples = data.shape[0]
    else:
        solver_input = data
        solver_n_samples = data.shape[0]

    t0 = time.perf_counter()
    solver = build_solver(
        solver_input,
        args.n_vars,
        mode=args.mode,
        pop_size=args.pop_size,
        max_steps=args.max_steps,
        n_samples=solver_n_samples,
    )
    solver.set_random_seed(args.seed)
    solver.run()
    elapsed = time.perf_counter() - t0

    best_x = solver.best_x
    if best_x is None:
        print("[causal-discovery] ERROR: solver returned no best_x")
        return

    est_adj = _adj_from_solution(best_x, args.n_vars, args.mode)
    est_adj_bin = (np.abs(est_adj) > 1e-8) if args.mode == "lingam" else est_adj
    shd = _shd(true_adj, est_adj_bin)
    n_edges_est = int(est_adj_bin.sum())

    edges_correct = int((true_adj * est_adj_bin).sum())
    edges_extra = n_edges_est - edges_correct
    edges_missed = n_edges_true - edges_correct

    print(f"[causal-discovery] recovered edges: {n_edges_est}")
    print(f"[causal-discovery] SHD: {shd}  (correct={edges_correct}  extra={edges_extra}  missed={edges_missed})")
    print(f"[causal-discovery] time: {elapsed:.2f}s")
    print(f"[causal-discovery] estimated adjacency:\n{est_adj_bin.astype(int)}")


if __name__ == "__main__":
    main()
