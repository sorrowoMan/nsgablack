"""Canonical assembly for the Kernel SHAP optimization Case."""

from __future__ import annotations

from collections.abc import Mapping
import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))
from _bootstrap import ensure_nsgablack_importable

ensure_nsgablack_importable(Path(__file__))

from nsgablack.adapters import PatternSearchAdapter
from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.representation import RepresentationPipeline
from nsgablack.representation.continuous import ClipRepair, ContextGaussianMutation, UniformInitializer
from problem.shap_problem import KernelSHAPProblem


def build_solver(
    model=None,
    X_bg=None,
    x_target=None,
    *,
    config=None,
    n_coalitions=200,
    max_steps=200,
    resource_context=None,
    component_overrides=None,
):
    """Build exactly one solver; default data keeps the assembly independently checkable."""

    payload = dict(config or {}) if isinstance(config, Mapping) else {}
    overrides = dict(component_overrides or {})
    seed = int(payload.get("seed", 42))
    if model is None or X_bg is None or x_target is None:
        from sklearn.datasets import make_regression
        from sklearn.linear_model import LinearRegression

        X, y = make_regression(n_samples=500, n_features=5, noise=5.0, random_state=seed)
        model = LinearRegression().fit(X, y)
        X_bg = X[:200]
        x_target = X[0]

    n_coalitions = int(payload.get("n_coalitions", n_coalitions))
    max_steps = int(payload.get("max_steps", max_steps))
    problem = KernelSHAPProblem(model, X_bg, x_target, n_coalitions=n_coalitions)
    lower = [bound[0] for bound in problem.bounds]
    upper = [bound[1] for bound in problem.bounds]
    pipeline = overrides.get("representation_pipeline") or RepresentationPipeline(
        initializer=UniformInitializer(low=lower, high=upper),
        mutator=ContextGaussianMutation(base_sigma=0.2, low=lower, high=upper),
        repair=ClipRepair(low=lower, high=upper),
    )
    adapter = overrides.get("adapter") or PatternSearchAdapter()
    solver = ComposableSolver(problem=problem, adapter=adapter, representation_pipeline=pipeline)
    solver.set_max_steps(max_steps)
    solver.set_resource_context(resource_context)
    return solver
