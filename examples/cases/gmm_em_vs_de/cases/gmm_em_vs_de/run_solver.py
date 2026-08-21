# -*- coding: utf-8 -*-
"""GMM benchmark CLI for the canonical Case assembly."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from build_solver import build_solver  # noqa: E402
    from problem.gmm_problem import GMMProblem  # noqa: E402
else:
    from .build_solver import build_solver
    from .problem.gmm_problem import GMMProblem

from nsgablack.project.scaffold import print_solver_check


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="GMM DE-to-VNS benchmark")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--pop-size", type=int, default=30)
    parser.add_argument("--max-steps", type=int, default=300)
    parser.add_argument("--n-samples", type=int, default=300)
    parser.add_argument("--n-features", type=int, default=2)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    from sklearn.datasets import make_blobs
    from sklearn.mixture import GaussianMixture

    X, _ = make_blobs(
        n_samples=args.n_samples,
        n_features=args.n_features,
        centers=args.k,
        cluster_std=1.0,
        random_state=args.seed,
    )
    solver = build_solver(
        pop_size=args.pop_size,
        max_steps=args.max_steps,
        component_overrides={"problem": GMMProblem(X, k=args.k)},
    )
    solver.set_random_seed(args.seed)
    if args.check:
        print_solver_check(solver)
        return 0

    started = time.perf_counter()
    baseline = GaussianMixture(
        n_components=args.k,
        covariance_type="diag",
        random_state=args.seed,
        n_init=3,
    ).fit(X)
    baseline_time = time.perf_counter() - started
    baseline_nll = -baseline.score(X) * X.shape[0]
    started = time.perf_counter()
    solver.run()
    search_time = time.perf_counter() - started
    search_nll = (
        float(solver.best_objective)
        if solver.best_objective is not None
        else float("inf")
    )
    print(f"GMM  k={args.k}  n={X.shape[0]}  d={X.shape[1]}  dimension={solver.problem.dimension}")
    print(f"sklearn EM        NLL={baseline_nll:.3f}  time={baseline_time:.3f}s")
    print(f"nsgablack DE→VNS  NLL={search_nll:.3f}  time={search_time:.2f}s")
    if search_nll < float("inf") and baseline_nll < float("inf"):
        print(f"ratio (DE→VNS/EM) = {search_nll / max(baseline_nll, 1e-10):.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
