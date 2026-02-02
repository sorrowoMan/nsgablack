from __future__ import annotations

import numpy as np

from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.core.adapters import TrustRegionDFOAdapter
from nsgablack.representation import RepresentationPipeline, UniformInitializer, GaussianMutation, ClipRepair
from nsgablack.bias import BiasModule, RiskBias
from nsgablack.utils.plugins import BenchmarkHarnessPlugin, ModuleReportPlugin, MonteCarloEvaluationPlugin, MonteCarloEvaluationConfig


class RiskyProblem:
    def __init__(self, dimension: int = 6):
        self.dimension = int(dimension)
        self.bounds = [(-2.0, 2.0)] * self.dimension

    def evaluate(self, x):
        x = np.asarray(x, dtype=float)
        base = float(np.sum(x * x))
        noise = float(np.random.normal(0.0, 0.2))
        return base + noise


def build_solver():
    problem = RiskyProblem(dimension=6)
    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=-2.0, high=2.0),
        mutator=GaussianMutation(sigma=0.3, low=-2.0, high=2.0),
        repair=ClipRepair(low=-2.0, high=2.0),
    )

    adapter = TrustRegionDFOAdapter()
    solver = ComposableSolver(problem=problem, adapter=adapter, representation_pipeline=pipeline)

    bias = BiasModule()
    bias.add(RiskBias(mode="cvar", alpha=0.2, weight=0.3))
    solver.bias_module = bias
    solver.enable_bias = True

    solver.add_plugin(MonteCarloEvaluationPlugin(MonteCarloEvaluationConfig(mc_samples=12, reduce="mean")))
    solver.add_plugin(BenchmarkHarnessPlugin(run_id="risk_bias_demo"))
    solver.add_plugin(ModuleReportPlugin())
    return solver


def main():
    solver = build_solver()
    result = solver.run(max_generations=40, seed=7)
    print("运行状态:", result.get("status"))
    print("best_objective:", result.get("best_objective"))


if __name__ == "__main__":
    main()
