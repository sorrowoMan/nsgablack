from __future__ import annotations

import numpy as np

from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.core.adapters import VNSAdapter
from nsgablack.representation import RepresentationPipeline, UniformInitializer, GaussianMutation, ClipRepair, ContextGaussianMutation
from nsgablack.plugins import BenchmarkHarnessPlugin, ModuleReportPlugin, SurrogateEvaluationPlugin, SurrogateEvaluationConfig


class SphereProblem:
    def __init__(self, dimension: int = 10):
        self.dimension = int(dimension)
        self.bounds = [(-5.0, 5.0)] * self.dimension

    def evaluate(self, x):
        x = np.asarray(x, dtype=float)
        return float(np.sum(x * x))


def build_solver():
    problem = SphereProblem(dimension=10)
    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=-5.0, high=5.0),
        mutator=ContextGaussianMutation(base_sigma=0.4, low=-5.0, high=5.0),
        repair=ClipRepair(low=-5.0, high=5.0),
    )

    adapter = VNSAdapter()
    solver = ComposableSolver(problem=problem, adapter=adapter, representation_pipeline=pipeline)

    cfg = SurrogateEvaluationConfig(min_train_samples=30, topk_exploit=8, topk_explore=8, min_true_evals=6)
    solver.add_plugin(SurrogateEvaluationPlugin(config=cfg, model_type="rf"))
    solver.add_plugin(BenchmarkHarnessPlugin(run_id="surrogate_assisted_ea_demo"))
    solver.add_plugin(ModuleReportPlugin())
    return solver


def main():
    solver = build_solver()
    result = solver.run(max_generations=40, seed=7)
    print("运行状态:", result.get("status"))
    print("best_objective:", result.get("best_objective"))


if __name__ == "__main__":
    main()


