# -*- coding: utf-8 -*-
"""Causal-discovery CLI for the canonical Case assembly."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from build_solver import (  # noqa: E402
        _adj_from_solution,
        _generate_random_dag,
        _shd,
        build_solver,
    )
    from problem.causal_discovery_problem import (  # noqa: E402
        LiNGAMDiscoveryProblem,
        PCDiscoveryProblem,
    )
else:
    from .build_solver import _adj_from_solution, _generate_random_dag, _shd, build_solver
    from .problem.causal_discovery_problem import LiNGAMDiscoveryProblem, PCDiscoveryProblem

from nsgablack.project.scaffold import print_solver_check


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Causal discovery via optimization")
    parser.add_argument("--mode", default="pc", choices=["pc", "lingam"])
    parser.add_argument("--n-vars", type=int, default=6)
    parser.add_argument("--edge-prob", type=float, default=0.35)
    parser.add_argument("--pop-size", type=int, default=40)
    parser.add_argument("--max-steps", type=int, default=400)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    weights, data, _ = _generate_random_dag(
        args.n_vars,
        edge_prob=args.edge_prob,
        seed=args.seed,
    )
    true_adjacency = (np.abs(weights) > 1e-8).astype(float)
    problem = (
        PCDiscoveryProblem(data, n_samples=data.shape[0], sparsity_lambda=0.5)
        if args.mode == "pc"
        else LiNGAMDiscoveryProblem(data, sparsity_lambda=0.1)
    )
    solver = build_solver(
        mode=args.mode,
        n_vars=args.n_vars,
        pop_size=args.pop_size,
        max_steps=args.max_steps,
        random_seed=args.seed,
        component_overrides={"problem": problem},
    )
    if args.check:
        print_solver_check(solver)
        return 0

    started = time.perf_counter()
    solver.run()
    elapsed = time.perf_counter() - started
    if solver.best_x is None:
        print("[causal-discovery] no best candidate")
        return 1
    estimated = _adj_from_solution(solver.best_x, args.n_vars, args.mode)
    estimated_binary = (np.abs(estimated) > 1e-8).astype(float)
    correct = int((true_adjacency * estimated_binary).sum())
    print(f"[causal-discovery] true edges: {int(true_adjacency.sum())}")
    print(f"[causal-discovery] recovered edges: {int(estimated_binary.sum())}")
    print(f"[causal-discovery] SHD: {_shd(true_adjacency, estimated_binary)}")
    print(f"[causal-discovery] correct edges: {correct}")
    print(f"[causal-discovery] time: {elapsed:.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
