"""Thread scheduling preserves the Solver's evaluation and identity authority."""
from collections import Counter
import threading

import numpy as np
import pytest

from blackbase.preferences import PreferenceDelta
from blackbase.project.runtime import ProjectL0Runtime, ProjectRuntimeConfig
from blackbase.resources import ResourceOffer, ResourcePolicy, ResourceRequest
from blackbase.types import Feedback
from nsgablack.adapters import AlgorithmAdapter
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.core.control_plane import BudgetController, EvaluationBudgetExceeded
from nsgablack.core.evaluation_feedback import OptimizationFeedbackBatch
from nsgablack.plugins import Plugin
from nsgablack.representation.base import RepresentationPipeline
from nsgablack.utils.parallel import with_parallel_evaluation


ParallelSolver = with_parallel_evaluation(ComposableSolver)


class Problem(BlackBoxProblem):
    def __init__(self, fail=None):
        super().__init__(dimension=1, objectives=["cost"], bounds=[(-10., 10.)])
        self.calls, self.lock, self.fail = [], threading.Lock(), fail

    def evaluate(self, candidate, context=None):
        value = float(candidate[0])
        with self.lock:
            self.calls.append((value, threading.get_ident()))
        if value == self.fail:
            raise TypeError("actual Problem failure")
        context = context or {}
        shared = context.get("probe_shared")
        if shared is not None:
            shared["rows"].append(value)
        return Feedback(objectives=[value * value], gradients=[2 * value], loss=value * value,
                        metrics={"row": value}, signals={"measured": True}, info={
                            "seen_token": context.get("candidate_token"),
                            "hook_marker": context.get("hook_marker"),
                            "local_rows": None if shared is None else list(shared["rows"]),
                        })

    def evaluate_constraints(self, candidate):
        return np.array([float(candidate[0]) - 2.])


class Preference:
    preference_keys = ("objectives.0",)

    def __init__(self):
        self.lock, self.observed = threading.RLock(), []

    def preferences(self, candidate, feedback, context):
        self.observed.append((threading.get_ident(), np.array(context.get("constraints", []), copy=True),
                              context.get("constraint_violation", 0.), feedback.info.get("seen_token")))
        return (PreferenceDelta("objectives.0", 3., "fixture selection preference"),)


class Hooks(Plugin):
    def __init__(self):
        super().__init__(name="parallel_fixture_hooks")
        self.starts, self.ends, self.shared = [], [], {"rows": []}

    def on_evaluate_start(self, candidate, context):
        context["hook_marker"] = "row-" + str(context["individual_id"])
        context["probe_shared"] = self.shared
        self.starts.append((float(candidate[0]), threading.get_ident()))

    def on_evaluate_end(self, candidate, result, context):
        self.ends.append((float(candidate[0]), threading.get_ident(), np.array(context.get("constraints", []), copy=True),
                          context.get("constraint_violation", 0.), context.get("candidate_token")))


class Proposer(AlgorithmAdapter):
    def __init__(self, count=8):
        super().__init__(name="parallel_batch_fixture")
        self.count, self.feedback = count, None

    def propose(self, control, context):
        return [np.array([float(i)]) for i in range(self.count)]

    def update(self, control, candidates, feedback, context):
        self.feedback = feedback


def build(*, count=8, parallel=True, backend="thread", problem=None, resources=None):
    problem = problem if problem is not None else Problem()
    bias, hooks, adapter = Preference(), Hooks(), Proposer(count)
    control = ParallelSolver(problem, adapter=adapter, bias_module=bias,
        ignore_constraint_violation_when_bias=True, enable_parallel=parallel,
        parallel_backend=backend, parallel_max_workers=4, plugin_strict=True,
        resource_context=resources)
    control.add_plugin(hooks)
    return control, problem, bias, hooks, adapter


