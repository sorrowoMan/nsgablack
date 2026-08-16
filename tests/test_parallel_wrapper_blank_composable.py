import numpy as np

from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.blank_solver import SolverBase
from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.core.evolution_solver import EvolutionSolver
from nsgablack.adapters import AlgorithmAdapter
from nsgablack.utils.parallel import with_parallel_evaluation


class TinySphere(BlackBoxProblem):
    def __init__(self, dimension=4):
        bounds = {f"x{i}": (-5, 5) for i in range(dimension)}
        super().__init__(name="tiny_sphere", dimension=dimension, bounds=bounds, objectives=["minimize"])

    def evaluate(self, candidate):
        candidate = np.asarray(candidate, dtype=float)
        return float(np.sum(candidate * candidate))


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

    def propose(self, control, context):
        return list(self._candidates)

    def update(self, control, candidates, feedback, context):
        del control, candidates, feedback, context


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


def test_solver_projects_resource_context_and_caps_parallel_wrapper_workers():
    problem = TinySphere()
    ParallelComposable = with_parallel_evaluation(ComposableSolver)
    solver = ParallelComposable(
        problem,
        adapter=FixedCandidatesAdapter([[0.0, 0.0, 0.0, 0.0]]),
        parallel=True,
        parallel_backend="thread",
        parallel_max_workers=8,
        resource_context={
            "scope": "case",
            "threads": 2,
            "namespace": "project.stage.case",
            "grant": {"threads": 2, "backend": "local"},
        },
    )

    context = solver.build_context()
    assert solver.get_resource_context().threads == 2
    assert context["resource_context"]["namespace"] == "project.stage.case"
    assert context["resource.context"]["threads"] == 2
    assert context["resource.threads"] == 2
    assert solver._parallel_cfg["max_workers"] == 2
    assert solver._parallel_cfg["extra_context"]["resource.namespace"] == "project.stage.case"

    solver.set_resource_context({"threads": 1, "namespace": "project.stage.case.regranted"})
    assert solver._parallel_cfg["max_workers"] == 1


def test_evolution_solver_caps_requested_workers_by_project_grant():
    solver = EvolutionSolver(
        TinySphere(),
        enable_parallel=True,
        parallel_backend="thread",
        parallel_max_workers=6,
        resource_context={"threads": 2, "namespace": "project.evolution"},
    )

    assert solver._parallel_cfg["max_workers"] == 2
    assert solver.build_context()["resource.namespace"] == "project.evolution"
