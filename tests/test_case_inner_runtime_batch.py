"""Standard child-Case batching keeps outer Solver semantics on one thread."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import threading

import numpy as np
import pytest

from blackbase.preferences import PreferenceDelta
from blackbase.project import CaseFailure, CaseRunRequest, CaseRunResult
from blackbase.resources import CancellationToken, DataRef
from blackbase.types import CandidateBatch, Feedback
from nsgablack.core import (
    BlackBoxProblem, CaseInnerRuntimeEvaluator, ChildCaseExecutionError,
    ComposableSolver, EvolutionSolver, FeasibleEvaluationAcceptance,
)


class BatchRuntime:
    """Exercise the real CaseStage barrier with an in-process test runtime."""

    def __init__(self, *, fail_index=None):
        self.request = CaseRunRequest(
            project_name="batch-test", stage_name="outer", case_name="parent",
            resource_context={"threads": 2, "grant": {"threads": 2, "workers": 2}},
        )
        self.fail_index = fail_index
        self.barrier = threading.Barrier(2)
        self.second_finished = threading.Event()
        self.requests = []
        self.finished = []

    def checkpoint(self):
        pass

    def stage_worker_capacity(self, workers):
        return min(workers, 2)

    def stage_executor(self, workers):
        return ThreadPoolExecutor(max_workers=self.stage_worker_capacity(workers))

    def cancellation_token(self, ref):
        return CancellationToken(ref)

    def invoke(self, request, *, intermediate_cancellations=()):
        index = int(request.inputs["outer_individual_id"])
        self.requests.append(request)
        self.barrier.wait(timeout=3)
        if index == 0:
            assert self.second_finished.wait(timeout=3)
        self.finished.append(index)
        if index == 1:
            self.second_finished.set()
        request = replace(request, identity=self.request.identity.child())
        if index == self.fail_index:
            return CaseRunResult(
                request=request, status="failed", exit_code=1,
                failure=CaseFailure(kind="domain_failure", message="explicit child failure"),
            )
        return CaseRunResult(request=request, status="succeeded", output={"index": index})


def project(_solver, _candidate, result):
    index = result.output["index"]
    return Feedback(
        objectives=np.array([float(index + 1)]), gradients=np.array([10.0 + index]),
        info={"child_index": index, "child_run_id": result.identity.case_run_id},
    )


def test_batch_executes_together_but_factories_and_projection_use_caller_thread():
    runtime = BatchRuntime()
    caller_thread = threading.get_ident()
    factory_threads, projector_threads = [], []
    class Solver:
        case_runtime = runtime
        generation = 3
    def configure(_solver, row, context):
        factory_threads.append(threading.get_ident())
        with pytest.raises(ValueError):
            row.setflags(write=True)
        return {"tag": context["tag"]}
    def checked_project(*args):
        projector_threads.append(threading.get_ident())
        return project(*args)
    evaluator = CaseInnerRuntimeEvaluator(
        case_name="inner", projector=checked_project, max_workers=2,
        component_overrides_factory=configure,
    )
    values = evaluator.evaluate_batch(
        solver=Solver(), population=np.array([[0.0], [0.0]]),
        contexts=({"tag": "left"}, {"tag": "right"}),
    )
    assert runtime.finished == [1, 0]
    assert [item.info["child_index"] for item in values] == [0, 1]
    assert factory_threads == projector_threads == [caller_thread, caller_thread]
    assert {item.component_overrides["tag"] for item in runtime.requests} == {"left", "right"}
    assert len({result.identity.case_run_id for result in evaluator.last_batch_results}) == 2
    assert evaluator.stats["calls"] == evaluator.stats["success"] == 2


def test_child_failure_joins_batch_without_partial_projection_or_replay():
    runtime = BatchRuntime(fail_index=1)
    projections = []
    solver = type("Solver", (), {"case_runtime": runtime})()
    evaluator = CaseInnerRuntimeEvaluator(
        case_name="inner", max_workers=2,
        projector=lambda *args: projections.append(args),
    )
    with pytest.raises(ChildCaseExecutionError) as caught:
        evaluator.evaluate_batch(solver=solver, population=np.array([[1.0], [2.0]]))
    assert caught.value.result.failure.kind == "domain_failure"
    assert runtime.finished == [1, 0]
    assert len(runtime.requests) == len(evaluator.last_batch_results) == 2
    assert projections == []


class Problem(BlackBoxProblem):
    def __init__(self, evaluator):
        super().__init__(dimension=1, objectives=["cost"], bounds=[(-2.0, 2.0)])
        self.inner_runtime_evaluator = evaluator

    def evaluate(self, candidate):
        raise AssertionError("a failed or batched child must never replay Problem.evaluate")

    def evaluate_constraints(self, candidate):
        return [max(0.0, float(candidate[0]))]


class Preference:
    preference_keys = ("objectives.0",)

    def __init__(self):
        self.threads = []

    def preferences(self, candidate, feedback, context):
        self.threads.append(threading.get_ident())
        return (PreferenceDelta("objectives.0", 3.0, "caller-thread preference"),)


@pytest.mark.parametrize("evolution", [False, True], ids=["composable", "evolution"])
def test_solver_batch_keeps_raw_constraints_bias_and_outer_count(evolution):
    runtime = BatchRuntime()
    evaluator = CaseInnerRuntimeEvaluator(case_name="inner", projector=project, max_workers=2)
    bias = Preference()
    options = dict(bias_module=bias, ignore_constraint_violation_when_bias=True)
    solver = (
        EvolutionSolver(Problem(evaluator), enable_parallel=True, **options)
        if evolution else ComposableSolver(Problem(evaluator), **options)
    )
    solver.case_runtime = runtime
    hooks = []
    solver.plugin_manager.on_evaluate_start = lambda row, context: hooks.append(
        ("start", int(context["individual_id"]), threading.get_ident())
    )
    solver.plugin_manager.on_evaluate_end = lambda row, result, context: hooks.append(
        ("end", int(context["individual_id"]), threading.get_ident())
    )
    values = np.array([[-1.0], [1.0]])
    objectives, violations = solver.evaluate_population(values)
    batch = solver.get_last_feedback_batch()
    np.testing.assert_allclose(objectives[:, 0], [4.0, 5.0])
    np.testing.assert_allclose(violations, [0.0, 0.0])
    np.testing.assert_allclose(batch.raw_objectives[:, 0], [1.0, 2.0])
    np.testing.assert_allclose(batch.raw_violations, [0.0, 1.0])
    assert [item.info["child_index"] for item in batch.items] == [0, 1]
    assert [item.gradients[0] for item in batch.items] == [10.0, 11.0]
    assert solver.evaluation_count == 2
    assert batch.metadata["evaluation_path"] == "inner_case_batch"
    assert bias.threads == [threading.get_ident(), threading.get_ident()]
    assert hooks == [
        (event, index, threading.get_ident())
        for event in ("start", "end") for index in (0, 1)
    ]
    disposition = FeasibleEvaluationAcceptance().select(
        CandidateBatch.from_candidates(values), batch, {},
    )
    assert disposition.accepted_indices == (0,)


def test_individual_provider_keeps_arbitration_before_inner_batch():
    runtime = BatchRuntime()
    evaluator = CaseInnerRuntimeEvaluator(case_name="inner", projector=project, max_workers=2)
    solver = ComposableSolver(Problem(evaluator))
    solver.case_runtime = runtime
    class Provider:
        name = "individual-owner"
        semantic_mode = "exact"
        def can_handle_population(self, *_):
            return False
        def can_handle_individual(self, *_):
            return True
        def evaluate_individual(self, *args, **kwargs):
            return np.array([99.0]), 0.0
    solver.register_evaluation_provider(Provider())
    objectives, _violations = solver.evaluate_population(np.array([[-1.0], [1.0]]))
    np.testing.assert_allclose(objectives[:, 0], [99.0, 99.0])
    assert runtime.requests == []
    assert evaluator.stats["calls"] == 0
    assert solver.evaluation_count == 2


def test_failed_batch_retains_outer_dispatch_cost_and_no_feedback_delivery():
    runtime = BatchRuntime(fail_index=1)
    evaluator = CaseInnerRuntimeEvaluator(case_name="inner", projector=project, max_workers=2)
    solver = ComposableSolver(Problem(evaluator))
    solver.case_runtime = runtime
    with pytest.raises(ChildCaseExecutionError):
        solver.evaluate_population(np.array([[-1.0], [1.0]]))
    assert solver.evaluation_count == 2
    assert len(runtime.requests) == 2
    assert evaluator.stats["success"] == 0


@pytest.mark.parametrize("workers", [0, -1, 1.5, True])
def test_invalid_batch_concurrency_is_rejected(workers):
    with pytest.raises(ValueError, match="positive integer"):
        CaseInnerRuntimeEvaluator(case_name="inner", projector=project, max_workers=workers)


def test_batch_shape_and_context_alignment_are_validated_before_invocation():
    evaluator = CaseInnerRuntimeEvaluator(case_name="inner", projector=project, max_workers=2)
    with pytest.raises(ValueError, match="2-D"):
        evaluator.evaluate_batch(solver=object(), population=np.array([1.0]))
    with pytest.raises(ValueError, match="align"):
        evaluator.evaluate_batch(solver=object(), population=np.ones((2, 1)), contexts=({},))


def test_equal_candidates_preserve_distinct_bound_tokens():
    runtime = BatchRuntime()
    values = np.array([[1.0], [1.0]])
    tokens = {values[0].ctypes.data: "left", values[1].ctypes.data: "right"}
    class Provenance:
        def __init__(self, token):
            self.token = token
        def as_dict(self):
            return {"candidate_token": self.token}
    class Solver:
        case_runtime = runtime
        def candidate_provenance_for(self, row):
            return Provenance(tokens[row.ctypes.data])
    evaluator = CaseInnerRuntimeEvaluator(case_name="inner", projector=project, max_workers=2)
    evaluator.evaluate_batch(solver=Solver(), population=values)
    ordered = sorted(runtime.requests, key=lambda request: request.inputs["outer_individual_id"])
    assert [request.inputs["candidate_provenance"]["candidate_token"] for request in ordered] == ["left", "right"]


def test_bare_solver_accepts_case_input_locations_without_loading_or_claiming_authority():
    evaluator = CaseInnerRuntimeEvaluator(case_name="inner", projector=project)
    solver = ComposableSolver(Problem(evaluator))
    source = DataRef(uri="memory://declared-source", kind="data", backend="memory")
    refs = {"dataset": source}
    assert solver.set_input_artifacts(refs) is solver
    refs.clear()
    assert solver.input_artifacts == {"dataset": source}
    with pytest.raises(TypeError):
        solver.input_artifacts["dataset"] = source
    with pytest.raises(TypeError, match="DataRef"):
        solver.set_input_artifacts({"dataset": {"raw_data": [1, 2]}})
    assert solver.evaluation_count == 0 and solver.case_runtime is None
