from __future__ import annotations

import numpy as np

from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.core.adapters import TrustRegionDFOAdapter
from nsgablack.representation import RepresentationPipeline, UniformInitializer, GaussianMutation, ClipRepair
from nsgablack.plugins import BenchmarkHarnessPlugin, ModuleReportPlugin, SurrogateEvaluationPlugin, SurrogateEvaluationConfig


class SmallExpensiveProblem:
    def __init__(self, dimension: int = 6):
        self.dimension = int(dimension)
        self.bounds = [(-4.0, 4.0)] * self.dimension

    def evaluate(self, x):
        x = np.asarray(x, dtype=float)
        base = float(np.sum(x * x))
        noise = float(np.random.normal(0.0, 0.1))
        return base + noise


def build_solver(model_type: str, run_id: str):
    problem = SmallExpensiveProblem(dimension=6)
    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=-4.0, high=4.0),
        mutator=GaussianMutation(sigma=0.3, low=-4.0, high=4.0),
        repair=ClipRepair(low=-4.0, high=4.0),
    )

    adapter = TrustRegionDFOAdapter()
    solver = ComposableSolver(problem=problem, adapter=adapter, representation_pipeline=pipeline)

    cfg = SurrogateEvaluationConfig(min_train_samples=20, topk_explore=8, topk_exploit=6)
    solver.add_plugin(SurrogateEvaluationPlugin(config=cfg, model_type=model_type))
    solver.add_plugin(BenchmarkHarnessPlugin(run_id=run_id))
    solver.add_plugin(ModuleReportPlugin())
    return solver


def main():
    for model_type in ("rf", "gb", "knn"):
        solver = build_solver(model_type=model_type, run_id=f"surrogate_model_{model_type}")
        result = solver.run(max_generations=25, seed=7)
        print(model_type, "status:", result.get("status"), "best:", result.get("best_objective"))


if __name__ == "__main__":
    main()

