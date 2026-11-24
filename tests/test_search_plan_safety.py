"""Real Solver attempts preserve local plan quotas and rollback boundaries."""
from __future__ import annotations

import copy

import numpy as np
import pytest

from blackbase.contracts import BatchDisposition
from blackbase.orchestration import ExecutionPlan
from nsgablack.adapters import AlgorithmAdapter, MultiStrategyConfig, StrategySpec
from nsgablack.adapters.search_plan import SearchPlanAdapter
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.core.control_plane import BudgetController
from nsgablack.core.state import StepOutcome
from nsgablack.plugins import CheckpointResumePlugin


class CountingProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, objectives=["min"], bounds=[(-100., 100.)])
        self.calls = []

    def evaluate(self, candidate):
        self.calls.append(float(candidate[0]))
        return [float(candidate[0] ** 2)]


class ProbeAdapter(AlgorithmAdapter):
    state_recovery_level = "L1"
    state_recovery_notes = "Exact counters and last accepted values."

    def __init__(self, name, value, *, batch=1, empty=None):
        super().__init__(name=name)
        self.value, self.batch, self.empty = value, batch, empty
        self.proposals = self.updates = 0
        self.last_values = []
        self.last_phase = None
        self.fail_update = False

    def propose(self, control, context):
        self.proposals += 1
        self.last_phase = context.get("phase")
        if self.empty is not None:
            return []
        return [np.array([self.value + index], dtype=float) for index in range(self.batch)]

    def update(self, control, candidates, feedback, context):
        self.updates += 1
        self.last_values = [float(item[0]) for item in candidates]
        assert context.get("phase") == self.last_phase
        if self.fail_update:
            raise RuntimeError("probe child update failed")

    def get_empty_proposal_outcome(self, control, context):
        if self.empty == "complete":
            return StepOutcome(status="terminal", reason="goal_reached",
                               metadata={"completion": "success"})
        if self.empty == "cancel":
            return StepOutcome(status="cancelled", reason="cancel_probe")
        return StepOutcome(status="idle", reason="input_not_ready")

    def get_state(self):
        return {"proposals": self.proposals, "updates": self.updates,
                "last_values": list(self.last_values), "last_phase": self.last_phase}

    def set_state(self, state):
        self.proposals, self.updates = state["proposals"], state["updates"]
        self.last_values, self.last_phase = list(state["last_values"]), state["last_phase"]


def build(plan, *children, total=None, until=None, metrics=None):
    adapter = SearchPlanAdapter(plan,
        strategies=[StrategySpec(child, child.name) for child in children],
        config=MultiStrategyConfig(total_batch_size=total or max(1, sum(c.batch for c in children)),
                                   adapt_weights=False),
        until=until, metrics=metrics)
    solver = ComposableSolver(CountingProblem(), adapter=adapter)
    solver.set_random_seed(183)
    solver.setup()
    return solver, adapter


def active_counts(adapter):
    return {row.name: row.count for row in adapter.cursor.active()}


def mean_objective(feedback):
    return float(np.mean(feedback.objectives[:, 0]))


def after_two_updates(progress):
    return progress.updates >= 2


def another_condition(progress):
    return progress.updates >= 3


def nonfinite_metric(feedback):
    return float("nan")


def test_nonprefix_admission_advances_only_the_child_that_actually_received_feedback():
    a, b = ProbeAdapter("a", 10., batch=2), ProbeAdapter("b", 20., batch=2)
    solver, adapter = build(ExecutionPlan.multi(
        ExecutionPlan.leaf("a", 1), ExecutionPlan.leaf("b", 2)), a, b,
        metrics={"a": mean_objective, "b": mean_objective})

    class LastOnly:
        policy_id = "search-plan-last-only"

        def select(self, candidates, feedback, context):
            return BatchDisposition(len(candidates.semantic_states), (3,))

    solver.set_evaluation_acceptance_policy(LastOnly())
    assert solver.step().committed
    assert active_counts(adapter) == {"a": 0, "b": 1}
    assert a.updates == 0 and b.updates == 1
    assert b.last_values == [21.]
    assert list(adapter._observations.values())[0]["last"] == 441.
    assert solver.evaluation_count == 4
    solver.set_evaluation_acceptance_policy(None)
    assert solver.step().committed
    assert adapter.cursor.completed
    assert (a.updates, b.updates) == (1, 2)


