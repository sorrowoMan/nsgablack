# -*- coding: utf-8 -*-
"""Clustering benchmark CLI for the canonical Case assembly."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from build_solver import build_solver  # noqa: E402
else:
    from .build_solver import build_solver

from nsgablack.project.scaffold import print_solver_check


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Clustering benchmark")
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--n-samples", type=int, default=300)
    parser.add_argument("--n-features", type=int, default=2)
    parser.add_argument("--adapter", type=str, default="sa")
    parser.add_argument("--pop-size", type=int, default=20)
    parser.add_argument("--max-steps", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    from sklearn.cluster import KMeans
    from sklearn.datasets import make_blobs

    data, _ = make_blobs(
        n_samples=args.n_samples,
        n_features=args.n_features,
        centers=args.k,
        cluster_std=1.5,
        random_state=args.seed,
    )
    solver = build_solver(
        data=data,
        k=args.k,
        adapter=args.adapter,
        pop_size=args.pop_size,
        max_steps=args.max_steps,
    )
    solver.set_random_seed(args.seed)
    if args.check:
        print_solver_check(solver)
        return 0

    started = time.perf_counter()
    solver.run()
    search_time = time.perf_counter() - started
    best_x = solver.best_x
    search_sse = float(solver.problem.evaluate(best_x)) if best_x is not None else float("inf")

    started = time.perf_counter()
    baseline = KMeans(n_clusters=args.k, n_init=10, random_state=args.seed).fit(data)
    baseline_time = time.perf_counter() - started
    print(f"{'':-^50}")
    print(f"{'Method':<20} {'SSE':>12} {'Time(s)':>10}")
    print(f"{'':-^50}")
    print(f"{'nsgablack (' + args.adapter + ')':<20} {search_sse:>12.4f} {search_time:>10.4f}")
    print(f"{'sklearn KMeans':<20} {float(baseline.inertia_):>12.4f} {baseline_time:>10.4f}")
    print(f"{'':-^50}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
