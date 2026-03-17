from __future__ import annotations

import numpy as np

from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.adapters import TrustRegionMODFOAdapter, TrustRegionMODFOConfig
from nsgablack.representation import RepresentationPipeline, UniformInitializer, GaussianMutation, ClipRepair
from nsgablack.plugins import ParetoArchivePlugin, BenchmarkHarnessPlugin, ModuleReportPlugin


class SimpleMOProblem:
    def __init__(self, dimension: int = 6):
        self.dimension = int(dimension)
        self.bounds = [(-2.0, 2.0)] * self.dimension

    def evaluate(self, x):
        x = np.asarray(x, dtype=float)
        f1 = float(np.sum(x * x))
        f2 = float(np.sum((x - 1.0) ** 2))
        return np.array([f1, f2], dtype=float)


def build_solver():
    problem = SimpleMOProblem(dimension=6)
    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=-2.0, high=2.0),
        mutator=GaussianMutation(sigma=0.2, low=-2.0, high=2.0),
        repair=ClipRepair(low=-2.0, high=2.0),
    )

    adapter = TrustRegionMODFOAdapter(TrustRegionMODFOConfig(batch_size=18))
    solver = ComposableSolver(problem=problem, adapter=adapter, representation_pipeline=pipeline)
    solver.add_plugin(ParetoArchivePlugin())
    solver.add_plugin(BenchmarkHarnessPlugin(run_id="trust_region_mo_dfo_demo"))
    solver.add_plugin(ModuleReportPlugin())
    return solver


def main():
    solver = build_solver()
    result = solver.run(max_generations=40, seed=7)
    print("运行状态:", result.get("status"))
    print("best_objective:", result.get("best_objective"))


if __name__ == "__main__":
    main()