def test_budget_truncation_never_gives_unprocessed_sibling_a_local_step():
    a, b = ProbeAdapter("a", 10., batch=2), ProbeAdapter("b", 20., batch=2)
    solver, adapter = build(ExecutionPlan.multi(
        ExecutionPlan.leaf("a", 2), ExecutionPlan.leaf("b", 2)), a, b)
    solver.register_controller(BudgetController(max_evaluations=1))
    assert solver.step().committed
    assert active_counts(adapter) == {"a": 1, "b": 0}
    assert (a.updates, b.updates) == (1, 0)
    assert a.last_values == [10.]
    assert solver.evaluation_count == 1


def test_late_child_failure_rolls_back_sibling_and_plan_but_retains_real_evaluation():
    a, b = ProbeAdapter("a", 10.), ProbeAdapter("b", 20.)
    solver, adapter = build(ExecutionPlan.multi(
        ExecutionPlan.leaf("a", 1), ExecutionPlan.leaf("b", 1)), a, b)
    baseline = copy.deepcopy(adapter.get_state())
    before_refs = solver.solution_pool.select()
    b.fail_update = True
    with pytest.raises(RuntimeError, match="probe child update failed"):
        solver.step()
    assert adapter.get_state() == baseline
    assert (a.updates, b.updates, a.proposals, b.proposals) == (0, 0, 0, 0)
    assert solver.solution_pool.select() == before_refs
    assert solver.evaluation_count == 2
    assert solver.problem.calls == [10., 20.]
    assert solver.generation == 0
    b.fail_update = False
    assert solver.step().committed
    assert adapter.cursor.completed
    assert solver.evaluation_count == 4


def test_child_goal_completes_its_serial_stage_and_dispatches_next_without_stopping_root():
    done, work = ProbeAdapter("done", 1., empty="complete"), ProbeAdapter("work", 2.)
    solver, adapter = build(ExecutionPlan.serial(
        ExecutionPlan.leaf("done"), ExecutionPlan.leaf("work", 1, label="continue")),
        done, work)
    assert solver.step().committed
    assert adapter.cursor.completed
    assert (done.proposals, done.updates, work.updates) == (1, 0, 1)
    assert work.last_phase == "continue"
    assert not solver.stop_requested
    assert solver.evaluation_count == 1


def test_finished_multi_branch_is_not_reopened_while_sibling_keeps_working():
    done, work = ProbeAdapter("done", 1., empty="complete"), ProbeAdapter("work", 2.)
    solver, adapter = build(ExecutionPlan.multi(
        ExecutionPlan.leaf("done"), ExecutionPlan.leaf("work", 2)), done, work)
    assert solver.step().committed
    assert active_counts(adapter) == {"work": 1}
    assert solver.step().committed
    assert adapter.cursor.completed
    assert done.proposals == 1 and work.updates == 2


def test_child_cancel_is_global_and_never_evaluates_already_proposed_sibling():
    work, cancel = ProbeAdapter("work", 2.), ProbeAdapter("cancel", 1., empty="cancel")
    solver, adapter = build(ExecutionPlan.multi(
        ExecutionPlan.leaf("work", 1), ExecutionPlan.leaf("cancel")), work, cancel)
    outcome = solver.step()
    assert outcome.status == "cancelled" and outcome.stop_requested
    assert outcome.reason == "cancel_probe"
    assert active_counts(adapter) == {"work": 0, "cancel": 0}
    assert solver.evaluation_count == 0 and not solver.problem.calls
    assert work.updates == 0


def test_waiting_attempts_do_not_create_generations_or_pool_publications():
    wait = ProbeAdapter("wait", 1., empty="wait")
    solver, adapter = build(ExecutionPlan.leaf("wait", 2), wait)
    result = solver.run(max_steps=2, max_step_attempts=2)
    assert result["steps_executed"] == 0
    assert result["step_attempts_executed"] == 2
    assert result["termination_reason"] == "attempt_limit"
    assert solver.generation == 0 and solver.evaluation_count == 0
    assert active_counts(adapter) == {"wait": 0}
    assert not solver.solution_pool.select()
    assert not solver.solution_pool.published_subpool_names()


