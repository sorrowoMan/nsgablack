# -*- coding: utf-8 -*-
"""Feature-selection benchmark CLI for the canonical Case assembly."""

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
    parser = argparse.ArgumentParser(description="Wrapper feature-selection benchmark")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    from sklearn.datasets import make_regression
    from sklearn.feature_selection import RFE
    from sklearn.linear_model import LinearRegression
    from sklearn.model_selection import cross_val_score

    X, y = make_regression(n_samples=300, n_features=10, noise=20.0, random_state=args.seed)
    rng = np.random.default_rng(args.seed)
    X_full = np.hstack([X, rng.normal(0, 1, (300, 6))])
    n_features = X_full.shape[1]
    solver = build_solver(X_full, y)
    solver.set_random_seed(args.seed)
    if args.check:
        print_solver_check(solver)
        return 0

    started = time.perf_counter()
    rfe = RFE(LinearRegression(), n_features_to_select=8).fit(X_full, y)
    rfe_time = time.perf_counter() - started
    rfe_score = -cross_val_score(
        LinearRegression(), X_full[:, rfe.support_], y, cv=3, scoring="neg_mean_squared_error"
    ).mean()
    started = time.perf_counter()
    solver.run()
    search_time = time.perf_counter() - started
    mask = (
        (np.asarray(solver.best_x) > 0.5).astype(int)
        if solver.best_x is not None
        else np.ones(n_features, dtype=int)
    )
    search_score = -cross_val_score(
        LinearRegression(), X_full[:, mask.astype(bool)], y, cv=3, scoring="neg_mean_squared_error"
    ).mean()
    print(f"Total: {n_features} features (10 informative + 6 noise)")
    print(f"sklearn RFE:   {rfe.support_.sum()} feats, MSE={rfe_score:.2f}, time={rfe_time:.2f}s")
    print(f"nsgablack DE:  {mask.sum()} feats, MSE={search_score:.2f}, time={search_time:.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
