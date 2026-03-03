import numpy as np

from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.blank_solver import SolverBase
from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.adapters import AlgorithmAdapter
from nsgablack.utils.parallel import with_parallel_evaluation


class TinySphere(BlackBoxProblem):
    def __init__(self, dimension=4):
        bounds = {f"x{i}": (-5, 5) for i in range(dimension)}
        super().__init__(name="tiny_sphere", dimension=dimension, bounds=bounds, objectives=["minimize"])

    def evaluate(self, x):
        x = np.asarray(x, dtype=float)
        return float(np.sum(x * x))


def test_parallel_wrapper_blank_matches_serial():
    problem = TinySphere()
    population = np.array(
        [
            [0.0, 1.0, 2.0, 3.0],
            [1.0, 2.0, 3.0, 4.0],
            [-1.0, -2.0, -3.0, -4.0],
            [0.5, -0.5, 1.5, -1.5],
            [2.0, 0.0, 0.0, 0.0],
        ],
        dtype=float,
    )

    serial = SolverBase(problem)
    obj_s, vio_s = serial.evaluate_population(population)

    ParallelBlank = with_parallel_evaluation(SolverBase)
    parallel = ParallelBlank(problem, parallel=True, parallel_backend="thread", parallel_max_workers=2)
    obj_p, vio_p = parallel.evaluate_population(population)

    assert np.allclose(obj_s, obj_p)
    assert np.allclose(vio_s, vio_p)


class FixedCandidatesAdapter(AlgorithmAdapter):
    def __init__(self, candidates):
        super().__init__(name="fixed")
        self._candidates = [np.asarray(c, dtype=float) for c in candidates]

    def propose(self, solver, context):
        return list(self._candidates)


def test_parallel_wrapper_composable_evaluates():
    problem = TinySphere()
    candidates = [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 2.0, 0.0, 0.0],
        [0.0, 0.0, -3.0, 0.0],
        [0.0, 0.0, 0.0, 4.0],
        [0.5, 0.5, 0.5, 0.5],
    ]

    ParallelComposable = with_parallel_evaluation(ComposableSolver)
    solver = ParallelComposable(
        problem,
        adapter=FixedCandidatesAdapter(candidates),
        parallel=True,
        parallel_backend="thread",
        parallel_max_workers=2,
    )
    solver.max_steps = 1
    solver.run()

    assert solver.objectives is not None
    assert solver.objectives.shape[0] == len(candidates)
