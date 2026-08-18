"""RANSAC: nsgablack DE vs sklearn RANSACRegressor."""
from __future__ import annotations
import sys, time, argparse
from pathlib import Path
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path: sys.path.insert(0, str(_THIS_DIR))
from _bootstrap import ensure_nsgablack_importable; ensure_nsgablack_importable(Path(__file__))

import numpy as np
from nsgablack.adapters import DEConfig, DifferentialEvolutionAdapter
from nsgablack.bias import BiasModule
from nsgablack.bias.domain import CallableBias
from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.project.scaffold import print_solver_check
from nsgablack.representation import RepresentationPipeline
from nsgablack.representation.continuous import ClipRepair, ContextGaussianMutation, UniformInitializer
from problem.ransac_problem import RANSACProblem

def build_solver(X=None, y=None, *, pop_size=30, max_steps=100, resource_context=None, component_overrides=None):
    overrides = dict(component_overrides or {})
    X = overrides.get("X", X)
    y = overrides.get("y", y)
    if X is None or y is None:
        rng = np.random.default_rng(0)
        X = rng.normal(size=(40, 2))
        y = 2.0 * X[:, 0] - X[:, 1] + rng.normal(0.0, 0.1, size=40)
    prob = RANSACProblem(X, y); n = prob.n_samples
    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=[0]*n, high=[1]*n),
        mutator=ContextGaussianMutation(base_sigma=0.25, low=[0]*n, high=[1]*n),
        repair=ClipRepair(low=[0]*n, high=[1]*n))
    bias = BiasModule()
    def inlier_count(x, constraints, context):
        n_in = max((np.asarray(x)>0.5).sum(), 1)
        return {"penalty": float(100.0/n_in)}
    bias.add(CallableBias(name="inlier_ratio", func=inlier_count, weight=1.0, mode="penalty"))
    solver = ComposableSolver(problem=prob, adapter=DifferentialEvolutionAdapter(DEConfig(batch_size=pop_size)),
                              representation_pipeline=pipeline, bias_module=bias)
    solver.set_max_steps(max_steps)
    solver.set_resource_context(resource_context)
    return solver

def main():
    p = argparse.ArgumentParser(); p.add_argument("--seed", type=int, default=42)
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    from sklearn.datasets import make_regression
    from sklearn.linear_model import RANSACRegressor, LinearRegression
    X, y = make_regression(n_samples=200, n_features=2, noise=5.0, random_state=args.seed)
    rng = np.random.default_rng(args.seed)
    y[rng.choice(200, 40, replace=False)] += rng.normal(0, 200, 40)
    solver = build_solver(X, y); solver.set_random_seed(args.seed)
    if args.check:
        print_solver_check(solver)
        return
    t0 = time.perf_counter(); sk = RANSACRegressor(random_state=args.seed).fit(X, y); sk_t = time.perf_counter()-t0
    t0 = time.perf_counter(); solver.run(); nsga_t = time.perf_counter()-t0
    nsga_mask = (np.asarray(solver.best_x)>0.5) if solver.best_x is not None else np.ones(len(y),dtype=bool)
    from sklearn.model_selection import cross_val_score
    nsga_mse = -cross_val_score(LinearRegression(), X[nsga_mask], y[nsga_mask], cv=3, scoring='neg_mean_squared_error').mean()
    sk_mse = -cross_val_score(LinearRegression(), X[sk.inlier_mask_], y[sk.inlier_mask_], cv=3, scoring='neg_mean_squared_error').mean()
    print(f"sklearn RANSAC: inliers={sk.inlier_mask_.sum()}, MSE={sk_mse:.1f}, time={sk_t:.3f}s")
    print(f"nsgablack DE:   inliers={nsga_mask.sum()}, MSE={nsga_mse:.1f}, time={nsga_t:.2f}s")

if __name__ == "__main__": main()
