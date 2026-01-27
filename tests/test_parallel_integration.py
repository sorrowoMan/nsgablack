import numpy as np

from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.solver import BlackBoxSolverNSGAII


class TinySphere(BlackBoxProblem):
    def __init__(self, dimension=3):
        bounds = {f"x{i}": (-5, 5) for i in range(dimension)}
        super().__init__(dimension=dimension, objectives=["minimize"], bounds=bounds)

    def evaluate(self, x):
        return float(np.sum(np.asarray(x, dtype=float) ** 2))


def test_parallel_evaluation_matches_serial():
    problem = TinySphere()
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

    parallel = BlackBoxSolverNSGAII(
        problem,
        parallel=True,
        parallel_backend="thread",
        parallel_max_workers=2,
    )
    obj_p, vio_p = parallel.evaluate_population(population)

    assert np.allclose(obj_s, obj_p)
    assert np.allclose(vio_s, vio_p)
