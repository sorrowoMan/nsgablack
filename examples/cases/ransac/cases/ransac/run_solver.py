# -*- coding: utf-8 -*-
"""RANSAC benchmark CLI for the canonical Case assembly."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from build_solver import build_solver  # noqa: E402
else:
    from .build_solver import build_solver

from nsgablack.project.scaffold import print_solver_check


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="RANSAC subset-search benchmark")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    from sklearn.datasets import make_regression
    from sklearn.linear_model import LinearRegression, RANSACRegressor
    from sklearn.model_selection import cross_val_score

    X, y = make_regression(n_samples=200, n_features=2, noise=5.0, random_state=args.seed)
    rng = np.random.default_rng(args.seed)
    y[rng.choice(200, 40, replace=False)] += rng.normal(0, 200, 40)
    solver = build_solver(X, y)
    solver.set_random_seed(args.seed)
    if args.check:
        print_solver_check(solver)
        return 0

    started = time.perf_counter()
    baseline = RANSACRegressor(random_state=args.seed).fit(X, y)
    baseline_time = time.perf_counter() - started
    started = time.perf_counter()
    solver.run()
    search_time = time.perf_counter() - started
    mask = (
        np.asarray(solver.best_x) > 0.5
        if solver.best_x is not None
        else np.ones(len(y), dtype=bool)
    )
    search_mse = -cross_val_score(
        LinearRegression(), X[mask], y[mask], cv=3, scoring="neg_mean_squared_error"
    ).mean()
    baseline_mse = -cross_val_score(
        LinearRegression(),
        X[baseline.inlier_mask_],
        y[baseline.inlier_mask_],
        cv=3,
        scoring="neg_mean_squared_error",
    ).mean()
    print(
        f"sklearn RANSAC: inliers={baseline.inlier_mask_.sum()}, "
        f"MSE={baseline_mse:.1f}, time={baseline_time:.3f}s"
    )
    print(f"nsgablack DE:   inliers={mask.sum()}, MSE={search_mse:.1f}, time={search_time:.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
