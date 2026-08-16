from __future__ import annotations

import concurrent.futures
import threading

import numpy as np
import pytest

from blackbase.project.runtime import ProjectL0Runtime, ProjectRuntimeConfig
from blackbase.resources import ResourceOffer, ResourcePolicy, ResourceRequest
from nsgablack.adapters import AlgorithmAdapter
from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.blank_solver import SolverBase
from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.core.control_plane import EvaluationBudgetExceeded
from nsgablack.core.evaluation_runtime import EvaluationProviderContractError


class _Problem(BlackBoxProblem):
    def __init__(self) -> None:
        super().__init__(
            name="shared-budget",
            dimension=1,
            bounds={"x0": (-10.0, 10.0)},
            objectives=["f"],
        )

    def evaluate(self, candidate):
        value = float(np.asarray(candidate, dtype=float).reshape(-1)[0])
        return np.array([value * value], dtype=float)


class _FailThirdProblem(_Problem):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def evaluate(self, candidate):
        self.calls += 1
        if self.calls == 3:
            raise RuntimeError("third evaluation failed")
        return super().evaluate(candidate)


class _NullProvider:
    name = "null-provider"
    semantic_mode = "equivalent"

    def __init__(self, *, population: bool) -> None:
        self.population = bool(population)
        self.calls = 0

    def can_handle_individual(self, solver, candidate, context):
        del solver, candidate, context
        return not self.population

    def evaluate_individual(self, solver, candidate, context, individual_id=None):
        del solver, candidate, context, individual_id
        self.calls += 1
        return None

    def can_handle_population(self, solver, population, context):
        del solver, population, context
        return self.population

    def evaluate_population(self, solver, population, context):
        del solver, population, context
        self.calls += 1
        return None


def _runtime(tmp_path, *, limit: int) -> ProjectL0Runtime:
    return ProjectL0Runtime(
        ProjectRuntimeConfig(
            offer=ResourceOffer(threads=2, gpus=0, backend="local"),
            policy=ResourcePolicy(max_workers=2, max_threads=2, max_gpus=0),
            default_request=ResourceRequest(workers=1, threads=1),
            namespace="nsgablack-budget-test",
            lease_backend="sqlite",
            lease_path="l0.sqlite",
            lease_ttl_seconds=2.0,
            lease_heartbeat_seconds=0.2,
            budgets={"evaluations": limit},
        ),
        project_root=tmp_path,
    )


def _solver(runtime: ProjectL0Runtime, name: str) -> SolverBase:
    lease = runtime.acquire_case(name)
    context = runtime.resource_context(lease, case_name=name)
    return SolverBase(_Problem(), resource_context=context)


def test_two_solvers_cannot_overbook_the_same_project_evaluation_budget(tmp_path) -> None:
    runtime = _runtime(tmp_path, limit=2)
    solvers = (_solver(runtime, "a"), _solver(runtime, "b"))
    population = np.array([[1.0], [2.0]], dtype=float)
    barrier = threading.Barrier(2)

    def evaluate(solver: SolverBase):
        barrier.wait(timeout=2.0)
        try:
            objectives, _ = solver.evaluate_population(population)
            return objectives
        except EvaluationBudgetExceeded:
            return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(evaluate, solvers))

    assert sum(item is not None for item in results) == 1
    assert sorted(solver.evaluation_count for solver in solvers) == [0, 2]
    status = runtime.budget_authority.status("evaluations")
    assert status.committed == 2
    assert status.reserved == 0
    assert status.remaining == 0


def test_solver_allowance_and_direct_evaluation_share_the_project_limit(tmp_path) -> None:
    runtime = _runtime(tmp_path, limit=3)
    first = _solver(runtime, "first")
    second = _solver(runtime, "second")

    first.evaluate_population(np.array([[1.0], [2.0]], dtype=float))

    assert second.evaluation_batch_allowance(5) == 1
    with pytest.raises(EvaluationBudgetExceeded):
        second.evaluate_population(np.array([[3.0], [4.0]], dtype=float))
    second.evaluate_individual(np.array([3.0], dtype=float))

    assert first.evaluation_count == 2
    assert second.evaluation_count == 1
    assert second.shared_evaluation_budget_status() == {
        "scope": runtime.budget_authority.scope,
        "budget": "evaluations",
        "limit": 3,
        "committed": 3,
        "reserved": 0,
        "remaining": 0,
        "reclaimed": 0,
    }


def test_concurrent_solver_runs_stop_cleanly_when_one_wins_the_final_budget(tmp_path) -> None:
    runtime = _runtime(tmp_path, limit=2)
    propose_barrier = threading.Barrier(2)

    class _TwoCandidateAdapter(AlgorithmAdapter):
        def propose(self, solver, context):
            del solver, context
            propose_barrier.wait(timeout=2.0)
            return [np.array([1.0]), np.array([2.0])]

        def update(self, solver, candidates, evaluation, context):
            del solver, candidates, evaluation, context

    solvers = []
    for name in ("run-a", "run-b"):
        lease = runtime.acquire_case(name)
        context = runtime.resource_context(lease, case_name=name)
        solvers.append(
            ComposableSolver(
                _Problem(),
                adapter=_TwoCandidateAdapter("two-candidate"),
                resource_context=context,
            )
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda solver: solver.run(max_steps=1), solvers))

    assert sorted(solver.evaluation_count for solver in solvers) == [0, 2]
    assert sorted(result["status"] for result in results) == ["ok", "stopped"]
    assert runtime.budget_authority.status("evaluations").committed == 2


def test_partial_batch_failure_keeps_every_dispatched_evaluation_consumed(tmp_path) -> None:
    runtime = _runtime(tmp_path, limit=3)
    lease = runtime.acquire_case("partial-failure")
    context = runtime.resource_context(lease, case_name="partial-failure")
    problem = _FailThirdProblem()
    solver = SolverBase(problem, resource_context=context)

    with pytest.raises(RuntimeError, match="third evaluation failed"):
        solver.evaluate_population(np.array([[1.0], [2.0], [3.0]], dtype=float))

    assert problem.calls == 3
    assert solver.evaluation_count == 3
    assert solver.evaluation_budget_reserved == 0
    status = runtime.budget_authority.status("evaluations")
    assert status.committed == 3
    assert status.reserved == 0
    assert status.remaining == 0
    with pytest.raises(EvaluationBudgetExceeded):
        solver.evaluate_individual(np.array([4.0], dtype=float))


@pytest.mark.parametrize("population_size", [1, 2])
def test_accepting_provider_cannot_return_none_and_trigger_an_unbudgeted_fallback(
    tmp_path,
    population_size: int,
) -> None:
    runtime = _runtime(tmp_path, limit=population_size)
    solver = _solver(runtime, f"null-provider-{population_size}")
    provider = _NullProvider(population=population_size > 1)
    solver.register_evaluation_provider(provider)

    with pytest.raises(EvaluationProviderContractError, match="returned None"):
        if population_size == 1:
            solver.evaluate_individual(np.array([1.0], dtype=float))
        else:
            solver.evaluate_population(
                np.arange(population_size, dtype=float).reshape(-1, 1)
            )

    assert provider.calls == 1
    assert solver.evaluation_count == population_size
    status = runtime.budget_authority.status("evaluations")
    assert status.committed == population_size
    assert status.reserved == 0
    assert status.remaining == 0
