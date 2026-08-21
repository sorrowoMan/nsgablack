# -*- coding: utf-8 -*-
"""AutoML benchmark CLI for the canonical Case assembly."""

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
    parser = argparse.ArgumentParser(description="AutoML search benchmark")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--samples", type=int, default=300)
    parser.add_argument("--features", type=int, default=10)
    parser.add_argument("--pop-size", type=int, default=15)
    parser.add_argument("--max-steps", type=int, default=40)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    from sklearn.datasets import make_classification
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import cross_val_score
    from sklearn.tree import DecisionTreeClassifier

    models = [
        ("lr", LogisticRegression(max_iter=500)),
        ("dt", DecisionTreeClassifier(max_depth=5)),
        ("rf", RandomForestClassifier(n_estimators=50)),
    ]
    X, y = make_classification(
        n_samples=max(40, int(args.samples)),
        n_features=max(4, int(args.features)),
        n_informative=max(2, min(int(args.features) - 2, int(args.features * 0.6))),
        random_state=args.seed,
    )
    solver = build_solver(X, y, pop_size=args.pop_size, max_steps=args.max_steps)
    solver.set_random_seed(args.seed)
    if args.check:
        print_solver_check(solver)
        return 0

    best_baseline = max(
        cross_val_score(model, X, y, cv=3, scoring="accuracy").mean()
        for _, model in models
    )
    started = time.perf_counter()
    solver.run()
    elapsed = time.perf_counter() - started
    best_x = solver.best_x
    best_acc = 1.0 - solver.problem.evaluate(best_x) if best_x is not None else 0
    best_model = models[int(best_x[0])][0] if best_x is not None else "?"
    print(f"Best single model: acc={best_baseline:.4f}")
    print(f"AutoML (DE):       acc={best_acc:.4f}, model={best_model}, time={elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
