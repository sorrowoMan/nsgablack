"""AutoML: nsgablack DE searches model + hyperparams jointly."""
from __future__ import annotations
import numpy as np
from nsgablack.adapters import DEConfig, DifferentialEvolutionAdapter
from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.representation import RepresentationPipeline
from nsgablack.representation.continuous import ClipRepair, ContextGaussianMutation, UniformInitializer
from problem.automl_problem import AutoMLProblem

def build_solver(X=None, y=None, *, pop_size=15, max_steps=40, resource_context=None, component_overrides=None):
    overrides = dict(component_overrides or {})
    config = dict(overrides.pop("config", {}) or {})
    pop_size = int(config.pop("pop_size", pop_size))
    max_steps = int(config.pop("max_steps", max_steps))
    n_samples = int(config.pop("n_samples", 60))
    n_features = int(config.pop("n_features", 4))
    random_seed = int(config.pop("random_seed", 0))
    if config:
        raise ValueError("unsupported automl config overrides: " + str(sorted(config)))
    X = overrides.pop("X", X)
    y = overrides.pop("y", y)
    if X is None or y is None:
        rng = np.random.default_rng(random_seed)
        X = rng.normal(size=(n_samples, n_features))
        y = (X[:, 0] + 0.5 * X[:, 1] > 0.0).astype(int)
    prob = AutoMLProblem(X, y)
    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=[0,0.01,2,0], high=[2.99,1.0,20,1]),
        mutator=ContextGaussianMutation(base_sigma=0.2, low=[0,0.01,2,0], high=[2.99,1.0,20,1]),
        repair=ClipRepair(low=[0,0.01,2,0], high=[2.99,1.0,20,1]))
    solver = ComposableSolver(problem=prob, adapter=DifferentialEvolutionAdapter(DEConfig(batch_size=pop_size)),
                              representation_pipeline=pipeline)
    solver.set_max_steps(max_steps)
    from nsgablack.project import apply_solver_component_overrides
    apply_solver_component_overrides(solver, overrides)
    solver.set_resource_context(resource_context)
    return solver
