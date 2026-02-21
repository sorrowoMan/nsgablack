"""Template: multi-objective Pareto optimization (MOEA/D + Pareto archive)."""

import numpy as np

try:
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.core.adapters import MOEADConfig
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, ContextGaussianMutation, ClipRepair
    from nsgablack.utils.suites import attach_moead, attach_benchmark_harness, attach_module_report
except ModuleNotFoundError:  # pragma: no cover
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.core.adapters import MOEADConfig
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, ContextGaussianMutation, ClipRepair
    from nsgablack.utils.suites import attach_moead, attach_benchmark_harness, attach_module_report


class BiObjectiveSphere(BlackBoxProblem):
    """Two objectives with trade-off: f1=x^2, f2=(x-2)^2 (sum over dims)."""

    def __init__(self, dimension=6, low=-5.0, high=5.0):
        super().__init__(
            name="BiObjectiveSphere",
            dimension=dimension,
            bounds={f"x{i}": (low, high) for i in range(dimension)},
        )
        self.low = low
        self.high = high

    def evaluate(self, x):
        x = np.asarray(x, dtype=float)
        f1 = float(np.sum(x ** 2))
        f2 = float(np.sum((x - 2.0) ** 2))
        return np.array([f1, f2], dtype=float)


def build_solver():
    problem = BiObjectiveSphere()

    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=problem.low, high=problem.high),
        mutator=ContextGaussianMutation(base_sigma=0.5, low=problem.low, high=problem.high),
        repair=ClipRepair(low=problem.low, high=problem.high),
    )

    solver = ComposableSolver(problem=problem, representation_pipeline=pipeline)
    solver.set_max_steps(80)

    attach_moead(solver, config=MOEADConfig(pop_size=40, n_neighbors=10), archive=True)
    attach_benchmark_harness(solver, output_dir="runs", run_id="template_mo_pareto", overwrite=True, log_every=1)
    attach_module_report(solver, output_dir="runs", run_id="template_mo_pareto", write_bias_markdown=True)
    return solver


if __name__ == "__main__":
    solver = build_solver()
    result = solver.run()
    print("status:", result["status"], "steps:", result["steps"])
    print("pareto_size:", len(getattr(solver, "pareto_objectives", []) or []))
