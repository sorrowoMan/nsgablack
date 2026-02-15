from __future__ import annotations

import numpy as np

from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.core.adapters import TrustRegionDFOAdapter
from nsgablack.representation import RepresentationPipeline, UniformInitializer, GaussianMutation, ClipRepair
from nsgablack.plugins import BenchmarkHarnessPlugin, ModuleReportPlugin, MultiFidelityEvaluationPlugin, MultiFidelityEvaluationConfig


class MultiFidelityProblem:
    def __init__(self, dimension: int = 8):
        self.dimension = int(dimension)
        self.bounds = [(-3.0, 3.0)] * self.dimension

    def evaluate(self, x):
        x = np.asarray(x, dtype=float)
        # high-fidelity
        return float(np.sum(x * x) + 0.05 * np.sin(np.sum(x)))

    def evaluate_low_fidelity(self, x):
        x = np.asarray(x, dtype=float)
        # cheaper/rougher proxy
        return float(np.sum(x * x))


def build_solver():
    problem = MultiFidelityProblem(dimension=8)
    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=-3.0, high=3.0),
        mutator=GaussianMutation(sigma=0.25, low=-3.0, high=3.0),
        repair=ClipRepair(low=-3.0, high=3.0),
    )

    adapter = TrustRegionDFOAdapter()
    solver = ComposableSolver(problem=problem, adapter=adapter, representation_pipeline=pipeline)

    cfg = MultiFidelityEvaluationConfig(min_high_fidelity=6, topk_exploit=6, topk_explore=6)
    solver.add_plugin(MultiFidelityEvaluationPlugin(config=cfg))
    solver.add_plugin(BenchmarkHarnessPlugin(run_id="multi_fidelity_demo"))
    solver.add_plugin(ModuleReportPlugin())
    return solver


def main():
    solver = build_solver()
    result = solver.run(max_generations=40, seed=7)
    print("����״̬:", result.get("status"))
    print("best_objective:", result.get("best_objective"))


if __name__ == "__main__":
    main()

