from __future__ import annotations

import numpy as np

from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.adapters import TrustRegionSubspaceAdapter, TrustRegionSubspaceConfig
from nsgablack.representation import RepresentationPipeline, UniformInitializer, GaussianMutation, ClipRepair
from nsgablack.plugins import BenchmarkHarnessPlugin, ModuleReportPlugin


class HighDimProblem:
    def __init__(self, dimension: int = 20):
        self.dimension = int(dimension)
        self.bounds = [(-5.0, 5.0)] * self.dimension

    def evaluate(self, x):
        x = np.asarray(x, dtype=float)
        return float(np.sum(x * x))


def build_solver():
    problem = HighDimProblem(dimension=20)
    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=-5.0, high=5.0),
        mutator=GaussianMutation(sigma=0.3, low=-5.0, high=5.0),
        repair=ClipRepair(low=-5.0, high=5.0),
    )

    adapter = TrustRegionSubspaceAdapter(
        TrustRegionSubspaceConfig(subspace_dim=6, batch_size=16, basis_method="pca", min_samples=16)
    )
    solver = ComposableSolver(problem=problem, adapter=adapter, representation_pipeline=pipeline)
    solver.add_plugin(BenchmarkHarnessPlugin(run_id="trust_region_subspace_frontier_demo"))
    solver.add_plugin(ModuleReportPlugin())
    return solver


def main():
    solver = build_solver()
    result = solver.run(max_generations=40, seed=7)
    print("运行状态:", result.get("status"))
    print("best_objective:", result.get("best_objective"))


if __name__ == "__main__":
    main()


