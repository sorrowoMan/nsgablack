from __future__ import annotations

import numpy as np
import pytest


def test_parallel_evaluator_ray_backend_smoke():
    try:
        import ray  # type: ignore
    except Exception:
        pytest.skip("ray not installed")

    from nsgablack.utils.parallel.evaluator import ParallelEvaluator

    class SphereProblem:
        dimension = 3
        bounds = {f"x{i}": (-5.0, 5.0) for i in range(dimension)}

        def evaluate(self, x):
            x = np.asarray(x, dtype=float)
            return float(np.sum(x * x))

        def get_num_objectives(self):
            return 1

    def problem_factory():
        return SphereProblem()

    if not ray.is_initialized():
        ray.init(ignore_reinit_error=True, include_dashboard=False, log_to_driver=False)

    pop = np.random.uniform(-5, 5, size=(20, 3))
    evaluator = ParallelEvaluator(backend="ray", max_workers=4, problem_factory=problem_factory, precheck=True)
    obj, vio = evaluator.evaluate_population(pop, problem_factory(), enable_bias=False, bias_module=None)
    assert obj.shape == (20, 1)
    assert vio.shape == (20,)
