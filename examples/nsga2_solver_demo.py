"""NSGA-II solver demo with engineering suite wiring."""

import numpy as np

try:
    from nsgablack.core.solver import BlackBoxSolverNSGAII
    from nsgablack.utils.suites import attach_nsga2_engineering
    from nsgablack.plugins import BenchmarkHarnessPlugin, ModuleReportPlugin
except ModuleNotFoundError:  # pragma: no cover
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from nsgablack.core.solver import BlackBoxSolverNSGAII
    from nsgablack.utils.suites import attach_nsga2_engineering
    from nsgablack.plugins import BenchmarkHarnessPlugin, ModuleReportPlugin


class BiObjectiveSphere:
    def __init__(self, dimension: int = 6, low: float = -5.0, high: float = 5.0):
        self.name = "BiObjectiveSphere"
        self.dimension = int(dimension)
        self.bounds = {f"x{i}": (low, high) for i in range(self.dimension)}
        self.variables = list(self.bounds.keys())

    def get_num_objectives(self):
        return 2

    def evaluate(self, x):
        x = np.asarray(x, dtype=float)
        f1 = float(np.sum(x * x))
        f2 = float(np.sum((x - 1.5) ** 2))
        return np.array([f1, f2], dtype=float)


def build_solver():
    problem = BiObjectiveSphere()
    solver = BlackBoxSolverNSGAII(problem)
    solver.set_solver_hyperparams(pop_size=60)
    solver.set_solver_hyperparams(max_generations=40)

    attach_nsga2_engineering(
        solver,
        enable_basic_elite=True,
        enable_convergence=False,
        enable_diversity_metrics=False,
    )

    solver.add_plugin(BenchmarkHarnessPlugin())
    solver.add_plugin(ModuleReportPlugin())
    return solver


if __name__ == "__main__":
    solver = build_solver()
    result = solver.run(max_generations=40, seed=3)
    print("status:", result.get("status"))
    print("best objective:", result.get("best_objective"))

