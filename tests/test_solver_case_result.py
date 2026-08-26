from __future__ import annotations

import gc
import threading

import numpy as np
import pytest

from blackbase.resources import DataRef
from blackbase.types import PopulationSnapshot, SolveQuality, SolverResult, UnknownState
from nsgablack.core import (
    BlackBoxProblem,
    ComposableSolver,
    EvolutionSolver,
    IncumbentState,
    ScalarizationError,
    SolverBase,
    build_solver_result,
)
from nsgablack.adapters import AlgorithmAdapter
from nsgablack.core.solver_helpers import format_run_result


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
    solver.set_incumbent(
        IncumbentState(
            candidate=[1.0, 2.0],
            objectives=[0.2, 0.8],
            constraint_violation=0.0,
            score=1.0,
        )
    )
    solver.pareto_solutions = {
        "individuals": solver.population[:2],
        "objectives": solver.objectives[:2],
    }
    solver.pareto_objectives = solver.objectives[:2]
    solver.pareto_population_snapshot = PopulationSnapshot(
        candidates=(
            UnknownState([1.0, 2.0], metadata={"model": "first"}),
            UnknownState([2.0, 1.0], metadata={"model": "second"}),
        ),
        candidate_tokens=("candidate:first", "candidate:second"),
        objectives=solver.objectives[:2],
        constraints=solver.constraint_violations[:2],
        generation=5,
        metadata={"source": "test.authority"},
    )
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
    assert result.pareto_front.candidate_tokens == (
        "candidate:first",
        "candidate:second",
    )
    assert result.pareto_front.candidates[0].metadata["model"] == "first"
    assert np.allclose(result.pareto_front.constraints, [0.0, 0.1])
    assert result.report["generation"] == 5
    assert result.report["evaluation_count"] == 12
    assert result.solve_status == "feasible"
    assert result.feasibility == "feasible"
    assert result.termination_reason == "completed"


def test_pareto_result_preserves_equal_numeric_candidates_by_token() -> None:
    solver = SolverBase(_Problem())
    duplicated = np.asarray([[1.0, 2.0], [1.0, 2.0]])
    objectives = np.asarray([[0.2, 0.8], [0.5, 0.4]])
    solver.population = duplicated
    solver.objectives = objectives
    solver.constraint_violations = np.asarray([0.0, 3.0])
    solver.pareto_solutions = {
        "individuals": duplicated,
        "objectives": objectives,
    }
    solver.pareto_objectives = objectives
    solver.pareto_population_snapshot = PopulationSnapshot(
        candidates=(
            UnknownState(duplicated[0], metadata={"structure": "a"}),
            UnknownState(duplicated[1], metadata={"structure": "b"}),
        ),
        candidate_tokens=("token:a", "token:b"),
        objectives=objectives,
        constraints=np.asarray([0.0, 3.0]),
    )

    result = build_solver_result(solver, {"status": "ok"})

    assert result.pareto_front is not None
    assert result.pareto_front.candidate_tokens == ("token:a", "token:b")
    assert [state.metadata["structure"] for state in result.pareto_front.candidates] == [
        "a",
        "b",
    ]
    assert np.array_equal(result.pareto_front.constraints, [0.0, 3.0])


def test_solver_base_case_export_returns_versioned_shared_payload() -> None:
    payload = _solver().export_case_result({"status": "ok"}).as_dict()

    assert payload["protocol_type"] == "blackbase.solver_result"
    restored = SolverResult.from_dict(payload)
    assert np.allclose(restored.best_objectives, [0.2, 0.8])


def test_result_boundary_does_not_select_best_when_solver_declares_none() -> None:
    solver = _solver()
    solver.clear_incumbent()

    result = build_solver_result(solver, {"status": "ok"})

    assert result.best_solution is None
    assert result.best_objectives is None
    assert result.best_constraint_violation is None
    assert result.pareto_front is not None


