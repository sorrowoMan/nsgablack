"""Final task selections retain exact identities independently of trial history."""
from __future__ import annotations

import copy

import numpy as np
import pytest

from blackbase.orchestration import ExecutionPlan
from blackbase.types import CandidateBatch, UnknownState
from nsgablack.adapters import (
    FixedCandidateAdapter, MultiStrategyConfig, PoolTaskSpec, SearchPlanAdapter,
    StrategySpec, VNSAdapter,
)
from nsgablack.core import BlackBoxProblem, ComposableSolver, PoolRetentionPolicy, StepOutcome
from nsgablack.plugins import CheckpointResumePlugin
from nsgablack.representation import RepresentationPipeline


class Sphere(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, objectives=["min"], bounds=[(-100., 100.)])
        self.calls = []

    def evaluate(self, candidate):
        self.calls.append(float(candidate[0]))
        return [float(candidate[0] ** 2)]


class Descend:
    context_requires = ("vns_k",)

    def initialize(self, problem, context):
        return np.array([10.])

    def mutate(self, candidate, context):
        return candidate - (1. + float(context.get("vns_k", 0)))


def seeds(control, context):
    return control.solution_pool.select(stage="initial")


def build(*, output="history", values=(10., 20.), repeat=1, tail=False,
          local=None, steps=2, retention=False):
    local = local or VNSAdapter(name="local_vns", batch_size=1, restart_on_stagnation=False)
    plan = ExecutionPlan.repeat(ExecutionPlan.leaf("local"), count=repeat)
    strategies = [StrategySpec(local, "local", pool_task=PoolTaskSpec(
        seeds, steps=steps, output=output, count="all", shuffle=False))]
    if tail:
        plan = ExecutionPlan.serial(plan, ExecutionPlan.leaf("tail", steps=3))
        strategies.append(StrategySpec(FixedCandidateAdapter(name="tail"), "tail"))
    adapter = SearchPlanAdapter(plan, strategies=strategies,
        config=MultiStrategyConfig(total_batch_size=1, adapt_weights=False))
    operator = Descend()
    solver = ComposableSolver(Sphere(), adapter=adapter,
        representation_pipeline=RepresentationPipeline(initializer=operator, mutator=operator))
    solver.set_random_seed(119)
    if retention:
        solver.set_solution_pool_retention(PoolRetentionPolicy(idle_steps=1))
    solver.setup()
    if values:
        batch = CandidateBatch.from_candidates(
            [UnknownState([float(value)], {"source": index}) for index, value in enumerate(values)],
            candidate_tokens=tuple(f"seed:{index}" for index in range(len(values))))
        solver.store_solutions(batch)
    return solver, adapter, adapter.units[0].adapter


def complete(solver, updates=4):
    for _ in range(updates):
        assert solver.step().committed


@pytest.mark.parametrize("replacement", ["collection", "same-kind"])
def test_dropped_final_view_cannot_be_redirected_by_reusing_its_name(replacement):
    solver, adapter, task = build()
    complete(solver)
    original = task.get_pool_task_results(solver)
    receipt = task.get_state()["pool_task"]["result_views"][0]
    name = receipt["descriptor"]["name"]
    solver.solution_pool.drop_subpool(name)
    if replacement == "collection":
        solver.solution_pool.create_subpool(name, original[1:])
    else:
        solver.solution_pool.publish_subpool_view(name, original[1:],
            created_by=receipt["created_by"])
    assert solver.solution_pool.subpool_descriptor(name)["view_id"] != receipt["descriptor"]["view_id"]
    with pytest.raises(ValueError, match="identity or interpretation changed"):
        task.get_pool_task_results(solver)
    assert task.task_status["status"] == "done"


def test_same_view_identity_with_a_new_revision_is_not_the_original_final_selection():
    solver, adapter, task = build()
    complete(solver)
    original = task.get_pool_task_results(solver)
    receipt = task.get_state()["pool_task"]["result_views"][0]
    name = receipt["descriptor"]["name"]
    solver.solution_pool.publish_subpool_view(name, original[1:],
        created_by=receipt["created_by"])
    current = solver.solution_pool.subpool_descriptor(name)
    assert current["view_id"] == receipt["descriptor"]["view_id"]
    assert current["revision"] == receipt["descriptor"]["revision"] + 1
    with pytest.raises(ValueError, match="identity or interpretation changed"):
        task.get_pool_task_results(solver)


