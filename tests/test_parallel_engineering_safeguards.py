import numpy as np
import pytest

from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.solver import BlackBoxSolverNSGAII


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
