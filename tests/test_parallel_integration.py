import numpy as np

from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.nested_solver import InnerRuntimeConfig, TaskInnerRuntimeEvaluator
from nsgablack.core.evolution_solver import EvolutionSolver
from nsgablack.utils.parallel import with_parallel_evaluation


class TinySphere(BlackBoxProblem):
    def __init__(self, dimension=3):
        bounds = {f"x{i}": (-5, 5) for i in range(dimension)}
        super().__init__(dimension=dimension, objectives=["minimize"], bounds=bounds)

    def evaluate(self, candidate):
        return float(np.sum(np.asarray(candidate, dtype=float) ** 2))


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

        def evaluate(self, candidate):
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


def test_nested_parallel_uses_parent_l0_grant_and_keeps_local_slot_as_audit_metadata():
    from nsgablack.utils.parallel.nested import NestedParallelEvaluator

    seen_contexts: list[dict] = []

    class NestedProblem(BlackBoxProblem):
        def __init__(self):
            super().__init__(
                name="nested_resource_lineage",
                dimension=1,
                objectives=["nested_score"],
                bounds={"x0": (-5.0, 5.0)},
            )

        def evaluate(self, candidate):
            return np.asarray([9999.0])

        def build_inner_task(self, x, eval_context):
            seen_contexts.append(dict(eval_context["resource_context"]))
            return {"run_inner": lambda _p, _s, _c: {"status": "ok", "objective": float(x[0])}}

    problem = NestedProblem()
    problem.inner_runtime_evaluator = TaskInnerRuntimeEvaluator()
    solver = EvolutionSolver(
        problem,
        resource_context={
            "threads": 2,
            "namespace": "project.stage.outer",
            "grant": {"threads": 2, "workers": 2},
            "lease": {"lease_id": "project-lease", "owner_id": "outer"},
        },
    )
    evaluator = NestedParallelEvaluator(max_workers=8)

    objectives, violations = evaluator.evaluate_population(solver, np.asarray([[1.0], [2.0], [3.0]]))

    assert np.allclose(objectives.reshape(-1), [1.0, 2.0, 3.0])
    assert np.allclose(violations, 0.0)
    assert len(seen_contexts) == 3
    for context in seen_contexts:
        assert context["lease"]["lease_id"] == "project-lease"
        assert context["threads"] == 1
        assert context["metadata"]["parent_lease_id"] == "project-lease"
        assert context["metadata"]["local_execution_lease"]["lease_id"]