def test_result_boundary_ignores_uncommitted_best_mirror_fields() -> None:
    solver = _solver()
    solver.clear_incumbent()
    solver.best_x = np.asarray([99.0, 100.0])
    solver.best_objective = 199.0

    result = build_solver_result(solver, {"status": "ok"})

    assert result.best_solution is None
    assert result.best_objectives is None
    assert result.best_constraint_violation is None


def test_best_ref_without_declared_objectives_stays_unbound() -> None:
    solver = _solver()
    solver.clear_incumbent()
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

    assert result is not formal
    assert result.quality.metrics == {"certificate": "verified"}
    assert result.report == {"backend": "custom"}
    assert result.metadata["custom"] is True
    assert result.metadata["incumbent_revision"] == 0
    assert result.metadata["incumbent_context_projection_revision"] == 0
    assert result.metadata["incumbent_context_projection_current"] is True
    assert result.metadata["incumbent_context_projection_error"] is None


def test_formal_solver_result_is_completed_from_authoritative_incumbent() -> None:
    solver = SolverBase(_Problem())
    solver.set_incumbent(
        IncumbentState(
            candidate=[1.0, 2.0],
            objectives=[0.2, 0.8],
            constraint_violation=0.0,
            score=1.0,
            candidate_token="candidate:best",
            evaluation_id="evaluation:best",
            source="evaluation",
            source_run_id="solver-run:1",
            proposal_id="proposal:1",
        )
    )

    result = build_solver_result(
        solver,
        SolverResult(
            solve_status="feasible",
            feasibility="feasible",
        ),
    )

    assert np.allclose(result.best_solution.as_array(), [1.0, 2.0])
    assert np.allclose(result.best_objectives, [0.2, 0.8])
    assert result.best_constraint_violation == 0.0
    assert result.best_candidate_token == "candidate:best"
    assert result.best_evaluation_id == "evaluation:best"
    assert result.best_provenance["proposal_id"] == "proposal:1"


@pytest.mark.parametrize(
    "formal",
    (
        SolverResult(best_candidate_token="wrong"),
        SolverResult(best_evaluation_id="wrong"),
        SolverResult(best_objectives=[9.0, 9.0]),
        SolverResult(best_solution=UnknownState([9.0, 9.0])),
        SolverResult(best_provenance={"source": "rewritten"}),
        SolverResult(
            best_solution_ref=DataRef(
                uri="artifact://unbound-best",
                checksum="sha256:" + "a" * 64,
            )
        ),
    ),
)
def test_formal_solver_result_rejects_incumbent_authority_conflicts(
    formal: SolverResult,
) -> None:
    solver = _solver()

    with pytest.raises(RuntimeError, match="formal SolverResult"):
        build_solver_result(solver, formal)


def test_large_pareto_front_requires_real_artifact_authority() -> None:
    solver = _solver()
    solver.clear_incumbent()
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
    solver.clear_incumbent()
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
    solver.pareto_population_snapshot = None
    solver.set_incumbent(
        IncumbentState(
            candidate=np.arange(128, dtype=float),
            objectives=[1.0],
            constraint_violation=0.0,
            score=1.0,
        )
    )
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
    solver.pareto_population_snapshot = None
    solver.set_incumbent(
        IncumbentState(
            candidate=np.arange(128, dtype=float),
            objectives=[1.0],
            constraint_violation=0.0,
            score=1.0,
        )
    )
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


def test_incumbent_selection_is_feasibility_first_without_penalty_tuning() -> None:
    solver = ComposableSolver(_Problem())

    solver._update_best(
        np.asarray([[1.0, 1.0], [2.0, 2.0]]),
        np.asarray([[2_000_000.0, 0.0], [0.0, 0.0]]),
        np.asarray([0.0, 0.1]),
    )

    assert np.allclose(solver.best_x, [1.0, 1.0])
    assert np.allclose(solver.best_objectives, [2_000_000.0, 0.0])
    assert solver.best_constraint_violation == 0.0


