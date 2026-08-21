# -*- coding: utf-8 -*-
"""Anomaly-detection benchmark CLI for the canonical Case assembly."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from build_solver import build_solver, generate_anomaly_data  # noqa: E402
    from problem.isolation_forest_problem import (  # noqa: E402
        IsolationForestProblem,
        LOFProblem,
    )
else:
    from .build_solver import build_solver, generate_anomaly_data
    from .problem.isolation_forest_problem import IsolationForestProblem, LOFProblem

from nsgablack.project.scaffold import print_solver_check


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Anomaly detection hyperparameter search")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--mode", choices=["lof", "iforest", "both"], default="both")
    parser.add_argument("--pop-size", type=int, default=30)
    parser.add_argument("--max-steps", type=int, default=80)
    parser.add_argument("--n-samples", type=int, default=500)
    parser.add_argument("--n-outliers", type=int, default=50)
    parser.add_argument("--n-features", type=int, default=5)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    from sklearn.ensemble import IsolationForest
    from sklearn.metrics import roc_auc_score
    from sklearn.neighbors import LocalOutlierFactor

    X, y_true = generate_anomaly_data(
        n_samples=args.n_samples,
        n_outliers=args.n_outliers,
        n_features=args.n_features,
        seed=args.seed,
    )
    modes = ["lof", "iforest"] if args.mode == "both" else [args.mode]
    results = {}
    for mode in modes:
        problem = LOFProblem(X, y_true) if mode == "lof" else IsolationForestProblem(X, y_true)
        solver = build_solver(
            mode=mode,
            pop_size=args.pop_size,
            max_steps=args.max_steps,
            component_overrides={"problem": problem},
        )
        solver.set_random_seed(args.seed)
        if args.check:
            print(f"[check] mode={mode}")
            print_solver_check(solver)
            continue

        started = time.perf_counter()
        solver.run()
        search_time = time.perf_counter() - started
        if solver.best_x is None:
            print(f"[{mode}] no best candidate")
            continue
        best = np.asarray(solver.best_x, dtype=float)
        if mode == "lof":
            neighbors = max(2, int(round(float(best[0]))))
            contamination = float(np.clip(best[1], 0.01, 0.5))
            fitted = LocalOutlierFactor(
                n_neighbors=neighbors,
                contamination=contamination,
                novelty=False,
            ).fit(X)
            scores = -fitted.negative_outlier_factor_
            baseline = LocalOutlierFactor(n_neighbors=20, contamination=0.1, novelty=False).fit(X)
            baseline_scores = -baseline.negative_outlier_factor_
        else:
            fitted = IsolationForest(
                n_estimators=max(10, int(round(float(best[0])))),
                max_samples=float(np.clip(best[1], 0.1, 1.0)),
                max_features=float(np.clip(best[2], 0.1, 1.0)),
                random_state=args.seed,
            ).fit(X)
            scores = -fitted.score_samples(X)
            baseline = IsolationForest(random_state=args.seed).fit(X)
            baseline_scores = -baseline.score_samples(X)
        results[mode] = (
            roc_auc_score(y_true, scores),
            roc_auc_score(y_true, baseline_scores),
            search_time,
        )

    if args.check:
        return 0
    for mode, (search_auc, baseline_auc, elapsed) in results.items():
        print(
            f"{mode}: nsgablack ROC-AUC={search_auc:.4f}, "
            f"sklearn default={baseline_auc:.4f}, time={elapsed:.2f}s"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
