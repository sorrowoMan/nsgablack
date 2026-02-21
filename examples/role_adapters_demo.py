"""Role-based adapters demo: RoleAdapter + MultiRoleControllerAdapter."""

import numpy as np

try:
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.core.adapters import AlgorithmAdapter, RoleAdapter, MultiRoleControllerAdapter
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, GaussianMutation, ClipRepair
    from nsgablack.utils.suites import attach_benchmark_harness, attach_module_report
except ModuleNotFoundError:  # pragma: no cover
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.core.adapters import AlgorithmAdapter, RoleAdapter, MultiRoleControllerAdapter
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, GaussianMutation, ClipRepair
    from nsgablack.utils.suites import attach_benchmark_harness, attach_module_report


class Sphere(BlackBoxProblem):
    def __init__(self, dim=6, low=-5.0, high=5.0):
        super().__init__(name="Sphere", dimension=dim, bounds={f"x{i}": (low, high) for i in range(dim)})
        self.low = low
        self.high = high

    def evaluate(self, x):
        x = np.asarray(x, dtype=float)
        return float(np.sum(x * x))


class Explorer(AlgorithmAdapter):
    def __init__(self):
        super().__init__(name="explorer")

    def propose(self, solver, context):
        return [solver.mutate_candidate(solver.init_candidate(context), context) for _ in range(12)]


class Exploiter(AlgorithmAdapter):
    def __init__(self):
        super().__init__(name="exploiter")

    def propose(self, solver, context):
        if solver.best_x is None:
            return [solver.init_candidate(context) for _ in range(8)]
        return [solver.mutate_candidate(solver.best_x, context) for _ in range(8)]


def build_solver():
    problem = Sphere()

    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=problem.low, high=problem.high),
        mutator=GaussianMutation(sigma=0.5, low=problem.low, high=problem.high),
        repair=ClipRepair(low=problem.low, high=problem.high),
    )

    controller = MultiRoleControllerAdapter(
        [
            RoleAdapter("explorer", Explorer(), max_candidates=10),
            RoleAdapter("exploiter", Exploiter(), max_candidates=8),
        ]
    )

    solver = ComposableSolver(problem=problem, adapter=controller, representation_pipeline=pipeline)
    solver.set_max_steps(20)

    attach_benchmark_harness(solver, output_dir="runs", run_id="role_adapters", overwrite=True, log_every=1)
    attach_module_report(solver, output_dir="runs", run_id="role_adapters", write_bias_markdown=True)
    return solver


if __name__ == "__main__":
    solver = build_solver()
    result = solver.run()
    print("status:", result["status"], "steps:", result["steps"])
    print("best:", solver.best_objective)