def test_incumbent_uses_the_same_scalarizer_across_updates() -> None:
    solver = ComposableSolver(_Problem())
    solver.set_incumbent_scalarizer(
        lambda objective_row, violation, context: objective_row[1],
        policy_id="test.second_objective/v1",
    )

    solver._update_best(
        np.asarray([[1.0, 1.0], [2.0, 2.0]]),
        np.asarray([[100.0, 1.0], [0.0, 2.0]]),
        np.zeros(2),
    )
    solver._update_best(
        np.asarray([[3.0, 3.0]]),
        np.asarray([[-100.0, 5.0]]),
        np.zeros(1),
    )

    assert np.allclose(solver.best_x, [1.0, 1.0])
    assert np.allclose(solver.best_objectives, [100.0, 1.0])
    assert solver.best_objective == 1.0
    assert solver.best_score == 1.0


def test_evolution_direct_and_case_results_share_the_run_incumbent() -> None:
    solver = EvolutionSolver(_Problem(), pop_size=1, max_generations=1)
    solver.population = np.asarray([[1.0, 1.0]])
    solver.objectives = np.asarray([[1.0, 1.0]])
    solver.constraint_violations = np.asarray([0.0])
    solver._refresh_best()

    solver.population = np.asarray([[9.0, 9.0]])
    solver.objectives = np.asarray([[9.0, 9.0]])
    solver.constraint_violations = np.asarray([0.0])
    solver._refresh_best()

    direct_x, direct_score = solver._get_best_solution()
    direct_dict = format_run_result(solver=solver, base_result={}, return_dict=True)
    result = build_solver_result(
        solver,
        {"status": "ok", "feasibility": "feasible"},
    )

    assert np.allclose(direct_x, [1.0, 1.0])
    assert direct_score == 2.0
    assert np.allclose(direct_dict["best_solution"], direct_x)
    assert np.allclose(direct_dict["best_objectives"], [1.0, 1.0])
    assert direct_dict["best_constraint_violation"] == 0.0
    assert np.allclose(result.best_solution.as_array(), direct_x)
    assert np.allclose(result.best_objectives, [1.0, 1.0])
    assert result.best_constraint_violation == 0.0


def test_evolution_terminal_feasibility_uses_the_run_incumbent() -> None:
    solver = EvolutionSolver(_Problem(), pop_size=1, max_generations=2)
    solver.population = np.asarray([[1.0, 1.0]])
    solver.objectives = np.asarray([[1.0, 1.0]])
    solver.constraint_violations = np.asarray([0.0])
    solver._refresh_best()

    solver.population = np.asarray([[2.0, 2.0]])
    solver.objectives = np.asarray([[0.0, 0.0]])
    solver.constraint_violations = np.asarray([0.5])
    solver._refresh_best()

    run_result = solver._build_run_result({"status": "ok"})
    case_result = build_solver_result(solver, run_result)

    assert np.allclose(solver.best_x, [1.0, 1.0])
    assert solver.best_constraint_violation == 0.0
    assert run_result["feasibility"] == "feasible"
    assert run_result["solve_status"] == "feasible"
    assert case_result.feasibility == "feasible"
    assert case_result.solve_status == "feasible"


def test_evolution_stopped_result_keeps_incumbent_feasibility() -> None:
    solver = EvolutionSolver(_Problem(), pop_size=1, max_generations=1)
    solver.set_incumbent(
        IncumbentState(
            candidate=[1.0, 1.0],
            objectives=[1.0, 1.0],
            constraint_violation=0.0,
            score=2.0,
        )
    )
    solver.constraint_violations = np.asarray([0.5])

    run_result = solver._build_run_result({"status": "stopped"})

    assert run_result["solve_status"] == "stopped"
    assert run_result["feasibility"] == "feasible"


def test_incumbent_replacement_updates_all_best_fields_atomically() -> None:
    solver = ComposableSolver(_Problem())
    solver._update_best(
        np.asarray([[1.0, 1.0]]),
        np.asarray([[10.0, 1.0]]),
        np.asarray([0.0]),
    )

    solver.set_incumbent(
        IncumbentState(
            candidate=[9.0, 9.0],
            objectives=[0.25, 0.25],
            constraint_violation=0.0,
            score=0.5,
        )
    )

    assert solver.get_incumbent() is not None
    assert np.allclose(solver.best_x, [9.0, 9.0])
    assert np.allclose(solver.best_objectives, [0.25, 0.25])
    assert solver.best_constraint_violation == 0.0
    assert solver.best_score == 0.5


