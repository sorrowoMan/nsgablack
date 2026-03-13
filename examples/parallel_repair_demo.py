"""ParallelRepair demo: wrap repair in thread/process parallelism."""

import numpy as np

try:
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import SimulatedAnnealingAdapter, SAConfig
    from nsgablack.representation import RepresentationPipeline, ParallelRepair
    from nsgablack.representation.continuous import UniformInitializer, ContextGaussianMutation, ClipRepair
    from nsgablack.utils.wiring import attach_benchmark_harness, attach_module_report
except ModuleNotFoundError:  # pragma: no cover
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import SimulatedAnnealingAdapter, SAConfig
    from nsgablack.representation import RepresentationPipeline, ParallelRepair
    from nsgablack.representation.continuous import UniformInitializer, ContextGaussianMutation, ClipRepair
    from nsgablack.utils.wiring import attach_benchmark_harness, attach_module_report


class Sphere(BlackBoxProblem):
    def __init__(self, dim=12, low=-10.0, high=10.0):
        super().__init__(name="Sphere", dimension=dim, bounds={f"x{i}": (low, high) for i in range(dim)})
        self.low = low
        self.high = high

    def evaluate(self, x):
        x = np.asarray(x, dtype=float)
        return float(np.sum(x * x))


def build_solver():
    problem = Sphere()

    repair = ParallelRepair(
        ClipRepair(low=problem.low, high=problem.high),
        backend="thread",
        max_workers=4,
        min_batch_size=8,
    )

    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=problem.low, high=problem.high),
        mutator=ContextGaussianMutation(base_sigma=0.6, low=problem.low, high=problem.high),
        repair=repair,
    )

    adapter = SimulatedAnnealingAdapter(SAConfig(batch_size=24, initial_temperature=8.0, cooling_rate=0.97))

    solver = ComposableSolver(problem=problem, adapter=adapter, representation_pipeline=pipeline)
    solver.set_max_steps(40)

    attach_benchmark_harness(solver, output_dir="runs", run_id="parallel_repair", overwrite=True, log_every=1)
    attach_module_report(solver, output_dir="runs", run_id="parallel_repair", write_bias_markdown=True)
    return solver


if __name__ == "__main__":
    solver = build_solver()
    result = solver.run()
    print("status:", result["status"], "steps:", result["steps"])
    print("best:", solver.best_objective)
