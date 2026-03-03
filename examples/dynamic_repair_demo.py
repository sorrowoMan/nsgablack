from __future__ import annotations

import numpy as np

from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.adapters import TrustRegionDFOAdapter
from nsgablack.representation import RepresentationPipeline, UniformInitializer, GaussianMutation, ClipRepair, DynamicRepair
from nsgablack.plugins import BenchmarkHarnessPlugin, ModuleReportPlugin


class SimpleProblem:
    def __init__(self, dimension: int = 6):
        self.dimension = int(dimension)
        self.bounds = [(-2.0, 2.0)] * self.dimension

    def evaluate(self, x):
        x = np.asarray(x, dtype=float)
        return float(np.sum(x * x))


def build_solver():
    problem = SimpleProblem(dimension=6)
    # two-stage repair: early clip wide, later clip tighter
    repair_stage1 = ClipRepair(low=-2.0, high=2.0)
    repair_stage2 = ClipRepair(low=-1.0, high=1.0)

    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=-2.0, high=2.0),
        mutator=GaussianMutation(sigma=0.3, low=-2.0, high=2.0),
        repair=DynamicRepair([(0, repair_stage1), (20, repair_stage2)]),
    )

    adapter = TrustRegionDFOAdapter()
    solver = ComposableSolver(problem=problem, adapter=adapter, representation_pipeline=pipeline)
    solver.add_plugin(BenchmarkHarnessPlugin(run_id="dynamic_repair_demo"))
    solver.add_plugin(ModuleReportPlugin())
    return solver


def main():
    solver = build_solver()
    result = solver.run(max_generations=40, seed=7)
    print("运行状态:", result.get("status"))
    print("best_objective:", result.get("best_objective"))


if __name__ == "__main__":
    main()