def test_scalarizer_failure_is_strict_by_default() -> None:
    solver = ComposableSolver(_Problem())

    def broken_scalarizer(objective_row, violation, context):
        del objective_row, violation, context
        raise RuntimeError("bad scalarizer")

    solver.set_incumbent_scalarizer(
        broken_scalarizer,
        policy_id="test.broken/v1",
    )

    with pytest.raises(ScalarizationError, match="scalarization failed"):
        solver._update_best(
            np.asarray([[1.0, 1.0]]),
            np.asarray([[1.0, 2.0]]),
            np.asarray([0.0]),
        )


def test_explicit_scalarizer_fallback_is_audited_in_solver_result() -> None:
    solver = ComposableSolver(_Problem())

    def broken_scalarizer(objective_row, violation, context):
        del objective_row, violation, context
        raise RuntimeError("bad scalarizer")

    solver.set_incumbent_scalarizer(
        broken_scalarizer,
        policy_id="test.fallback/v1",
        failure_policy="fallback_sum",
    )
    solver._update_best(
        np.asarray([[1.0, 1.0]]),
        np.asarray([[1.0, 2.0]]),
        np.asarray([0.0]),
    )

    result = build_solver_result(solver, {"status": "ok"})

    assert solver.scalarizer_fallback_count == 1
    assert result.metadata["scalarizer_failure_policy"] == "fallback_sum"
    assert result.metadata["scalarizer_fallback_count"] == 1
    assert result.metadata["result_quality_degraded"] is True


class _FixedCandidateAdapter(AlgorithmAdapter):
    def __init__(self, candidate) -> None:
        super().__init__(name="fixed_candidate")
        self.candidate = np.asarray(candidate, dtype=float)

    def propose(self, control, context):
        del control, context
        return [self.candidate.copy()]

    def update(self, control, candidates, feedback, context):
        del control, candidates, feedback, context


def test_scalarizer_fallback_counts_each_evaluated_candidate_once() -> None:
    solver = ComposableSolver(
        _Problem(),
        adapter=_FixedCandidateAdapter([1.0, 2.0]),
    )

    def broken_scalarizer(objective_row, violation, context):
        del objective_row, violation, context
        raise RuntimeError("bad scalarizer")

    solver.set_incumbent_scalarizer(
        broken_scalarizer,
        policy_id="test.run_fallback/v1",
        failure_policy="fallback_sum",
    )
    solver.max_steps = 1

    solver.run()

    assert solver.scalarizer_fallback_count == 1


def test_reusing_solver_for_fresh_run_does_not_inherit_old_incumbent() -> None:
    adapter = _FixedCandidateAdapter([1.0, 1.0])
    solver = ComposableSolver(_Problem(), adapter=adapter)
    solver.max_steps = 1

    first_result = solver.run()
    first_incumbent = solver.get_incumbent()
    assert first_incumbent is not None

    adapter.candidate = np.asarray([9.0, 9.0])
    second_result = solver.run()
    second_incumbent = solver.get_incumbent()

    assert second_incumbent is not None
    assert np.allclose(second_incumbent.candidate, [9.0, 9.0])
    assert second_incumbent.source_run_id != first_incumbent.source_run_id
    assert second_result["evaluation_count"] == 1
    assert first_result["evaluation_count"] == 1


