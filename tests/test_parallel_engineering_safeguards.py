import numpy as np
import pytest

from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.solver import BlackBoxSolverNSGAII
from nsgablack.utils.parallel.evaluator import ParallelEvaluator


def test_parallel_process_precheck_falls_back_to_thread_when_unpicklable():
    class LocalSphere(BlackBoxProblem):
        def __init__(self, dimension: int = 3):
            bounds = {f"x{i}": (-5, 5) for i in range(dimension)}
            super().__init__(dimension=dimension, objectives=["minimize"], bounds=bounds)

        def evaluate(self, x):
            return float(np.sum(np.asarray(x, dtype=float) ** 2))

    problem = LocalSphere()
    population = np.array(
        [
            [0.0, 1.0, 2.0],
            [1.0, 2.0, 3.0],
            [-1.0, -2.0, -3.0],
        ],
        dtype=float,
    )

    serial = BlackBoxSolverNSGAII(problem)
    obj_s, vio_s = serial.evaluate_population(population)

    with pytest.warns(UserWarning):
        parallel = BlackBoxSolverNSGAII(
            problem,
            parallel=True,
            parallel_backend="process",
            parallel_precheck=True,
            parallel_strict=False,
            parallel_fallback_backend="thread",
            parallel_max_workers=2,
        )
        obj_p, vio_p = parallel.evaluate_population(population)

    assert np.allclose(obj_s, obj_p)
    assert np.allclose(vio_s, vio_p)


def test_parallel_process_precheck_strict_raises_when_unpicklable():
    class LocalSphere(BlackBoxProblem):
        def __init__(self, dimension: int = 3):
            bounds = {f"x{i}": (-5, 5) for i in range(dimension)}
            super().__init__(dimension=dimension, objectives=["minimize"], bounds=bounds)

        def evaluate(self, x):
            return float(np.sum(np.asarray(x, dtype=float) ** 2))

    problem = LocalSphere()
    population = np.array(
        [
            [0.0, 1.0, 2.0],
            [1.0, 2.0, 3.0],
        ],
        dtype=float,
    )

    parallel = BlackBoxSolverNSGAII(
        problem,
        parallel=True,
        parallel_backend="process",
        parallel_precheck=True,
        parallel_strict=True,
        parallel_max_workers=2,
    )

    with pytest.raises(ValueError):
        parallel.evaluate_population(population)


def test_thread_backend_deepcopy_bias_isolation_keeps_original_state():
    class LocalSphere(BlackBoxProblem):
        def __init__(self):
            super().__init__(dimension=2, objectives=["minimize"], bounds={"x0": (-5, 5), "x1": (-5, 5)})

        def evaluate(self, x):
            return float(np.sum(np.asarray(x, dtype=float) ** 2))

    class CountingBias:
        def __init__(self):
            self.count = 0
            self.cache_enabled = True

        def compute_bias(self, x, objective_value, individual_id=0, context=None):
            self.count += 1
            return float(objective_value)

    population = np.array([[0.0, 1.0], [1.0, 2.0], [2.0, 3.0], [3.0, 4.0]], dtype=float)
    problem = LocalSphere()
    bias = CountingBias()

    evaluator = ParallelEvaluator(
        backend="thread",
        max_workers=2,
        thread_bias_isolation="deepcopy",
    )
    objectives, _ = evaluator.evaluate_population(population, problem, enable_bias=True, bias_module=bias)

    assert objectives.shape == (4, 1)
    assert bias.count == 0
    assert bias.cache_enabled is True


def test_thread_backend_disable_cache_temporarily_and_restore():
    class LocalSphere(BlackBoxProblem):
        def __init__(self):
            super().__init__(dimension=2, objectives=["minimize"], bounds={"x0": (-5, 5), "x1": (-5, 5)})

        def evaluate(self, x):
            return float(np.sum(np.asarray(x, dtype=float) ** 2))

    class CountingBias:
        def __init__(self):
            self.count = 0
            self.cache_enabled = True

        def compute_bias(self, x, objective_value, individual_id=0, context=None):
            self.count += 1
            return float(objective_value)

    population = np.array([[0.0, 1.0], [1.0, 2.0], [2.0, 3.0]], dtype=float)
    problem = LocalSphere()
    bias = CountingBias()

    evaluator = ParallelEvaluator(
        backend="thread",
        max_workers=2,
        thread_bias_isolation="disable_cache",
    )
    objectives, _ = evaluator.evaluate_population(population, problem, enable_bias=True, bias_module=bias)

    assert objectives.shape == (3, 1)
    assert bias.count > 0
    assert bias.cache_enabled is True