def test_getter_checks_exact_members_against_the_result_receipt():
    solver, adapter, task = build()
    complete(solver)
    original = task.get_pool_task_results(solver)
    state = task.get_state()
    state["pool_task"]["result_views"][0]["refs"] = [original[1].as_dict()]
    task.set_state(state)
    with pytest.raises(ValueError, match="members changed"):
        task.get_pool_task_results(solver)


@pytest.mark.parametrize("output", [None, "history"])
def test_final_identity_receipts_survive_a_formal_checkpoint_without_re_evaluation(output):
    source, source_plan, task = build(output=output)
    complete(source)
    expected = task.get_pool_task_results(source)
    target, target_plan, restored_task = build(output=output, values=())
    writer, reader = CheckpointResumePlugin(), CheckpointResumePlugin()
    writer.cfg.strict = reader.cfg.strict = True
    writer.attach(source)
    reader.attach(target)
    reader._restore_payload(solver=target,
        payload=writer._build_payload(solver=source, reason="task-result-identity"))
    assert restored_task.get_pool_task_results(target) == expected
    assert restored_task.get_state()["pool_task"]["result_views"] == task.get_state()["pool_task"]["result_views"]
    assert not target.problem.calls
    assert target.evaluation_count == source.evaluation_count == 4


@pytest.mark.parametrize("kind", ["checkpoint", "step"])
@pytest.mark.parametrize("corruption", ["missing", "revision", "foreign-ref", "wrong-request"])
def test_restore_validates_result_receipts_before_mutating_the_owned_state(kind, corruption):
    solver, adapter, task = build()
    complete(solver)
    get = task.get_state if kind == "checkpoint" else task.snapshot_step_state
    restore = task.set_state if kind == "checkpoint" else task.restore_step_state
    before = get()
    state = copy.deepcopy(before)
    payload = state["pool_task"]
    if corruption == "missing":
        del payload["result_views"]
    elif corruption == "revision":
        payload["result_views"][0]["descriptor"]["revision"] = -1
    elif corruption == "foreign-ref":
        payload["result_views"][0]["refs"][0]["pool_id"] = "foreign"
    else:
        payload["result_views"][0]["descriptor"]["name"] += "/other-request"
    with pytest.raises((TypeError, ValueError)):
        restore(state)
    assert get() == before


def test_refinement_without_aggregate_history_delivers_only_final_selected_views():
    solver, adapter, task = build(output=None, repeat=2)
    complete(solver)
    first = task.get_pool_task_results(solver)
    assert len(first) == 2
    np.testing.assert_array_equal(solver.solution_pool.read(first).numeric_matrix, [[9.], [19.]])
    complete(solver)
    second = task.get_pool_task_results(solver)
    assert len(second) == 2 and set(first).isdisjoint(second)
    assert task.task_status["output"] is None
    assert len(solver.solution_pool.select()) == 8
    # Input-allocation markers may remain, but no ordinary history collection
    # retains all the accepted neighborhood trials.
    for name in solver.solution_pool.published_subpool_names():
        if solver.solution_pool.subpool_metadata(name)["kind"] == "candidate_collection":
            assert not solver.solution_pool.subpool_refs(name)
    assert len([name for name in solver.solution_pool.published_subpool_names()
                if solver.solution_pool.subpool_metadata(name)["kind"] == "candidate_view"]) == 4
    np.testing.assert_array_equal(solver.solution_pool.read(first).numeric_matrix, [[9.], [19.]])


def test_unconsumed_final_results_remain_readable_with_idle_collection_enabled():
    solver, adapter, task = build(output=None, tail=True, retention=True)
    complete(solver)
    expected = task.get_pool_task_results(solver)
    complete(solver, updates=3)
    assert task.get_pool_task_results(solver) == expected
    np.testing.assert_array_equal(solver.solution_pool.read(expected).numeric_matrix, [[9.], [19.]])


