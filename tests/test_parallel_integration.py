import numpy as np

from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.nested_solver import InnerRuntimeConfig, TaskInnerRuntimeEvaluator
from nsgablack.core.evolution_solver import EvolutionSolver
from nsgablack.utils.parallel import with_parallel_evaluation


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

    serial = EvolutionSolver(problem)
    obj_s, vio_s = serial.evaluate_population(population)

    parallel = EvolutionSolver(
        problem,
        parallel=True,
        parallel_backend="thread",
        parallel_max_workers=2,
    )
    obj_p, vio_p = parallel.evaluate_population(population)

    assert np.allclose(obj_s, obj_p)
    assert np.allclose(vio_s, vio_p)


def test_parallelized_evolution_solver_preserves_nested_inner_runtime_path():
    class NestedProblem(BlackBoxProblem):
        def __init__(self):
            super().__init__(
                name="nested_parallel_guard",
                dimension=1,
                objectives=["nested_score"],
                bounds={"x0": (-5.0, 5.0)},
            )
            self.direct_evaluate_calls = 0
            self.build_task_calls = 0
            self.project_calls = 0

        def evaluate(self, x):
            self.direct_evaluate_calls += 1
            return np.array([9999.0], dtype=float)

        def build_inner_task(self, x, eval_context):
            self.build_task_calls += 1
            value = float(np.asarray(x, dtype=float).reshape(-1)[0])
            return {
                "run_inner": lambda _p, _s, _c: {
                    "status": "ok",
                    "objective": value + 10.0,
                    "inner_value": value + 10.0,
                }
            }

        def evaluate_from_inner_result(self, x, inner_result, eval_context):
            _ = (x, eval_context)
            self.project_calls += 1
            return np.array([float(inner_result["inner_value"])], dtype=float), 0.0

    problem = NestedProblem()
    problem.inner_runtime_evaluator = TaskInnerRuntimeEvaluator(
        config=InnerRuntimeConfig(source_layer="L2", target_layer="L1")
    )

    ParallelEvolutionSolver = with_parallel_evaluation(EvolutionSolver, min_population_for_parallel=1)
    solver = ParallelEvolutionSolver(
        problem,
        parallel=True,
        parallel_backend="thread",
        parallel_max_workers=2,
    )

    population = np.array([[1.0], [2.0]], dtype=float)
    objectives, violations = solver.evaluate_population(population)

    assert np.allclose(objectives.reshape(-1), [11.0, 12.0])
    assert np.allclose(violations, [0.0, 0.0])
    assert problem.direct_evaluate_calls == 0
    assert problem.build_task_calls == 2
    assert problem.project_calls == 2
