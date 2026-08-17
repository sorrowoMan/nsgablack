from __future__ import annotations

import numpy as np
import pytest

from blackbase.resources import DataRef
from blackbase.types import SolveQuality, SolverResult, UnknownState
from nsgablack.core import BlackBoxProblem, EvolutionSolver, SolverBase, build_solver_result


class _Problem(BlackBoxProblem):
    def __init__(self) -> None:
        super().__init__(dimension=2, objectives=("cost", "risk"))

    def evaluate(self, candidate, context=None):
        del context
        value = np.asarray(candidate, dtype=float)
        return np.asarray([value[0], value[1]], dtype=float)


def _solver() -> SolverBase:
    solver = SolverBase(_Problem())
    solver.population = np.asarray([[1.0, 2.0], [2.0, 1.0], [3.0, 3.0]])
    solver.objectives = np.asarray([[0.2, 0.8], [0.5, 0.4], [3.0, 3.0]])
    solver.constraint_violations = np.asarray([0.0, 0.1, 0.0])
    solver.best_x = np.asarray([1.0, 2.0])
    solver.best_objectives = np.asarray([0.2, 0.8])
    solver.best_constraint_violation = 0.0
    solver.pareto_solutions = {
        "individuals": solver.population[:2],
        "objectives": solver.objectives[:2],
    }
    solver.pareto_objectives = solver.objectives[:2]
    solver.generation = 5
    solver.evaluation_count = 12
    return solver


def test_build_solver_result_preserves_vector_objectives_and_pareto_front() -> None:
    result = build_solver_result(_solver(), {"status": "ok", "elapsed_sec": 0.2})

    assert isinstance(result, SolverResult)
    assert isinstance(result.best_solution, UnknownState)
    assert np.allclose(result.best_solution.as_array(), [1.0, 2.0])
    assert np.allclose(result.best_objectives, [0.2, 0.8])
    assert result.best_constraint_violation == 0.0
    assert result.pareto_front is not None
    assert len(result.pareto_front.candidates) == 2
    assert np.allclose(result.pareto_front.constraints, [0.0, 0.1])
    assert result.report["generation"] == 5
    assert result.report["evaluation_count"] == 12
    assert result.solve_status == "feasible"
    assert result.feasibility == "feasible"
    assert result.termination_reason == "completed"


def test_solver_base_case_export_returns_versioned_shared_payload() -> None:
    payload = _solver().export_case_result({"status": "ok"}).as_dict()

    assert payload["protocol_type"] == "blackbase.solver_result"
    restored = SolverResult.from_dict(payload)
    assert np.allclose(restored.best_objectives, [0.2, 0.8])


def test_result_boundary_does_not_select_best_when_solver_declares_none() -> None:
    solver = _solver()
    solver.best_x = None
    solver.best_objectives = None
    solver.best_constraint_violation = None

    result = build_solver_result(solver, {"status": "ok"})

    assert result.best_solution is None
    assert result.best_objectives is None
    assert result.best_constraint_violation is None
    assert result.pareto_front is not None


def test_result_boundary_does_not_bind_population_objectives_to_unmatched_best() -> None:
    solver = _solver()
    solver.best_x = np.asarray([99.0, 100.0])
    solver.best_objectives = None
    solver.best_constraint_violation = None

    result = build_solver_result(solver, {"status": "ok"})

    assert np.allclose(result.best_solution.as_array(), [99.0, 100.0])
    assert result.best_objectives is None
    assert result.best_constraint_violation is None


def test_best_ref_without_declared_objectives_stays_unbound() -> None:
    solver = _solver()
    solver.best_x = None
    solver.best_objectives = None
    solver.best_constraint_violation = None
    solver.best_solution_ref = DataRef(uri="artifact://solver/best", kind="solution")

    result = build_solver_result(solver, {"status": "ok"})

    assert result.best_solution is None
    assert result.best_solution_ref == solver.best_solution_ref
    assert result.best_objectives is None


