"""Demo: Ray distributed evaluation backend (optional dependency).

Run (from repo root parent directory):
  python examples/ray_parallel_demo.py

If ray is not installed, this script prints a hint and exits.
"""

from __future__ import annotations

import numpy as np


def main() -> int:
    try:
        import ray  # type: ignore
    except Exception:
        print("ray is not installed. Install with: python -m pip install 'ray[default]'")
        return 0

    from nsgablack.core.blank_solver import SolverBase
    from nsgablack.utils.parallel import with_parallel_evaluation
    from nsgablack.utils.suites import attach_ray_parallel

    class SphereProblem:
        name = "sphere"
        dimension = 5
        bounds = {f"x{i}": (-5.0, 5.0) for i in range(dimension)}

        def evaluate(self, x):
            x = np.asarray(x, dtype=float)
            return float(np.sum(x * x))

        def get_num_objectives(self):
            return 1

    def problem_factory():
        return SphereProblem()

    ParallelBlank = with_parallel_evaluation(SolverBase)
    solver = ParallelBlank(problem_factory(), enable_parallel=True, parallel_backend="ray", parallel_max_workers=4)
    attach_ray_parallel(solver, problem_factory=problem_factory, max_workers=4)

    if not ray.is_initialized():
        ray.init(ignore_reinit_error=True, include_dashboard=False, log_to_driver=False)

    # run a tiny loop (SolverBase contract)
    x0 = np.random.uniform(-5, 5, size=(30, 5))
    obj, vio = solver.evaluate_population(x0)
    print("ok:", obj.shape, vio.shape, "best", float(np.min(obj)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