def test_warm_start_is_reevaluated_before_becoming_incumbent() -> None:
    solver = ComposableSolver(_Problem())
    imported = IncumbentState(
        candidate=[3.0, 4.0],
        objectives=[0.0, 0.0],
        constraint_violation=0.0,
        score=0.0,
        evaluation_id="run-1:evaluation-1",
        source_run_id="run-1",
    )
    solver.set_warm_start(imported)
    solver.prepare_fresh_run()

    candidate = solver.init_candidate()
    assert solver.get_incumbent() is None
    solver._update_best(
        candidate.reshape(1, -1),
        np.asarray([[3.0, 4.0]]),
        np.asarray([0.0]),
    )

    incumbent = solver.get_incumbent()
    assert incumbent is not None
    assert np.allclose(incumbent.objectives, [3.0, 4.0])
    assert incumbent.score == 7.0
    assert incumbent.source == "warm_start_evaluated"
    assert incumbent.source_run_id == "run-1"
    assert incumbent.candidate_token is not None
    assert incumbent.warm_start_id is not None


def test_incumbent_mappings_are_recursively_immutable_and_as_dict_is_detached() -> None:
    state = IncumbentState(
        candidate=[1.0, 2.0],
        objectives=[3.0, 4.0],
        constraint_violation=0.0,
        score=7.0,
        policy_context={"weights": [0.7, 0.3], "nested": {"scale": 2}},
        metadata={"tags": ["warm", "audited"]},
    )

    with pytest.raises(TypeError):
        state.policy_context["weights"] = (1.0, 0.0)
    with pytest.raises(TypeError):
        state.policy_context["nested"]["scale"] = 999
    with pytest.raises(TypeError):
        state.metadata["tags"] = ()
    with pytest.raises(ValueError):
        state.candidate.setflags(write=True)

    payload = state.as_dict()
    payload["policy_context"]["weights"][0] = 999
    payload["metadata"]["tags"].append("rewritten")
    assert state.policy_context["weights"] == (0.7, 0.3)
    assert state.metadata["tags"] == ("warm", "audited")


def test_large_incumbent_candidate_is_referenced_from_context_snapshot() -> None:
    from nsgablack.core.state.context_keys import (
        KEY_BEST_CANDIDATE_REF,
        KEY_BEST_OBJECTIVE,
        KEY_BEST_X,
    )

    solver = SolverBase(_Problem(), context_inline_candidate_max_bytes=1)
    solver.set_incumbent(
        IncumbentState(
            candidate=[1.0, 2.0],
            objectives=[1.0, 2.0],
            constraint_violation=0.0,
            score=3.0,
        )
    )

    assert solver.context_store.get(KEY_BEST_X) is None
    ref = solver.context_store.get(KEY_BEST_CANDIDATE_REF)
    assert isinstance(ref, str) and ref
    assert solver.context_store.get(KEY_BEST_OBJECTIVE) == 3.0
    record = solver.snapshot_store.read(ref)
    assert record is not None
    assert np.allclose(record.data[KEY_BEST_X], [1.0, 2.0])
    context = solver.get_context()
    assert KEY_BEST_X not in context
    assert context[KEY_BEST_CANDIDATE_REF] == ref
    from nsgablack.core.solver_helpers import ensure_snapshot_readable

    hydrated = ensure_snapshot_readable(solver, context)
    assert np.allclose(hydrated[KEY_BEST_X], [1.0, 2.0])


def test_small_incumbent_candidate_remains_inline_without_snapshot_ref() -> None:
    from nsgablack.core.state.context_keys import KEY_BEST_CANDIDATE_REF, KEY_BEST_X

    solver = SolverBase(_Problem(), context_inline_candidate_max_bytes=4_096)
    solver.set_incumbent(
        IncumbentState(
            candidate=[1.0, 2.0],
            objectives=[1.0, 2.0],
            constraint_violation=0.0,
            score=3.0,
        )
    )

    assert np.allclose(solver.context_store.get(KEY_BEST_X), [1.0, 2.0])
    assert solver.context_store.get(KEY_BEST_CANDIDATE_REF) is None


