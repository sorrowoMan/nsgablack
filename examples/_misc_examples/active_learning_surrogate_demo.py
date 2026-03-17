from __future__ import annotations

import numpy as np

from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.adapters import TrustRegionDFOAdapter
from nsgablack.representation import RepresentationPipeline, UniformInitializer, GaussianMutation, ClipRepair
from nsgablack.plugins import BenchmarkHarnessPlugin, ModuleReportPlugin, SurrogateEvaluationProviderPlugin, SurrogateEvaluationConfig


class ExpensiveProblem:
    def __init__(self, dimension: int = 8):
        self.dimension = int(dimension)
        self.bounds = [(-3.0, 3.0)] * self.dimension

    def evaluate(self, x):
        x = np.asarray(x, dtype=float)
        # simulate expensive/noisy evaluation
        base = float(np.sum(x * x))
        noise = float(np.random.normal(0.0, 0.05))
        return base + noise


def build_solver():
    problem = ExpensiveProblem(dimension=8)
    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=-3.0, high=3.0),
        mutator=GaussianMutation(sigma=0.25, low=-3.0, high=3.0),
        repair=ClipRepair(low=-3.0, high=3.0),
    )

    adapter = TrustRegionDFOAdapter()
    solver = ComposableSolver(problem=problem, adapter=adapter, representation_pipeline=pipeline)

    cfg = SurrogateEvaluationConfig(min_train_samples=24, topk_explore=12, topk_exploit=6, min_true_evals=6)
    solver.register_evaluation_provider(SurrogateEvaluationProviderPlugin(config=cfg).create_provider())
    solver.add_plugin(BenchmarkHarnessPlugin(run_id="active_learning_surrogate_demo"))
    solver.add_plugin(ModuleReportPlugin())
    return solver


def main():
    solver = build_solver()
    result = solver.run(max_generations=40, seed=7)
    print("杩愯鐘舵€?", result.get("status"))
    print("best_objective:", result.get("best_objective"))


if __name__ == "__main__":
    main()


