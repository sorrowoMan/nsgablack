"""Anomaly Detection: nsgablack DE optimizes Isolation Forest / LOF hyperparameters.

Compares DE-optimized params against sklearn defaults on synthetic data with
labeled anomalies.  Uses ConstraintBias via BiasModule to enforce contamination
ratio bounds as a soft constraint alongside ClipRepair.

Pattern: RepresentationPipeline + ComposableSolver + DE + BiasModule(ConstraintBias)
"""

from __future__ import annotations

import sys
import time
import argparse
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))
from _bootstrap import ensure_nsgablack_importable

ensure_nsgablack_importable(Path(__file__))

import numpy as np
from sklearn.datasets import make_blobs
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.metrics import roc_auc_score

from nsgablack.adapters import DEConfig, DifferentialEvolutionAdapter
from nsgablack.bias.bias_module import BiasModule
from nsgablack.bias.domain.constraint import ConstraintBias
from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.project.scaffold import print_solver_check
from nsgablack.representation import RepresentationPipeline
from nsgablack.representation.continuous import (
    ClipRepair,
    ContextGaussianMutation,
    UniformInitializer,
)
from problem.isolation_forest_problem import LOFProblem, IsolationForestProblem


def generate_anomaly_data(n_samples=500, n_outliers=50, n_features=5, seed=42):
    rng = np.random.default_rng(seed)
    X_normal, centers = make_blobs(
        n_samples=n_samples - n_outliers,
        n_features=n_features,
        centers=3,
        cluster_std=1.0,
        random_state=seed,
    )
    n_near = max(0, n_outliers // 2)
    n_far = n_outliers - n_near
    if n_near > 0:
        center_ids = rng.integers(0, len(centers), size=n_near)
        base = np.asarray(centers)[center_ids].reshape(n_near, -1)
        X_near = base + rng.normal(0, 3.5, size=(n_near, n_features))
        X_far = rng.uniform(low=-10, high=10, size=(n_far, n_features))
        X = np.vstack([X_normal, X_near, X_far])
    else:
        X_far = rng.uniform(low=-10, high=10, size=(n_outliers, n_features))
        X = np.vstack([X_normal, X_far])
    y_true = np.zeros(len(X), dtype=int)
    y_true[-n_outliers:] = 1
    return X, y_true


def _build_lof_constraint_bias():
    """ConstraintBias enforcing LOF contamination in [0.01, 0.5]."""
    bias = ConstraintBias(weight=1.0, penalty_factor=100.0)

    def contamination_low(x: np.ndarray) -> float:
        return max(0.0, 0.01 - float(x[1]))

    def contamination_high(x: np.ndarray) -> float:
        return max(0.0, float(x[1]) - 0.5)

    bias.add_constraint(contamination_low, weight=1.0, constraint_type="hard")
    bias.add_constraint(contamination_high, weight=1.0, constraint_type="hard")
    return bias


def _build_iforest_constraint_bias():
    """ConstraintBias enforcing IForest params: max_samples/max_features in [0.1, 1.0]."""
    bias = ConstraintBias(weight=1.0, penalty_factor=100.0)

    def max_samples_low(x: np.ndarray) -> float:
        return max(0.0, 0.1 - float(x[1]))

    def max_samples_high(x: np.ndarray) -> float:
        return max(0.0, float(x[1]) - 1.0)

    def max_features_low(x: np.ndarray) -> float:
        return max(0.0, 0.1 - float(x[2]))

    def max_features_high(x: np.ndarray) -> float:
        return max(0.0, float(x[2]) - 1.0)

    bias.add_constraint(max_samples_low, weight=1.0, constraint_type="hard")
    bias.add_constraint(max_samples_high, weight=1.0, constraint_type="hard")
    bias.add_constraint(max_features_low, weight=1.0, constraint_type="hard")
    bias.add_constraint(max_features_high, weight=1.0, constraint_type="hard")
    return bias


def build_solver(*, resource_context=None, component_overrides=None):
    """Canonical scaffold entry: assemble LOF anomaly detection solver.

    Uses synthetic anomaly data by default.
    Override the problem via component_overrides={"problem": my_problem}.
    """
    overrides = dict(component_overrides or {})

    problem = overrides.get("problem")
    if problem is None:
        data, y_true = generate_anomaly_data()
        problem = LOFProblem(data, y_true)

    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=[5, 0.01], high=[100, 0.5]),
        mutator=ContextGaussianMutation(base_sigma=0.3, low=[5, 0.01], high=[100, 0.5]),
        repair=ClipRepair(low=[5, 0.01], high=[100, 0.5]),
    )

    constraint_bias = _build_lof_constraint_bias()
    bias_module = BiasModule()
    bias_module.add(constraint_bias)

    solver = ComposableSolver(
        problem=problem,
        adapter=DifferentialEvolutionAdapter(DEConfig(batch_size=30)),
        representation_pipeline=pipeline,
    )
    solver.set_bias_module(bias_module)
    solver.enable_bias_module()
    solver.set_resource_context(resource_context)
    return solver


