"""AutoML: nsgablack DE searches model + hyperparams jointly."""
from __future__ import annotations
import sys, time, argparse
from pathlib import Path
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path: sys.path.insert(0, str(_THIS_DIR))
from _bootstrap import ensure_nsgablack_importable; ensure_nsgablack_importable(Path(__file__))
import numpy as np
from nsgablack.adapters import DEConfig, DifferentialEvolutionAdapter
from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.project.scaffold import print_solver_check
from nsgablack.representation import RepresentationPipeline
from nsgablack.representation.continuous import ClipRepair, ContextGaussianMutation, UniformInitializer
from problem.automl_problem import AutoMLProblem

def build_solver(X, y, *, pop_size=15, max_steps=40, resource_context=None, component_overrides=None):
    prob = AutoMLProblem(X, y)
    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=[0,0.01,2,0], high=[2.99,1.0,20,1]),
        mutator=ContextGaussianMutation(base_sigma=0.2, low=[0,0.01,2,0], high=[2.99,1.0,20,1]),
        repair=ClipRepair(low=[0,0.01,2,0], high=[2.99,1.0,20,1]))
    solver = ComposableSolver(problem=prob, adapter=DifferentialEvolutionAdapter(DEConfig(batch_size=pop_size)),
                              representation_pipeline=pipeline)
    solver.set_max_steps(max_steps); return solver

def main():
    p = argparse.ArgumentParser(); p.add_argument("--seed", type=int, default=42)
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    from sklearn.datasets import make_classification
    from sklearn.linear_model import LogisticRegression
    from sklearn.tree import DecisionTreeClassifier
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import cross_val_score
    models = [("lr", LogisticRegression(max_iter=500)), ("dt", DecisionTreeClassifier(max_depth=5)),
              ("rf", RandomForestClassifier(n_estimators=50))]
    X, y = make_classification(n_samples=300, n_features=10, n_informative=6, random_state=args.seed)
    solver = build_solver(X, y); solver.set_random_seed(args.seed)
    if args.check:
        print_solver_check(solver)
        return
    best_baseline = max(cross_val_score(m, X, y, cv=3, scoring='accuracy').mean() for _, m in models)
    t0 = time.perf_counter(); solver.run(); nsga_t = time.perf_counter()-t0
    best_x = solver.best_x
    best_acc = 1.0 - solver.problem.evaluate(best_x) if best_x is not None else 0
    best_model = models[int(best_x[0])][0] if best_x is not None else "?"
    print(f"Best single model: acc={best_baseline:.4f}")
    print(f"AutoML (DE):       acc={best_acc:.4f}, model={best_model}, time={nsga_t:.1f}s")

if __name__ == "__main__": main()