def test_consumed_results_can_be_released_without_reclaiming_other_consumers_or_units(monkeypatch):
    # Descending seeds leave the final VNS point as the Router's best too;
    # the first final point therefore has no unrelated best-so-far owner.
    solver, adapter, task = build(output=None, values=(30., 20., 10.),
        tail=True, retention=True)
    pool = solver.solution_pool
    pool.retain("test:initial-seeds", pool.select(stage="initial"))
    complete(solver, updates=6)
    # Reading is delivery, not an implicit release. The caller deliberately
    # drops the final views in the next normal accepted update.
    delivered = task.get_pool_task_results(solver)
    np.testing.assert_array_equal(pool.read(delivered).numeric_matrix, [[29.], [19.], [9.]])
    unowned, consumer_owned, unit_owned = delivered
    pool.retain("test:result-consumer", (consumer_owned,))
    assert task.inner.get_solution_pool_roots(solver) == (unit_owned,)
    result_names = tuple(receipt["descriptor"]["name"]
        for receipt in task.get_state()["pool_task"]["result_views"])
    tail = adapter.units[1].adapter
    original_update = tail.update
    released = []

    def consume_and_release(control, candidates, feedback, context):
        original_update(control, candidates, feedback, context)
        if not released:
            for name in result_names:
                pool.drop_subpool(name)
            pool.release("test:initial-seeds")
            released.append(True)

    monkeypatch.setattr(tail, "update", consume_and_release)
    # The same retention/publication path used by real accepted work retires
    # idle rows. No synthetic generation or standalone GC transaction is used.
    complete(solver, updates=3)
    assert released == [True]
    assert all(name not in pool.published_subpool_names() for name in result_names)
    assert unowned not in pool.select()
    with pytest.raises(ValueError, match="unavailable|retired"):
        pool.read((unowned,))
    np.testing.assert_array_equal(pool.read((consumer_owned, unit_owned)).numeric_matrix,
        [[19.], [9.]])
    assert task.inner.get_solution_pool_roots(solver) == (unit_owned,)
    # A detached identity receipt neither pins candidates nor resurrects a
    # dropped final view after its caller explicitly released that view.
    with pytest.raises(RuntimeError, match="unavailable"):
        task.get_pool_task_results(solver)


def test_staged_final_result_receipts_are_rolled_back_with_publication_failure(monkeypatch):
    solver, adapter, task = build(output=None)
    complete(solver, updates=3)
    before = task.get_state()["pool_task"]
    names = solver.solution_pool.published_subpool_names()
    original = adapter.update

    def fail_after_update(*args, **kwargs):
        original(*args, **kwargs)
        with pytest.raises(RuntimeError, match="commit"):
            task.get_pool_task_results(solver)
        raise RuntimeError("after final view staging")

    monkeypatch.setattr(adapter, "update", fail_after_update)
    with pytest.raises(RuntimeError, match="after final view staging"):
        solver.step()
    assert task.get_state()["pool_task"] == before
    assert solver.solution_pool.published_subpool_names() == names
    assert solver.evaluation_count == 4
    monkeypatch.setattr(adapter, "update", original)
    assert solver.step().committed
    assert len(task.get_pool_task_results(solver)) == 2


class EarlyTerminalVNS(VNSAdapter):
    def __init__(self, outcome="terminal"):
        super().__init__(name="early", batch_size=1, restart_on_stagnation=False)
        self.outcome = outcome

    def propose(self, control, context):
        return [] if self.current_score is not None else super().propose(control, context)

    def get_empty_proposal_outcome(self, control, context):
        if self.current_score is None:
            return None
        return StepOutcome(status="cancelled" if self.outcome == "cancelled" else "terminal",
            stop_requested=self.outcome == "stop", reason="early_local_end")


def test_inner_terminal_cannot_skip_remaining_seeds_or_finish_a_running_request():
    solver, adapter, task = build(local=EarlyTerminalVNS(), steps=5, repeat=2)
    assert solver.step().committed
    before = task.task_status
    active = adapter.cursor.active()
    with pytest.raises(RuntimeError, match="inner terminal before request completion is unsupported"):
        solver.step()
    assert task.task_status == before
    assert task.task_status["status"] == "running" and task.task_status["next"] == 0
    assert adapter.cursor.active() == active
    assert solver.problem.calls == [10.]
    assert solver.evaluation_count == 1
    with pytest.raises(RuntimeError, match="completion"):
        task.get_pool_task_results(solver)


@pytest.mark.parametrize("outcome", ["cancelled", "stop"])
def test_explicit_cancellation_or_stop_keeps_its_original_terminal_meaning(outcome):
    solver, adapter, task = build(local=EarlyTerminalVNS(outcome), steps=5)
    assert solver.step().committed
    result = solver.step()
    assert result.terminal and result.stop_requested
    assert not result.committed
    assert task.task_status["status"] == "running"
    assert not adapter.cursor.completed
    assert solver.problem.calls == [10.]