@pytest.mark.parametrize("count", [3, 8])
def test_feedback_bias_hooks_and_count_across_thread_threshold(count):
    control, problem, bias, hooks, _ = build(count=count)
    values = np.arange(count, dtype=float).reshape(-1, 1)
    original = values.copy()
    records = control.prepare_candidate_provenance(values)
    control.activate_candidate_provenance(values, records)
    objectives, violations = control.evaluate_population(values)
    feedback = control.get_last_feedback_batch()
    main_thread = threading.get_ident()
    np.testing.assert_array_equal(values, original)
    np.testing.assert_allclose(objectives[:, 0], values[:, 0] ** 2 + 3)
    np.testing.assert_array_equal(violations, np.zeros(count))
    np.testing.assert_array_equal(feedback.raw_objectives[:, 0], values[:, 0] ** 2)
    np.testing.assert_array_equal(feedback.raw_violations, np.maximum(values[:, 0] - 2, 0))
    assert control.evaluation_count == len(problem.calls) == len(hooks.starts) == len(hooks.ends) == count
    assert hooks.shared == {"rows": []}
    assert all(item[0] == main_thread for item in bias.observed)
    assert all(item[1] == main_thread for item in hooks.starts + hooks.ends)
    for index, item in enumerate(feedback.items):
        assert item.info["seen_token"] == records[index].candidate_token
        assert item.info["hook_marker"] == "row-" + str(index)
        assert item.info["local_rows"] == (float(index),)
        assert item.metrics["row"] == index and item.loss == index ** 2
        np.testing.assert_array_equal(item.gradients, [2. * index])
        assert item.signals["measured"] is True
        np.testing.assert_array_equal(hooks.ends[index][2], [index - 2.])
        assert hooks.ends[index][3] == max(0., index - 2.)
    assert control.parallel_evaluator.get_stats()["last_execution_mode"] == ("thread" if count >= 5 else "inline")
    dispatch = control.parallel_evaluator.last_dispatch_stats
    assert dispatch["input_count"] == dispatch["started_count"] == dispatch["completed_count"] == count
    assert set(dispatch["thread_ids"]) == {thread_id for _, thread_id in problem.calls}
    assert dispatch["distinct_processes"] == 1
    assert dispatch["requested_workers"] == 4 and dispatch["effective_workers"] == (4 if count >= 5 else 1)
    assert dispatch["wall_seconds"] >= 0 and dispatch["process_cpu_seconds"] >= 0
    dispatch["input_count"] = -1
    assert control.parallel_evaluator.last_dispatch_stats["input_count"] == count
    assert all(thread_id == main_thread for _, thread_id in problem.calls) if count < 5 else all(
        thread_id != main_thread for _, thread_id in problem.calls)


def test_thread_numerical_result_matches_existing_serial_solver():
    values = np.arange(8, dtype=float).reshape(-1, 1)
    serial, _, _, _, _ = build(parallel=False)
    parallel, _, _, _, _ = build()
    first, second = serial.evaluate_population(values), parallel.evaluate_population(values)
    np.testing.assert_array_equal(first[0], second[0])
    np.testing.assert_array_equal(first[1], second[1])
    np.testing.assert_array_equal(serial.get_last_feedback_batch().raw_objectives,
                                  parallel.get_last_feedback_batch().raw_objectives)
    np.testing.assert_array_equal(serial.get_last_feedback_batch().raw_violations,
                                  parallel.get_last_feedback_batch().raw_violations)


def test_cumulative_thread_evidence_survives_a_final_small_inline_batch():
    control, problem, _, _, _ = build()
    control.evaluate_population(np.arange(8, dtype=float).reshape(-1, 1))
    first = control.parallel_evaluator.last_dispatch_stats
    control.evaluate_population(np.array([[9.]]))
    last = control.parallel_evaluator.last_dispatch_stats
    cumulative = control.parallel_evaluator.raw_dispatch_stats
    assert first["execution_mode"] == "thread" and last["execution_mode"] == "inline"
    assert cumulative["batches"] == 2 and cumulative["thread_batches"] == cumulative["inline_batches"] == 1
    assert cumulative["started_count"] == cumulative["completed_count"] == len(problem.calls) == 9
    assert cumulative["thread_started_count"] == cumulative["thread_completed_count"] == 8
    assert cumulative["inline_started_count"] == cumulative["inline_completed_count"] == 1
    assert cumulative["max_distinct_threads"] == first["distinct_threads"]
    assert cumulative["process_ids"] == first["process_ids"] == last["process_ids"]
    assert cumulative["total_raw_wall_seconds"] == first["wall_seconds"] + last["wall_seconds"]
    assert cumulative["total_raw_cpu_seconds"] == first["process_cpu_seconds"] + last["process_cpu_seconds"]
    cumulative["thread_batches"] = 0
    assert control.parallel_evaluator.raw_dispatch_stats["thread_batches"] == 1


