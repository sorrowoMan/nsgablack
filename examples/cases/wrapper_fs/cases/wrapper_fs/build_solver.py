"""Wrapper Feature Selection: nsgablack DE vs sklearn RFE."""
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
from problem.feature_selection_problem import FeatureSelectionProblem

def build_solver(X=None, y=None, estimator=None, *, pop_size=25, max_steps=80, sparsity_weight=50.0, resource_context=None, component_overrides=None):
    overrides = dict(component_overrides or {})
    X = overrides.get("X", X)
    y = overrides.get("y", y)
    estimator = overrides.get("estimator", estimator)
    from sklearn.linear_model import LinearRegression
    if X is None or y is None:
        rng = np.random.default_rng(0)
        X = rng.normal(size=(60, 6))
        y = 3.0 * X[:, 0] - 2.0 * X[:, 1] + rng.normal(0.0, 0.1, size=60)
    est = estimator or LinearRegression()
    prob = FeatureSelectionProblem(X, y, est); nf = prob.n_features
    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=[0]*nf, high=[1]*nf),
        mutator=ContextGaussianMutation(base_sigma=0.3, low=[0]*nf, high=[1]*nf),
        repair=ClipRepair(low=[0]*nf, high=[1]*nf))
    bias = BiasModule()
    def sparsity_pen(x, constraints, context):
        return {"penalty": float((np.asarray(x)>0.5).sum() * sparsity_weight)}
    bias.add(CallableBias(name="sparsity", func=sparsity_pen, weight=1.0, mode="penalty"))
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
    from sklearn.linear_model import LinearRegression
    from sklearn.model_selection import cross_val_score
    from sklearn.feature_selection import RFE
    X, y = make_regression(n_samples=300, n_features=10, noise=20.0, random_state=args.seed)
    rng = np.random.default_rng(args.seed)
    X_noise = rng.normal(0, 1, (300, 6)); X_full = np.hstack([X, X_noise]); n_features = X_full.shape[1]
    solver = build_solver(X_full, y); solver.set_random_seed(args.seed)
    if args.check:
        print_solver_check(solver)
        return
    t0 = time.perf_counter(); rfe = RFE(LinearRegression(), n_features_to_select=8).fit(X_full, y); rfe_t = time.perf_counter()-t0
    rfe_score = -cross_val_score(LinearRegression(), X_full[:, rfe.support_], y, cv=3, scoring='neg_mean_squared_error').mean()
    t0 = time.perf_counter(); solver.run(); nsga_t = time.perf_counter()-t0
    nsga_mask = (np.asarray(solver.best_x)>0.5).astype(int) if solver.best_x is not None else np.ones(n_features,dtype=int)
    nsga_score = -cross_val_score(LinearRegression(), X_full[:, nsga_mask.astype(bool)], y, cv=3, scoring='neg_mean_squared_error').mean()
    print(f"Total: {n_features} features (10 informative + 6 noise)")
    print(f"sklearn RFE:   {rfe.support_.sum()} feats, MSE={rfe_score:.2f}, time={rfe_t:.2f}s")
    print(f"nsgablack DE:  {nsga_mask.sum()} feats, MSE={nsga_score:.2f}, time={nsga_t:.2f}s")

if __name__ == "__main__": main()