@pytest.mark.parametrize("plan", [
    ExecutionPlan.serial(),
    ExecutionPlan.leaf("unused", 0),
    ExecutionPlan.repeat(ExecutionPlan.leaf("unused", 1), 0),
])
def test_zero_work_plan_finishes_without_a_fake_logical_step(plan):
    children = [ProbeAdapter("unused", 1.)] if "unused" in plan.owner_names else []
    solver, adapter = build(plan, *children)
    outcome = solver.step()
    assert outcome.status == "terminal" and not outcome.committed
    assert adapter.cursor.completed
    assert solver.evaluation_count == solver.generation == 0
    assert all(child.proposals == 0 for child in children)


def test_formal_checkpoint_keeps_local_progress_and_does_not_replay_completed_stage():
    plan = ExecutionPlan.serial(
        ExecutionPlan.leaf("done"), ExecutionPlan.leaf("work", label="condition"))
    source, source_plan = build(plan, ProbeAdapter("done", 1., empty="complete"),
        ProbeAdapter("work", 2.), until={"condition": after_two_updates},
        metrics={"condition": mean_objective})
    assert source.step().committed
    original = source_plan.cursor.active()[0]
    target_done, target_work = ProbeAdapter("done", 1., empty="complete"), ProbeAdapter("work", 2.)
    target, target_plan = build(plan, target_done, target_work,
        until={"condition": after_two_updates}, metrics={"condition": mean_objective})
    writer, reader = CheckpointResumePlugin(), CheckpointResumePlugin()
    writer.cfg.strict = reader.cfg.strict = True
    writer.attach(source)
    reader.attach(target)
    reader._restore_payload(solver=target,
        payload=writer._build_payload(solver=source, reason="search-plan-safety"))
    assert target_plan.cursor.active()[0] == original
    assert not target.problem.calls
    assert target_done.proposals == 1 and target_work.updates == 1
    assert target.step().committed
    assert target_work.updates == 2
    completed = target.step()
    assert completed.status == "terminal" and not completed.committed
    assert target_plan.cursor.completed
    assert target_done.proposals == 1
    assert target.problem.calls == [2.]


@pytest.mark.parametrize("corruption", ["identity", "count", "future", "proposal_unit"])
def test_checkpoint_plan_identity_and_cursor_corruption_fail_before_child_restore(corruption):
    child = ProbeAdapter("work", 2.)
    solver, adapter = build(ExecutionPlan.serial(
        ExecutionPlan.leaf("work", 2, label="first"),
        ExecutionPlan.leaf("work", 1, label="later")), child)
    assert solver.step().committed
    state = copy.deepcopy(adapter.get_state())
    if corruption == "identity":
        state["search_plan"]["identity"]["plan"] = "wrong-plan"
    elif corruption == "count":
        state["search_plan"]["cursor"]["state"]["children"][0]["count"] = 3
    elif corruption == "future":
        state["search_plan"]["cursor"]["state"]["children"][1]["count"] = 1
    else:
        state["search_plan"]["proposals"] = [{"role": "work", "unit_id": 999,
            "activation_id": adapter.cursor.active()[0].activation_id}]
    before = child.get_state()
    with pytest.raises(ValueError):
        adapter.set_state(state)
    assert child.get_state() == before


def test_changed_condition_binding_is_not_silently_accepted_by_restore():
    plan = ExecutionPlan.leaf("work", label="condition")
    source, source_plan = build(plan, ProbeAdapter("work", 2.),
                              until={"condition": after_two_updates})
    target, target_plan = build(plan, ProbeAdapter("work", 2.),
                              until={"condition": another_condition})
    with pytest.raises(ValueError, match="identity"):
        target_plan.set_state(source_plan.get_state())
    assert not target.problem.calls


