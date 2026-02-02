from __future__ import annotations

import numpy as np

from nsgablack.core.solver import BlackBoxSolverNSGAII
from nsgablack.representation import RepresentationPipeline, UniformInitializer, GaussianMutation, ProjectionRepair
from nsgablack.bias import BiasModule, DynamicPenaltyBias
from nsgablack.utils.plugins import BenchmarkHarnessPlugin


class SimpleConstrainedProblem:
    """Minimize sum(x^2) with simplex constraint sum(x)=1 and x>=0."""

    def __init__(self, dimension: int = 5):
        self.dimension = int(dimension)
        self.bounds = [(0.0, 1.0)] * self.dimension

    def evaluate(self, x):
        x = np.asarray(x, dtype=float)
        return float(np.sum(x * x))

    def evaluate_constraints(self, x):
        x = np.asarray(x, dtype=float)
        # constraint: sum(x)=1 and x>=0 (repair enforces, but bias can still penalize drift)
        g_sum = abs(float(np.sum(x)) - 1.0)
        g_neg = float(np.sum(np.maximum(0.0, -x)))
        return np.array([g_sum, g_neg], dtype=float)


def build_solver():
    problem = SimpleConstrainedProblem(dimension=6)

    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=0.0, high=1.0),
        mutator=GaussianMutation(sigma=0.2, low=0.0, high=1.0),
        # Projection repair keeps x on simplex and nonnegative
        repair=ProjectionRepair(sum_target=1.0, nonnegative=True),
    )

    bias = BiasModule()

    def constraint_penalty(x, constraints, context):
        # constraints: [sum-violation, negative-violation]
        g_sum = float(constraints[0]) if len(constraints) > 0 else 0.0
        g_neg = float(constraints[1]) if len(constraints) > 1 else 0.0
        return {"penalty": g_sum + g_neg}

    # Dynamic penalty grows over generations
    bias.add(
        DynamicPenaltyBias(
            penalty_func=constraint_penalty,
            schedule="linear",
            start_scale=0.1,
            end_scale=2.0,
            max_generations=40,
        )
    )

    solver = BlackBoxSolverNSGAII(problem=problem, enable_bias=True)
    solver.representation_pipeline = pipeline
    solver.bias_module = bias
    solver.add_plugin(BenchmarkHarnessPlugin())
    return solver


def main():
    solver = build_solver()
    result = solver.run(max_generations=40, seed=7)
    print("运行状态:", result.get("status"))
    print("最优目标值:", result.get("best_objective"))
    print("最优解:", result.get("best_solution"))


if __name__ == "__main__":
    main()