def test_candidate_token_survives_repair_and_equal_natural_candidate_is_distinct() -> None:
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import ClipRepair

    class WarmStartAdapter(AlgorithmAdapter):
        def __init__(self) -> None:
            super().__init__(name="warm-start-adapter")

        def propose(self, solver, context):
            return [solver.init_candidate(context)]

        def update(self, solver, candidates, feedback, context):
            del solver, candidates, feedback, context

    solver = ComposableSolver(
        _Problem(),
        adapter=WarmStartAdapter(),
        representation_pipeline=RepresentationPipeline(
            repair=ClipRepair(low=0.0, high=1.0),
        ),
    )
    solver.max_steps = 1
    solver.set_warm_start([3.0, 4.0], source_run_id="source-run")
    solver.run()
    warm_incumbent = solver.get_incumbent()

    assert warm_incumbent is not None
    assert np.allclose(warm_incumbent.candidate, [1.0, 1.0])
    assert warm_incumbent.source == "warm_start_evaluated"
    assert warm_incumbent.source_run_id == "source-run"
    assert warm_incumbent.candidate_token is not None
    assert warm_incumbent.warm_start_id is not None
    assert warm_incumbent.proposal_id is not None

    solver.set_adapter(_FixedCandidateAdapter([1.0, 1.0]))
    solver.run()
    natural_incumbent = solver.get_incumbent()

    assert natural_incumbent is not None
    assert natural_incumbent.source == "evaluation"
    assert natural_incumbent.warm_start_id is None
    assert natural_incumbent.candidate_token != warm_incumbent.candidate_token


def test_strict_incumbent_snapshot_failure_leaves_previous_commit_unchanged() -> None:
    from nsgablack.core.state.context_keys import (
        KEY_BEST_CANDIDATE_REF,
        KEY_BEST_OBJECTIVE,
    )

    from blackbase.context import InMemorySnapshotStore

    class FailingSnapshotStore(InMemorySnapshotStore):
        def __init__(self):
            super().__init__()
            self.fail_writes = False

        def write(self, *args, **kwargs):
            if self.fail_writes:
                raise RuntimeError("snapshot unavailable")
            return super().write(*args, **kwargs)

    solver = SolverBase(
        _Problem(),
        context_inline_candidate_max_bytes=1,
        snapshot_strict=True,
    )
    from blackbase.evaluation import InMemoryEvaluationEvidenceJournal

    failing_store = FailingSnapshotStore()
    solver.set_snapshot_store(
        failing_store,
        evaluation_evidence_journal=InMemoryEvaluationEvidenceJournal(),
    )
    old_state = solver.set_incumbent(
        IncumbentState(
            candidate=[1.0, 2.0],
            objectives=[1.0, 2.0],
            constraint_violation=0.0,
            score=3.0,
        )
    )
    old_ref = solver.context_store.get(KEY_BEST_CANDIDATE_REF)
    failing_store.fail_writes = True

    with pytest.raises(RuntimeError, match="snapshot unavailable"):
        solver.set_incumbent(
            IncumbentState(
                candidate=[9.0, 9.0],
                objectives=[9.0, 9.0],
                constraint_violation=0.0,
                score=18.0,
            )
        )

    assert solver.get_incumbent() is old_state
    assert np.allclose(solver.best_x, [1.0, 2.0])
    assert solver.best_objective == 3.0
    assert solver._incumbent_candidate_ref == old_ref
    assert solver.context_store.get(KEY_BEST_CANDIDATE_REF) == old_ref
    assert solver.context_store.get(KEY_BEST_OBJECTIVE) == 3.0