def main():
    p = argparse.ArgumentParser(
        description="Anomaly Detection: DE-optimized hyperparams vs sklearn defaults",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--mode", choices=["lof", "iforest", "both"], default="both")
    p.add_argument("--pop-size", type=int, default=30)
    p.add_argument("--max-steps", type=int, default=80)
    p.add_argument("--n-samples", type=int, default=500)
    p.add_argument("--n-outliers", type=int, default=50)
    p.add_argument("--n-features", type=int, default=5)
    p.add_argument("--check", action="store_true")
    args = p.parse_args()

    X, y_true = generate_anomaly_data(
        n_samples=args.n_samples,
        n_outliers=args.n_outliers,
        n_features=args.n_features,
        seed=args.seed,
    )
    n_anomalies = int(y_true.sum())

    modes = ["lof", "iforest"] if args.mode == "both" else [args.mode]

    print("=" * 72)
    print("Anomaly Detection: nsgablack DE  vs  sklearn defaults")
    print("=" * 72)
    print(
        f"Data: {X.shape[0]} samples, {X.shape[1]} features, "
        f"{n_anomalies} anomalies  (seed={args.seed})"
    )
    print()

    results = {}

    for mode in modes:
        label = "LOF" if mode == "lof" else "Isolation Forest"

        # ---- nsgablack DE search ----
        print(f"[{label}]  DE searching optimal hyperparameters ...")
        if mode == "lof":
            prob = LOFProblem(X, y_true)
            pl = RepresentationPipeline(
                initializer=UniformInitializer(low=[5, 0.01], high=[100, 0.5]),
                mutator=ContextGaussianMutation(base_sigma=0.3, low=[5, 0.01], high=[100, 0.5]),
                repair=ClipRepair(low=[5, 0.01], high=[100, 0.5]),
            )
            cb = _build_lof_constraint_bias()
        else:
            prob = IsolationForestProblem(X, y_true)
            pl = RepresentationPipeline(
                initializer=UniformInitializer(low=[50, 0.1, 0.1], high=[500, 1.0, 1.0]),
                mutator=ContextGaussianMutation(base_sigma=0.3, low=[50, 0.1, 0.1], high=[500, 1.0, 1.0]),
                repair=ClipRepair(low=[50, 0.1, 0.1], high=[500, 1.0, 1.0]),
            )
            cb = _build_iforest_constraint_bias()

        bm = BiasModule()
        bm.add(cb)
        solver = ComposableSolver(
            problem=prob,
            adapter=DifferentialEvolutionAdapter(DEConfig(batch_size=args.pop_size)),
            representation_pipeline=pl,
        )
        solver.set_bias_module(bm)
        solver.enable_bias_module()
        solver.set_max_steps(args.max_steps)
        solver.set_random_seed(args.seed)
        if args.check:
            print(f"[check] mode={mode}")
            print_solver_check(solver)
            continue
        t0 = time.perf_counter()
        solver.run()
        nsga_t = time.perf_counter() - t0

        best_params = solver.best_x
        if best_params is None:
            print(f"  [skip] no best_x returned")
            continue

        if mode == "lof":
            k = max(2, int(round(float(best_params[0]))))
            cont = float(np.clip(best_params[1], 0.01, 0.5))
            model = LocalOutlierFactor(
                n_neighbors=k, contamination=cont, novelty=False
            )
            scores = -model.fit_predict(X).astype(float)
            score_vals = -model.negative_outlier_factor_
        else:
            n_est = max(10, int(round(float(best_params[0]))))
            max_s = float(np.clip(best_params[1], 0.1, 1.0))
            max_f = float(np.clip(best_params[2], 0.1, 1.0))
            model = IsolationForest(
                n_estimators=n_est,
                max_samples=max_s,
                max_features=max_f,
                random_state=args.seed,
            )
            score_vals = -model.fit(X).score_samples(X)

        auc = roc_auc_score(y_true, score_vals)
        results[mode] = {"params": best_params, "auc": auc, "time": nsga_t}

        if mode == "lof":
            param_str = f"n_neighbors={k}, contamination={cont:.3f}"
        else:
            param_str = (
                f"n_estimators={n_est}, max_samples={max_s:.3f}, "
                f"max_features={max_f:.3f}"
            )
        print(f"  DE best:   {param_str}")
        print(f"  ROC-AUC:   {auc:.4f}   time: {nsga_t:.2f}s")

        # ---- sklearn default baseline ----
        t0 = time.perf_counter()
        if mode == "lof":
            sk = LocalOutlierFactor(n_neighbors=20, contamination=0.1, novelty=False)
            sk_labels = sk.fit_predict(X)
            sk_scores = -sk.negative_outlier_factor_
        else:
            sk = IsolationForest(random_state=args.seed)
            sk_scores = -sk.fit(X).score_samples(X)
        sk_t = time.perf_counter() - t0
        sk_auc = roc_auc_score(y_true, sk_scores)
        results[f"{mode}_sklearn"] = {"auc": sk_auc, "time": sk_t}
        print(f"  sklearn:   ROC-AUC: {sk_auc:.4f}   time: {sk_t:.3f}s")
        print()

    if args.check:
        return

    # ---- comparison table ----
    print("=" * 72)
    print(f"{'Method':<38} {'ROC-AUC':>8}   {'Time':>8}")
    print("-" * 72)
    for mode in modes:
        r = results[mode]
        rs = results[f"{mode}_sklearn"]
        label = "LOF" if mode == "lof" else "IsolationForest"
        print(f"  nsgablack DE ({label:>14}):  {r['auc']:>8.4f} {r['time']:>7.2f}s")
        print(
            f"  sklearn default ({label:>8}):  {rs['auc']:>8.4f} {rs['time']:>7.3f}s"
        )
    print("=" * 72)


if __name__ == "__main__":
    main()
