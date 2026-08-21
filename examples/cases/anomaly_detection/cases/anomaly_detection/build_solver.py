"""Anomaly Detection: nsgablack DE optimizes Isolation Forest / LOF hyperparameters.

Compares DE-optimized params against sklearn defaults on synthetic data with
labeled anomalies.  Uses ConstraintBias via BiasModule to enforce contamination
ratio bounds as a soft constraint alongside ClipRepair.

Pattern: RepresentationPipeline + ComposableSolver + DE + BiasModule(ConstraintBias)
"""

from __future__ import annotations

import numpy as np
from sklearn.datasets import make_blobs

from nsgablack.adapters import DEConfig, DifferentialEvolutionAdapter
from nsgablack.bias.bias_module import BiasModule
from nsgablack.bias.domain.constraint import ConstraintBias
from nsgablack.core.composable_solver import ComposableSolver
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


def build_solver(
    *,
    mode: str = "lof",
    pop_size: int = 30,
    max_steps: int = 80,
    resource_context=None,
    component_overrides=None,
):
    """Canonical scaffold entry for LOF or Isolation Forest search.

    Uses synthetic anomaly data by default.
    Override the problem via component_overrides={"problem": my_problem}.
    """
    overrides = dict(component_overrides or {})
    case_config = dict(overrides.pop("config", {}) or {})
    mode = str(case_config.pop("mode", mode))
    pop_size = int(case_config.pop("pop_size", pop_size))
    max_steps = int(case_config.pop("max_steps", max_steps))
    data_config = {
        "n_samples": int(case_config.pop("n_samples", 500)),
        "n_outliers": int(case_config.pop("n_outliers", 50)),
        "n_features": int(case_config.pop("n_features", 5)),
        "seed": int(case_config.pop("seed", 42)),
    }
    if case_config:
        raise ValueError(
            "unsupported anomaly_detection config overrides: "
            + str(sorted(case_config))
        )

    mode = str(mode).strip().lower()
    if mode not in {"lof", "iforest"}:
        raise ValueError("mode must be 'lof' or 'iforest'")

    problem = overrides.pop("problem", None)
    if problem is None:
        data, y_true = generate_anomaly_data(**data_config)
        problem = LOFProblem(data, y_true) if mode == "lof" else IsolationForestProblem(data, y_true)

    if mode == "lof":
        low, high = [5, 0.01], [100, 0.5]
        constraint_bias = _build_lof_constraint_bias()
    else:
        low, high = [50, 0.1, 0.1], [500, 1.0, 1.0]
        constraint_bias = _build_iforest_constraint_bias()
    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=low, high=high),
        mutator=ContextGaussianMutation(base_sigma=0.3, low=low, high=high),
        repair=ClipRepair(low=low, high=high),
    )

    bias_module = BiasModule()
    bias_module.add(constraint_bias)

    solver = ComposableSolver(
        problem=problem,
        adapter=DifferentialEvolutionAdapter(DEConfig(batch_size=pop_size)),
        representation_pipeline=pipeline,
    )
    solver.set_bias_module(bias_module)
    solver.enable_bias_module()
    solver.set_max_steps(max_steps)
    from nsgablack.project import apply_solver_component_overrides

    apply_solver_component_overrides(solver, overrides)
    solver.set_resource_context(resource_context)
    return solver