def test_incumbent_context_failure_keeps_atomic_old_projection_and_is_audited() -> None:
    from blackbase.context import ContextStore
    from nsgablack.core.state.context_keys import KEY_BEST_OBJECTIVE, KEY_BEST_X

    class FailingContextStore(ContextStore):
        def __init__(self) -> None:
            super().__init__()
            self.fail_patch = False

        def apply_patch(self, values, *, delete_keys=(), ttl_seconds=None):
            if self.fail_patch:
                raise RuntimeError("context projection unavailable")
            return super().apply_patch(
                values,
                delete_keys=delete_keys,
                ttl_seconds=ttl_seconds,
            )

    solver = SolverBase(_Problem())
    store = FailingContextStore()
    solver.set_context_store(store)
    solver.set_incumbent(
        IncumbentState(
            candidate=[1.0, 2.0],
            objectives=[1.0, 2.0],
            constraint_violation=0.0,
            score=3.0,
        )
    )
    store.fail_patch = True

    committed = solver.set_incumbent(
        IncumbentState(
            candidate=[9.0, 9.0],
            objectives=[9.0, 9.0],
            constraint_violation=0.0,
            score=18.0,
        )
    )

    assert solver.get_incumbent() is committed
    assert np.allclose(solver.best_x, [9.0, 9.0])
    assert store.get(KEY_BEST_OBJECTIVE) == 3.0
    assert np.allclose(store.get(KEY_BEST_X), [1.0, 2.0])
    assert solver._incumbent_context_projection_revision < solver._incumbent_commit.revision
    assert solver._incumbent_context_projection_error == {
        "revision": solver._incumbent_commit.revision,
        "error_type": "RuntimeError",
        "message": "context projection unavailable",
    }
    audit = solver.get_incumbent_projection_audit()
    assert audit == {
        "incumbent_revision": solver._incumbent_commit.revision,
        "incumbent_context_projection_revision": 1,
        "incumbent_context_projection_current": False,
        "incumbent_context_projection_error": {
            "revision": solver._incumbent_commit.revision,
            "error_type": "RuntimeError",
            "message": "context projection unavailable",
        },
    }
    direct_result = format_run_result(solver)
    case_result = build_solver_result(solver, {"status": "ok"})
    checkpoint_state = solver.export_incumbent_checkpoint_state()
    for key, value in audit.items():
        assert direct_result[key] == value
        assert case_result.metadata[key] == value
    assert checkpoint_state["incumbent_projection"] == audit


def test_context_build_cannot_replay_a_stale_incumbent_projection() -> None:
    from blackbase.context import InMemoryContextStore
    from nsgablack.core.solver_helpers.context_helpers import build_solver_context
    from nsgablack.core.state.context_keys import KEY_BEST_OBJECTIVE, KEY_BEST_X

    class BlockingContextStore(InMemoryContextStore):
        def __init__(self) -> None:
            super().__init__()
            self.pause_next_update = False
            self.update_started = threading.Event()
            self.release_update = threading.Event()

        def update(self, values, *, ttl_seconds=None):
            if self.pause_next_update:
                self.pause_next_update = False
                self.update_started.set()
                if not self.release_update.wait(timeout=5):
                    raise TimeoutError("test did not release ContextStore update")
            return super().update(values, ttl_seconds=ttl_seconds)

    solver = SolverBase(_Problem())
    store = BlockingContextStore()
    solver.set_context_store(store)
    solver.set_incumbent(
        IncumbentState(
            candidate=[1.0, 2.0],
            objectives=[1.0, 2.0],
            constraint_violation=0.0,
            score=3.0,
        )
    )
    store.pause_next_update = True
    contexts = []
    errors = []

    def build_context() -> None:
        try:
            contexts.append(build_solver_context(solver))
        except Exception as exc:  # pragma: no cover - assertion reports detail
            errors.append(exc)

    worker = threading.Thread(target=build_context)
    worker.start()
    assert store.update_started.wait(timeout=5)
    solver.set_incumbent(
        IncumbentState(
            candidate=[9.0, 9.0],
            objectives=[9.0, 9.0],
            constraint_violation=0.0,
            score=18.0,
        )
    )
    store.release_update.set()
    worker.join(timeout=5)

    assert not worker.is_alive()
    assert errors == []
    assert np.allclose(contexts[0][KEY_BEST_X], [1.0, 2.0])
    assert np.allclose(store.get(KEY_BEST_X), [9.0, 9.0])
    assert store.get(KEY_BEST_OBJECTIVE) == 18.0
    assert solver.get_incumbent_projection_audit()[
        "incumbent_context_projection_current"
    ] is True


