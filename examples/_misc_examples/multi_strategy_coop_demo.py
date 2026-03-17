"""Multi-strategy cooperation demo (VNS + SA, direct wiring)."""

import numpy as np

try:
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import (
        StrategyRouterAdapter,
        SAConfig,
        SimulatedAnnealingAdapter,
        StrategySpec,
        VNSAdapter,
        VNSConfig,
    )
    from nsgablack.plugins import ParetoArchivePlugin
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import ClipRepair, ContextGaussianMutation, UniformInitializer
except ModuleNotFoundError:  # pragma: no cover
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import (
        StrategyRouterAdapter,
        SAConfig,
        SimulatedAnnealingAdapter,
        StrategySpec,
        VNSAdapter,
        VNSConfig,
    )
    from nsgablack.plugins import ParetoArchivePlugin
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import ClipRepair, ContextGaussianMutation, UniformInitializer


class SphereProblem(BlackBoxProblem):
    def __init__(self, dim=6, low=-5.0, high=5.0):
        super().__init__(name="Sphere", dimension=dim, bounds={f"x{i}": (low, high) for i in range(dim)})
        self.low = low
        self.high = high

    def evaluate(self, x):
        x = np.asarray(x, dtype=float)
        return float(np.sum(x**2))


def main():
    np.random.seed(123)
    problem = SphereProblem()

    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=problem.low, high=problem.high),
        mutator=ContextGaussianMutation(base_sigma=0.6, low=problem.low, high=problem.high),
        repair=ClipRepair(low=problem.low, high=problem.high),
    )

    solver = ComposableSolver(problem=problem, representation_pipeline=pipeline)
    solver.set_max_steps(40)

    strategies = [
        StrategySpec(adapter=VNSAdapter(VNSConfig(batch_size=16, k_max=4, base_sigma=0.15)), name="vns", weight=0.6),
        StrategySpec(
            adapter=SimulatedAnnealingAdapter(SAConfig(batch_size=8, initial_temperature=8.0, cooling_rate=0.95, base_sigma=0.6)),
            name="sa",
            weight=0.4,
        ),
    ]
    solver.set_adapter(StrategyRouterAdapter(strategies=strategies))
    solver.add_plugin(ParetoArchivePlugin())

    result = solver.run()
    print("status:", result["status"], "steps:", result["steps"])
    print("best_score:", solver.best_objective)
    print("shared_best_score:", getattr(solver, "shared_best_score", None))
    print("strategy_stats:", getattr(solver, "shared_strategy_stats", None))


if __name__ == "__main__":
    main()