def test_lifecycle_budget_8_to_2_repairs_and_evaluates_only_two_then_no_ghost(tmp_path):
    runtime = ProjectL0Runtime(ProjectRuntimeConfig(
        offer=ResourceOffer(threads=4), policy=ResourcePolicy(max_workers=1, max_threads=4),
        default_request=ResourceRequest(threads=4), namespace="parallel-closure-fixture",
        lease_backend="sqlite", lease_path="lease.sqlite", budgets={"evaluations": 2}), project_root=tmp_path)
    lease = runtime.acquire_case("fixture")
    try:
        control, problem, _, hooks, adapter = build(resources=runtime.resource_context(lease, case_name="fixture"))
        repaired = []
        class Repair:
            def repair(self, candidate, context=None):
                repaired.append(float(candidate[0]))
                return np.array(candidate, copy=True)
        control.representation_pipeline = RepresentationPipeline(repair=Repair())
        first = control.step()
        generation = control.generation
        second = control.step()
        assert first.committed and first.proposals == 8 and first.evaluations == 2
        assert second.evaluations == 0 and not second.committed and control.generation == generation
        assert repaired == [0., 1.]
        assert len(problem.calls) == len(hooks.starts) == len(hooks.ends) == control.evaluation_count == 2
        assert adapter.feedback.candidate_count == 2
        assert runtime.budget_authority.status("evaluations").committed == 2
        assert runtime.budget_authority.status("evaluations").reserved == 0
        assert runtime.budget_authority.status("evaluations").remaining == 0
    finally:
        runtime.release(lease)


def test_direct_budget_rejection_dispatches_nothing():
    control, problem, _, hooks, _ = build()
    control.register_controller(BudgetController(max_evaluations=2))
    with pytest.raises(EvaluationBudgetExceeded):
        control.evaluate_population(np.arange(8, dtype=float).reshape(-1, 1))
    assert control.evaluation_count == len(problem.calls) == len(hooks.starts) == len(hooks.ends) == 0


@pytest.mark.parametrize("backend", ["process", "ray", "joblib", "auto"])
def test_unsupported_formal_backend_is_rejected_before_dispatch(backend):
    control, problem, _, hooks, _ = build(backend=backend)
    with pytest.raises(ValueError, match="thread.*only"):
        control.evaluate_population(np.arange(8, dtype=float).reshape(-1, 1))
    assert len(problem.calls) == control.evaluation_count == len(hooks.starts) == 0


def test_worker_failure_propagates_without_retry_or_serial_fallback():
    control, problem, _, hooks, _ = build(problem=Problem(fail=3.))
    with pytest.raises(TypeError, match="actual Problem failure"):
        control.evaluate_population(np.arange(8, dtype=float).reshape(-1, 1))
    assert all(count == 1 for count in Counter(value for value, _ in problem.calls).values())
    assert control.parallel_evaluator.get_stats()["error_count"] == 1
    assert control.parallel_evaluator.get_stats()["retry_count"] == 0
    assert hooks.ends == []


def test_worker_constraint_failure_is_not_reinterpreted_as_missing_constraints():
    class BrokenConstraints(Problem):
        def evaluate_constraints(self, candidate):
            raise AttributeError("actual constraint failure")
    control, problem, _, _, _ = build(problem=BrokenConstraints())
    with pytest.raises(AttributeError, match="actual constraint failure"):
        control.evaluate_population(np.arange(8, dtype=float).reshape(-1, 1))
    assert all(count == 1 for count in Counter(value for value, _ in problem.calls).values())


def test_new_unbound_arrays_do_not_inherit_old_batch_token_or_shared_token():
    control, _, _, _, _ = build()
    old = np.arange(8, dtype=float).reshape(-1, 1)
    records = control.prepare_candidate_provenance(old)
    control.activate_candidate_provenance(old, records)
    control.context_store.set("candidate_token", "stale-shared-token")
    control.evaluate_population(old.copy())
    assert all(item.info["seen_token"] is None for item in control.get_last_feedback_batch().items)


def test_unsupported_feedback_info_fails_without_silent_array_conversion():
    class UnsupportedInfo(Problem):
        def evaluate(self, candidate, context=None):
            return Feedback(objectives=[1.], info={"live_lock": threading.Lock()})
    control, _, _, _, _ = build(problem=UnsupportedInfo())
    with pytest.raises(TypeError):
        control.evaluate_population(np.arange(8, dtype=float).reshape(-1, 1))


def test_provider_retains_dispatch_ownership_and_rich_feedback():
    control, problem, _, _, _ = build()
    class Provider:
        name, semantic_mode = "fixture_provider", "exact"
        def can_handle_individual(self, *args): return False
        def can_handle_population(self, *args): return True
        def evaluate_population(self, solver, population, context):
            return OptimizationFeedbackBatch.from_feedback([
                Feedback(objectives=[9.], info={"provider_row": i}) for i in range(len(population))])
    control.register_evaluation_provider(Provider())
    objectives, _ = control.evaluate_population(np.arange(8, dtype=float).reshape(-1, 1))
    assert problem.calls == [] and control.evaluation_count == 8
    np.testing.assert_array_equal(objectives[:, 0], [12.] * 8)
    assert [item.info["provider_row"] for item in control.get_last_feedback_batch().items] == list(range(8))
