"""Canonical CLI for the Kernel SHAP optimization Case."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

from blackbase.project import load_resource_context_from_env, print_resource_context_summary
from nsgablack.project.scaffold import print_solver_check

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from build_solver import build_solver  # noqa: E402
else:
    from .build_solver import build_solver


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run the Kernel SHAP optimization Case.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--steps", type=int, default=200)
    parser.add_argument("--check", action="store_true", help="Build and validate only; do not optimize")
    args = parser.parse_args(argv)

    from sklearn.datasets import make_regression
    from sklearn.linear_model import LinearRegression

    X, y = make_regression(n_samples=500, n_features=5, noise=5.0, random_state=args.seed)
    model = LinearRegression().fit(X, y)
    x_target = X[0]
    shap_true = model.coef_ * (x_target - X.mean(axis=0))
    resource_context = load_resource_context_from_env("nsgablack")
    solver = build_solver(
        model,
        X[:200],
        x_target,
        max_steps=max(1, int(args.steps)),
        resource_context=resource_context,
    )
    if args.check:
        print_solver_check(solver)
        return 0

    print_resource_context_summary(resource_context)
    problem = solver.problem
    started = time.perf_counter()
    phi_analytic = problem.analytical_solution()
    analytical_seconds = time.perf_counter() - started
    shap_analytic = phi_analytic[1:]
    cos_analytic = np.dot(shap_analytic, shap_true) / (
        np.linalg.norm(shap_analytic) * np.linalg.norm(shap_true) + 1e-10
    )

    solver.set_random_seed(args.seed)
    started = time.perf_counter()
    solver.run()
    search_seconds = time.perf_counter() - started
    shap_search = problem.get_shap_values(solver.best_x) if solver.best_x is not None else np.zeros(5)
    cos_search = np.dot(shap_search, shap_true) / (
        np.linalg.norm(shap_search) * np.linalg.norm(shap_true) + 1e-10
    )

    print(f"SHAP (true): {shap_true.round(4).tolist()}")
    print(
        f"SHAP (analytic): {shap_analytic.round(4).tolist()} "
        f"cos={cos_analytic:.4f} time={analytical_seconds:.4f}s"
    )
    print(
        f"SHAP (PatternSearch): {shap_search.round(4).tolist()} "
        f"cos={cos_search:.4f} time={search_seconds:.2f}s"
    )
    print("Framework: KernelSHAPProblem + analytical WLS (convex, closed-form)")
    print("Lesson: convex WLS is solved best analytically; search remains a comparison path.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
