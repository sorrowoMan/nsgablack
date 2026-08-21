"""RANSAC: nsgablack DE vs sklearn RANSACRegressor."""
from __future__ import annotations
import numpy as np
from nsgablack.adapters import DEConfig, DifferentialEvolutionAdapter
from nsgablack.bias import BiasModule
from nsgablack.bias.domain import CallableBias
from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.representation import RepresentationPipeline
from nsgablack.representation.continuous import ClipRepair, ContextGaussianMutation, UniformInitializer
from problem.ransac_problem import RANSACProblem

def build_solver(X=None, y=None, *, pop_size=30, max_steps=100, resource_context=None, component_overrides=None):
    overrides = dict(component_overrides or {})
    config = dict(overrides.pop("config", {}) or {})
    pop_size = int(config.pop("pop_size", pop_size))
    max_steps = int(config.pop("max_steps", max_steps))
    if config:
        raise ValueError("unsupported ransac config overrides: " + str(sorted(config)))
    X = overrides.pop("X", X)
    y = overrides.pop("y", y)
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
    from nsgablack.project import apply_solver_component_overrides
    apply_solver_component_overrides(solver, overrides)
    solver.set_resource_context(resource_context)
    return solver
