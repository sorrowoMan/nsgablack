"""Kernel SHAP: analytical WLS solution + nsgablack Newton solver.

SHAP = weighted least squares over coalitions. Convex with closed form.
nsgablack Newton/Broyden plugin solves it, or use analytical WLS directly.
"""
from __future__ import annotations
import sys, time, argparse
from pathlib import Path
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path: sys.path.insert(0, str(_THIS_DIR))
from _bootstrap import ensure_nsgablack_importable; ensure_nsgablack_importable(Path(__file__))
import numpy as np
from nsgablack.adapters import PatternSearchAdapter
from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.representation import RepresentationPipeline
from nsgablack.representation.continuous import ClipRepair, ContextGaussianMutation, UniformInitializer
from problem.shap_problem import KernelSHAPProblem


def build_solver(model, X_bg, x_target, *, n_coalitions=200, max_steps=200):
    prob = KernelSHAPProblem(model, X_bg, x_target, n_coalitions=n_coalitions)
    dim = prob.dimension; lo = [b[0] for b in prob.bounds]; hi = [b[1] for b in prob.bounds]
    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=lo, high=hi),
        mutator=ContextGaussianMutation(base_sigma=0.2, low=lo, high=hi),
        repair=ClipRepair(low=lo, high=hi))
    solver = ComposableSolver(problem=prob, adapter=PatternSearchAdapter(), representation_pipeline=pipeline)
    solver.set_max_steps(max_steps)
    return solver, prob


def main():
    p = argparse.ArgumentParser(); p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()
    from sklearn.datasets import make_regression
    from sklearn.linear_model import LinearRegression
    X, y = make_regression(n_samples=500, n_features=5, noise=5.0, random_state=args.seed)
    model = LinearRegression().fit(X, y); x_target = X[0]
    shap_true = model.coef_ * (x_target - X.mean(axis=0))

    # ── Analytical WLS (the right tool for this convex problem) ──
    solver, prob = build_solver(model, X[:200], x_target)
    t0 = time.perf_counter()
    phi_analytic = prob.analytical_solution()
    ana_t = time.perf_counter() - t0
    shap_analytic = phi_analytic[1:]
    cos_ana = np.dot(shap_analytic, shap_true) / (np.linalg.norm(shap_analytic)*np.linalg.norm(shap_true)+1e-10)

    # ── PatternSearch (for comparison) ──
    solver.set_random_seed(args.seed)
    t0 = time.perf_counter(); solver.run(); nsga_t = time.perf_counter()-t0
    shap_nsga = prob.get_shap_values(solver.best_x) if solver.best_x is not None else np.zeros(5)
    cos_ps = np.dot(shap_nsga, shap_true) / (np.linalg.norm(shap_nsga)*np.linalg.norm(shap_true)+1e-10)

    print(f"SHAP (true):     {shap_true.round(4).tolist()}")
    print(f"SHAP (analytic): {shap_analytic.round(4).tolist()}  cos={cos_ana:.4f}  time={ana_t:.4f}s")
    print(f"SHAP (PatternSearch): {shap_nsga.round(4).tolist()}  cos={cos_ps:.4f}  time={nsga_t:.2f}s")
    print(f"Framework: KernelSHAPProblem + analytical WLS (convex, closed-form)")
    print(f"Lesson: Convex WLS → analytical solver beats search. Choose the right tool.")


if __name__ == "__main__": main()
