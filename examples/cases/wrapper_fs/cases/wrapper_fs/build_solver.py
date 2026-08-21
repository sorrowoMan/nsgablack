"""Wrapper Feature Selection: nsgablack DE vs sklearn RFE."""
from __future__ import annotations
import numpy as np
from nsgablack.adapters import DEConfig, DifferentialEvolutionAdapter
from nsgablack.bias import BiasModule
from nsgablack.bias.domain import CallableBias
from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.representation import RepresentationPipeline
from nsgablack.representation.continuous import ClipRepair, ContextGaussianMutation, UniformInitializer
from problem.feature_selection_problem import FeatureSelectionProblem

def build_solver(X=None, y=None, estimator=None, *, pop_size=25, max_steps=80, sparsity_weight=50.0, resource_context=None, component_overrides=None):
    overrides = dict(component_overrides or {})
    config = dict(overrides.pop("config", {}) or {})
    pop_size = int(config.pop("pop_size", pop_size))
    max_steps = int(config.pop("max_steps", max_steps))
    sparsity_weight = float(config.pop("sparsity_weight", sparsity_weight))
    if config:
        raise ValueError("unsupported wrapper_fs config overrides: " + str(sorted(config)))
    X = overrides.pop("X", X)
    y = overrides.pop("y", y)
    estimator = overrides.pop("estimator", estimator)
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
    from nsgablack.project import apply_solver_component_overrides
    apply_solver_component_overrides(solver, overrides)
    solver.set_resource_context(resource_context)
    return solver