def test_nested_plan_completion_is_local_to_its_outer_stage():
    leaf = ProbeAdapter("leaf", 1., empty="complete")
    inner = SearchPlanAdapter(ExecutionPlan.leaf("leaf"),
        strategies=[StrategySpec(leaf, "leaf")], name="inner")
    work = ProbeAdapter("work", 2.)
    outer = SearchPlanAdapter(ExecutionPlan.serial(
        ExecutionPlan.leaf("inner"), ExecutionPlan.leaf("work", 1)),
        strategies=[StrategySpec(inner, "inner"), StrategySpec(work, "work")],
        config=MultiStrategyConfig(total_batch_size=2, adapt_weights=False))
    solver = ComposableSolver(CountingProblem(), adapter=outer)
    solver.setup()
    assert solver.step().committed
    assert outer.cursor.completed and inner.cursor.completed
    assert not solver.stop_requested
    assert solver.evaluation_count == 1 and work.updates == 1


def test_failure_after_inline_control_advance_restores_the_old_active_stage():
    done, work = ProbeAdapter("done", 1., empty="complete"), ProbeAdapter("work", 2.)
    solver, adapter = build(ExecutionPlan.serial(
        ExecutionPlan.leaf("done"), ExecutionPlan.leaf("work", 1)), done, work)
    baseline = copy.deepcopy(adapter.get_state())
    work.fail_update = True
    with pytest.raises(RuntimeError, match="probe child update failed"):
        solver.step()
    assert adapter.get_state() == baseline
    assert active_counts(adapter) == {"done": 0}
    assert done.proposals == work.proposals == 0
    assert solver.problem.calls == [2.]
    assert solver.evaluation_count == 1


def test_invalid_metric_rolls_back_already_updated_children_and_local_progress():
    child = ProbeAdapter("work", 2.)
    solver, adapter = build(ExecutionPlan.leaf("work", 2), child,
                            metrics={"work": nonfinite_metric})
    baseline = copy.deepcopy(adapter.get_state())
    with pytest.raises(ValueError, match="metric must be finite"):
        solver.step()
    assert adapter.get_state() == baseline
    assert child.updates == child.proposals == 0
    assert solver.evaluation_count == 1
    assert not solver.solution_pool.select()


def test_formal_checkpoint_can_preserve_control_only_advance_before_any_evaluation():
    plan = ExecutionPlan.serial(
        ExecutionPlan.leaf("done"), ExecutionPlan.leaf("wait", 1))
    source, source_plan = build(plan, ProbeAdapter("done", 1., empty="complete"),
                              ProbeAdapter("wait", 2., empty="wait"))
    assert source.step().status == "idle"
    assert active_counts(source_plan) == {"wait": 0}
    assert source.evaluation_count == source.generation == 0
    target_done, target_wait = ProbeAdapter("done", 1., empty="complete"), ProbeAdapter("wait", 2., empty="wait")
    target, target_plan = build(plan, target_done, target_wait)
    writer, reader = CheckpointResumePlugin(), CheckpointResumePlugin()
    writer.cfg.strict = reader.cfg.strict = True
    writer.attach(source)
    reader.attach(target)
    reader._restore_payload(solver=target,
        payload=writer._build_payload(solver=source, reason="control-only-plan-progress"))
    assert active_counts(target_plan) == {"wait": 0}
    assert target_done.proposals == 1 and target_wait.proposals == 1
    assert target.evaluation_count == 0 and not target.problem.calls
    target_wait.empty = None
    assert target.step().committed
    assert target_plan.cursor.completed
    assert target_done.proposals == 1
    assert target.problem.calls == [2.]


def test_router_restore_rejection_does_not_apply_an_otherwise_valid_plan_cursor():
    plan = ExecutionPlan.leaf("work", 2)
    source, source_plan = build(plan, ProbeAdapter("work", 2.))
    target, target_plan = build(plan, ProbeAdapter("work", 2.))
    assert source.step().committed
    state = copy.deepcopy(source_plan.get_state())
    state["working_pool"] = "different-assembly-binding"
    original = target_plan.cursor.get_state()
    with pytest.raises(ValueError):
        target_plan.set_state(state)
    assert target_plan.cursor.get_state() == original