def test_formal_solver_result_is_passed_through_without_field_loss() -> None:
    solver = SolverBase(_Problem())
    formal = SolverResult(
        solve_status="optimal",
        termination_reason="convergence",
        feasibility="feasible",
        quality=SolveQuality(
            approximate=False,
            absolute_gap=0.0,
            relative_gap=0.0,
            bound=0.2,
            metrics={"certificate": "verified"},
        ),
        best_solution=UnknownState([1.0, 2.0]),
        best_objectives=[0.2, 0.8],
        report={"backend": "custom"},
        metadata={"custom": True},
    )

    result = build_solver_result(solver, formal)

    assert result is formal
    assert result.quality.metrics == {"certificate": "verified"}
    assert result.report == {"backend": "custom"}
    assert result.metadata == {"custom": True}


def test_large_pareto_front_requires_real_artifact_authority() -> None:
    solver = _solver()
    solver.best_x = None
    solver.best_objectives = None
    solver.best_constraint_violation = None
    solver.case_result_inline_max_bytes = 1

    with pytest.raises(RuntimeError, match="SolverResult.pareto_front"):
        build_solver_result(solver, {"status": "ok"})


def test_large_pareto_front_is_published_through_case_runtime() -> None:
    class _Runtime:
        def __init__(self) -> None:
            self.artifact_refs = {}
            self.published = []

        def publish_artifact(self, name, value, **kwargs):
            self.published.append((name, value, kwargs))
            ref = DataRef(
                uri="memory://solver/pareto-front",
                kind=kwargs["kind"],
                backend="memory",
                media_type=kwargs["media_type"],
            )
            self.artifact_refs[name] = ref
            return ref

    solver = _solver()
    solver.best_x = None
    solver.best_objectives = None
    solver.best_constraint_violation = None
    solver.case_result_inline_max_bytes = 1
    solver.case_runtime = _Runtime()

    result = build_solver_result(solver, {"status": "ok"})

    assert result.pareto_front is None
    assert result.pareto_front_ref == result.artifact_refs["pareto_front"]
    assert solver.case_runtime.published[0][0] == "pareto_front"
    assert (
        solver.case_runtime.published[0][1]["protocol_type"]
        == "blackbase.population_snapshot"
    )


def test_large_best_solution_requires_real_artifact_authority() -> None:
    solver = _solver()
    solver.pareto_solutions = None
    solver.pareto_objectives = None
    solver.best_x = np.arange(128, dtype=float)
    solver.best_objectives = np.asarray([1.0])
    solver.case_result_inline_max_bytes = 1

    with pytest.raises(RuntimeError, match="SolverResult.best_solution"):
        build_solver_result(solver, {"status": "ok"})


def test_large_best_solution_is_published_through_case_runtime() -> None:
    class _Runtime:
        def __init__(self) -> None:
            self.artifact_refs = {}
            self.published = []

        def publish_artifact(self, name, value, **kwargs):
            self.published.append((name, value, kwargs))
            ref = DataRef(
                uri="memory://solver/best-solution",
                kind=kwargs["kind"],
                backend="memory",
                media_type=kwargs["media_type"],
            )
            self.artifact_refs[name] = ref
            return ref

    solver = _solver()
    solver.pareto_solutions = None
    solver.pareto_objectives = None
    solver.best_x = np.arange(128, dtype=float)
    solver.best_objectives = np.asarray([1.0])
    solver.case_result_inline_max_bytes = 1
    solver.case_runtime = _Runtime()

    result = build_solver_result(solver, {"status": "ok"})

    assert result.best_solution is None
    assert result.best_solution_ref == result.artifact_refs["best_solution"]
    assert solver.case_runtime.published[0][0] == "best_solution"
    assert solver.case_runtime.published[0][2]["kind"] == "solution"


def test_evolution_solver_declares_objectives_for_its_selected_best() -> None:
    solver = EvolutionSolver(_Problem(), pop_size=2, max_generations=1)
    solver.population = np.asarray([[1.0, 2.0], [2.0, 1.0]])
    solver.objectives = np.asarray([[0.2, 0.8], [0.5, 0.4]])
    solver.constraint_violations = np.asarray([0.0, 0.1])

    solver._refresh_best()
    result = build_solver_result(solver, {"status": "ok"})

    assert np.allclose(result.best_solution.as_array(), solver.best_x)
    assert np.allclose(result.best_objectives, solver.best_objectives)
    assert result.best_constraint_violation == solver.best_constraint_violation