def test_candidate_provenance_registry_releases_dead_arrays() -> None:
    solver = SolverBase(_Problem())
    arrays = [np.asarray([float(index), 0.0]) for index in range(200)]
    for array in arrays:
        solver._register_candidate_provenance(
            array,
            solver._new_candidate_provenance(),
        )
    del array
    assert len(solver._candidate_provenance_by_object) == 200

    arrays.clear()
    gc.collect()

    assert solver._candidate_provenance_by_object == {}


def test_active_incumbent_rejects_scalarizer_reconfiguration_immediately() -> None:
    solver = ComposableSolver(_Problem())
    solver._update_best(
        np.asarray([[1.0, 2.0]]),
        np.asarray([[1.0, 2.0]]),
        np.asarray([0.0]),
    )

    def replacement(objective_row, violation, context):
        del violation, context
        return float(np.sum(objective_row))

    with pytest.raises(ScalarizationError, match="active run"):
        solver.set_incumbent_scalarizer(
            replacement,
            policy_id="replacement/v1",
            context={"weights": [1.0, 1.0]},
        )

    assert solver.incumbent_scalarizer_id == "objective_sum/v1"
    assert solver.get_incumbent().policy_id == "objective_sum/v1"


def test_direct_incumbent_commit_rejects_mismatched_selection_policy() -> None:
    solver = ComposableSolver(_Problem())

    with pytest.raises(ScalarizationError, match="does not match"):
        solver.set_incumbent(
            IncumbentState(
                candidate=[1.0, 2.0],
                objectives=[1.0, 2.0],
                constraint_violation=0.0,
                score=3.0,
                policy_id="another-policy/v1",
            )
        )

    assert solver.get_incumbent() is None

    solver.set_incumbent_scalarizer(
        lambda objective_row, violation, context: float(
            np.dot(objective_row, context["weights"])
        ),
        policy_id="weighted/v1",
        context={"weights": [0.75, 0.25]},
    )
    with pytest.raises(ScalarizationError, match="policy context"):
        solver.set_incumbent(
            IncumbentState(
                candidate=[1.0, 2.0],
                objectives=[1.0, 2.0],
                constraint_violation=0.0,
                score=1.25,
                policy_id="weighted/v1",
                policy_context={"weights": [0.25, 0.75]},
            )
        )

    assert solver.get_incumbent() is None


def test_incumbent_commit_revalidates_policy_after_snapshot_staging() -> None:
    from blackbase.context import InMemorySnapshotStore

    class BlockingSnapshotStore(InMemorySnapshotStore):
        def __init__(self) -> None:
            super().__init__()
            self.write_finished = threading.Event()
            self.release_write = threading.Event()
            self.last_key = None

        def write(self, *args, **kwargs):
            handle = super().write(*args, **kwargs)
            self.last_key = handle.key
            self.write_finished.set()
            if not self.release_write.wait(timeout=5):
                raise TimeoutError("test did not release SnapshotStore write")
            return handle

    solver = ComposableSolver(_Problem())
    solver.context_inline_candidate_max_bytes = 1
    store = BlockingSnapshotStore()
    from blackbase.evaluation import InMemoryEvaluationEvidenceJournal

    solver.set_snapshot_store(
        store,
        evaluation_evidence_journal=InMemoryEvaluationEvidenceJournal(),
    )
    errors = []

    def commit_incumbent() -> None:
        try:
            solver.set_incumbent(
                IncumbentState(
                    candidate=[1.0, 2.0],
                    objectives=[1.0, 2.0],
                    constraint_violation=0.0,
                    score=3.0,
                )
            )
        except Exception as exc:
            errors.append(exc)

    worker = threading.Thread(target=commit_incumbent)
    worker.start()
    assert store.write_finished.wait(timeout=5)
    solver.set_incumbent_scalarizer(
        lambda objective_row, violation, context: float(objective_row[0]),
        policy_id="replacement/v1",
    )
    store.release_write.set()
    worker.join(timeout=5)

    assert not worker.is_alive()
    assert len(errors) == 1
    assert isinstance(errors[0], ScalarizationError)
    assert solver.get_incumbent() is None
    assert store.last_key is not None
    assert store.read(store.last_key) is None
