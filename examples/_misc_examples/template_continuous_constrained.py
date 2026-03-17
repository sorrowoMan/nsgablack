"""Template: continuous constrained optimization (box + soft constraint)."""

import numpy as np

try:
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import SimulatedAnnealingAdapter, SAConfig
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, ContextGaussianMutation, ClipRepair
    from nsgablack.bias import BiasModule
    from nsgablack.bias.domain import DynamicPenaltyBias
    from nsgablack.utils.wiring import attach_benchmark_harness, attach_module_report
except ModuleNotFoundError:  # pragma: no cover
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import SimulatedAnnealingAdapter, SAConfig
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, ContextGaussianMutation, ClipRepair
    from nsgablack.bias import BiasModule
    from nsgablack.bias.domain import DynamicPenaltyBias
    from nsgablack.utils.wiring import attach_benchmark_harness, attach_module_report


class SphereWithSumConstraint(BlackBoxProblem):
    def __init__(self, dimension=8, low=-5.0, high=5.0):
        super().__init__(
            name="SphereWithSumConstraint",
            dimension=dimension,
            bounds={f"x{i}": (low, high) for i in range(dimension)},
        )
        self.low = low
        self.high = high

    def evaluate(self, x):
        x = np.asarray(x, dtype=float)
        return float(np.sum(x ** 2))


def build_solver():
    problem = SphereWithSumConstraint()

    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=problem.low, high=problem.high),
        mutator=ContextGaussianMutation(base_sigma=0.4, low=problem.low, high=problem.high),
        repair=ClipRepair(low=problem.low, high=problem.high),
    )

    # soft constraint: sum(x) <= 1.0
    def _sum_constraint_penalty(x, _context):
        x = np.asarray(x, dtype=float)
        return float(max(0.0, np.sum(x) - 1.0))

    bias_module = BiasModule()
    bias_module.add(
        DynamicPenaltyBias(
            weight=0.4,
            penalty_func=_sum_constraint_penalty,
            schedule="linear",
            start_scale=0.2,
            end_scale=1.0,
        )
    )

    adapter = SimulatedAnnealingAdapter(SAConfig(batch_size=6, initial_temperature=8.0, cooling_rate=0.97))

    solver = ComposableSolver(
        problem=problem,
        adapter=adapter,
        representation_pipeline=pipeline,
        bias_module=bias_module,
    )
    solver.set_bias_enabled(True)
    solver.set_max_steps(60)

    attach_benchmark_harness(solver, output_dir="runs", run_id="template_continuous", overwrite=True, log_every=1)
    attach_module_report(solver, output_dir="runs", run_id="template_continuous", write_bias_markdown=True)
    return solver


if __name__ == "__main__":
    solver = build_solver()
    result = solver.run()
    print("status:", result["status"], "steps:", result["steps"])
    print("best:", solver.best_objective)

