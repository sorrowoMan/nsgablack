"""Nested schedules reopen control state while retaining algorithm ownership."""
from __future__ import annotations

import copy

import pytest

from blackbase.orchestration import ExecutionPlan
from nsgablack.adapters import (
    CompositeAdapter, MultiStrategyConfig, NSGA2Adapter, PoolTaskSpec, RoleAdapter, RoleRouterAdapter,
    SerialPhaseSpec, SerialStrategyConfig, StrategyChainAdapter,
    StrategyRouterAdapter, StrategySpec, VNSAdapter,
)
from nsgablack.adapters.search_plan import SearchPlanAdapter
from nsgablack.adapters.empty_outcome import (
    _decode_dispatch_stop_outcome, _encode_dispatch_stop_outcome,
)
from nsgablack.core import ComposableSolver
from nsgablack.core.state import StepOutcome
from nsgablack.plugins import CheckpointResumePlugin
from nsgablack.representation import RepresentationPipeline

from tests.test_search_plan_pool_tasks import (
    Descend, Sphere, add_seeds, initial_refs, task_wrappers,
)
from tests.test_search_plan_safety import ProbeAdapter


class TrackedGA(NSGA2Adapter):
    def __init__(self, name="ga"):
        self.setup_calls = self.teardown_calls = 0
        super().__init__(name=name, population_size=4, offspring_size=1)

    def setup(self, control):
        self.setup_calls += 1
        super().setup(control)

    def teardown(self, control):
        self.teardown_calls += 1
        super().teardown(control)


class TrackedVNS(VNSAdapter):
    def __init__(self, name="local"):
        self.setup_calls = self.teardown_calls = 0
        super().__init__(name=name, batch_size=1, restart_on_stagnation=False)

    def setup(self, control):
        self.setup_calls += 1
        super().setup(control)

    def teardown(self, control):
        self.teardown_calls += 1
        super().teardown(control)


class TrackedProbe(ProbeAdapter):
    def __init__(self, name, value, *, empty=None):
        super().__init__(name, value, empty=empty)
        self.setup_calls = self.teardown_calls = 0
        self.live = False
        self.activations, self.dispositions = [], []

    def setup(self, control):
        self.setup_calls += 1
        self.live = True

    def teardown(self, control):
        self.teardown_calls += 1
        self.live = False

    def on_schedule_activation(self, control, activation_id):
        self.activations.append(activation_id)

    def propose(self, control, context):
        assert self.live, "a retired algorithm cannot be reused by reopening a schedule"
        return super().propose(control, context)

    def on_proposal_disposition(self, control, disposition, context):
        self.dispositions.append(disposition)


def solver_for(adapter, *, seeds=()):
    operator = Descend()
    solver = ComposableSolver(Sphere(), adapter=adapter,
        representation_pipeline=RepresentationPipeline(initializer=operator, mutator=operator))
    solver.set_random_seed(731)
    solver.setup()
    if seeds:
        add_seeds(solver, seeds)
    return solver


def local_plan(*, name="inner", local=None):
    local = local or TrackedVNS()
    adapter = SearchPlanAdapter(ExecutionPlan.leaf("local"), strategies=[
        StrategySpec(local, "local", pool_task=PoolTaskSpec(initial_refs,
            mode="refine", steps=2, count=1, shuffle=False, output="trials")),
    ], config=MultiStrategyConfig(total_batch_size=1, adapt_weights=False), name=name)
    return adapter, local


def repeated_inner(inner, *, steps=None):
    return SearchPlanAdapter(
        ExecutionPlan.repeat(ExecutionPlan.leaf("inner", steps=steps), count=2),
        strategies=[StrategySpec(inner, "inner")],
        config=MultiStrategyConfig(total_batch_size=4, adapt_weights=False), name="outer")


def restore_into(source, target):
    writer, reader = CheckpointResumePlugin(), CheckpointResumePlugin()
    writer.cfg.strict = reader.cfg.strict = True
    writer.attach(source)
    reader.attach(target)
    reader._restore_payload(solver=target,
        payload=writer._build_payload(solver=source, reason="nested-schedule-activation"))


def test_repeated_child_plan_reopens_cursor_without_reinitializing_ga_or_its_unit():
    ga = TrackedGA()
    inner = SearchPlanAdapter(ExecutionPlan.leaf("ga", steps=1),
        strategies=[StrategySpec(ga, "ga", pool_task=PoolTaskSpec(initial_refs,
            mode="initialize", count=4, shuffle=False))],
        config=MultiStrategyConfig(total_batch_size=4, adapt_weights=False), name="inner")
    outer = repeated_inner(inner)
    solver = solver_for(outer, seeds=(10., 20., 30., 40.))
    assert solver.step().committed
    unit = ga.algorithm_unit
    assert unit is not None
    assert solver.evaluation_count == 4
    assert solver.step().committed
    assert ga.algorithm_unit is unit
    assert ga.setup_calls == 1 and ga.teardown_calls == 0
    assert solver.evaluation_count == 5
    assert inner.cursor.completed
    assert solver.step().status == "terminal"
    assert outer.cursor.completed
    outer.teardown(solver)
    assert ga.teardown_calls == 1


def test_new_parent_activation_gives_child_pool_tasks_a_new_request_identity():
    inner, local = local_plan()
    outer = repeated_inner(inner)
    solver = solver_for(outer, seeds=(10.,))
    task = task_wrappers(inner)["local"]
    assert solver.step().committed
    first_request = task.task_status["request"]
    geometry = local.neighborhood_unit
    assert solver.step().committed
    assert task.task_status["status"] == "done"
    assert solver.step().committed
    assert task.task_status["request"] != first_request
    assert local.neighborhood_unit is geometry
    assert solver.step().committed
    assert task.task_status["status"] == "done"
    assert solver.problem.calls == [10., 9., 10., 9.]
    assert solver.problem.selections == 2
    assert local.setup_calls == 1 and local.teardown_calls == 0


def test_paused_incomplete_child_resumes_same_frozen_request_instead_of_restarting():
    inner, local = local_plan()
    outer = repeated_inner(inner, steps=1)
    solver = solver_for(outer, seeds=(10.,))
    task = task_wrappers(inner)["local"]
    assert solver.step().committed
    request = task.task_status["request"]
    assert task.task_status["steps"] == 1
    assert not inner.cursor.completed
    assert solver.step().committed
    assert task.task_status["request"] == request
    assert task.task_status["status"] == "done"
    assert inner.cursor.completed and outer.cursor.completed
    assert solver.problem.calls == [10., 9.]
    assert solver.problem.selections == 1
    assert local.setup_calls == 1


def test_child_plan_normal_completion_advances_an_old_chain_to_its_next_phase():
    work, after = TrackedProbe("work", 2.), TrackedProbe("after", 3.)
    inner = SearchPlanAdapter(ExecutionPlan.leaf("work", steps=1),
        strategies=[StrategySpec(work, "work")], name="inner")
    chain = StrategyChainAdapter(phases=[
        SerialPhaseSpec("nested", inner, steps=-1),
        SerialPhaseSpec("after", after, steps=1),
    ], config=SerialStrategyConfig(repeat_last=False))
    solver = solver_for(chain)
    assert solver.step().committed
    assert solver.step().committed
    assert work.updates == after.updates == 1
    assert solver.problem.calls == [2., 3.]
    assert not solver.stop_requested


def test_chain_repeated_by_plan_reopens_only_schedule_and_retires_children_once_at_end():
    a, b = TrackedProbe("a", 2.), TrackedProbe("b", 3.)
    chain = StrategyChainAdapter(phases=[
        SerialPhaseSpec("first", a, steps=1),
        SerialPhaseSpec("second", b, steps=1),
    ], config=SerialStrategyConfig(repeat_last=False), name="chain")
    outer = SearchPlanAdapter(
        ExecutionPlan.repeat(ExecutionPlan.leaf("chain", steps=2), count=2),
        strategies=[StrategySpec(chain, "chain")], name="outer")
    solver = solver_for(outer)
    for _ in range(4):
        assert solver.step().committed
        assert a.setup_calls == b.setup_calls == 1
        assert a.teardown_calls == b.teardown_calls == 0
    assert solver.problem.calls == [2., 3., 2., 3.]
    assert a.updates == b.updates == 2 and outer.cursor.completed
    outer.teardown(solver)
    assert a.teardown_calls == b.teardown_calls == 1


def test_old_router_observes_nested_cancel_and_rejects_already_proposed_sibling():
    work, cancel = TrackedProbe("work", 2.), TrackedProbe("cancel", 3., empty="cancel")
    inner = SearchPlanAdapter(ExecutionPlan.leaf("cancel"),
        strategies=[StrategySpec(cancel, "cancel")], name="inner")
    router = StrategyRouterAdapter(strategies=[
        StrategySpec(work, "work"), StrategySpec(inner, "nested"),
    ], config=MultiStrategyConfig(total_batch_size=2, adapt_weights=False))
    solver = solver_for(router)
    outcome = solver.step()
    assert outcome.status == "cancelled"
    assert outcome.stop_requested and outcome.reason == "cancel_probe"
    assert work.proposals == 1 and work.updates == 0
    assert len(work.dispositions) == 1 and work.dispositions[0].accepted_count == 0
    assert not solver.problem.calls and solver.evaluation_count == 0
    assert solver.generation == 0


def cancel_after_intake(*, cancel=True):
    local = TrackedVNS()
    stopper = TrackedProbe("stopper", 3., empty="cancel" if cancel else "wait")
    adapter = SearchPlanAdapter(ExecutionPlan.multi(
        ExecutionPlan.leaf("local"), ExecutionPlan.leaf("stopper")), strategies=[
        StrategySpec(local, "local", pool_task=PoolTaskSpec(initial_refs,
            mode="refine", steps=2, count=1, shuffle=False, output="trials")),
        StrategySpec(stopper, "stopper"),
    ], config=MultiStrategyConfig(total_batch_size=2, adapt_weights=False))
    return adapter, local, stopper


def test_cancel_after_pool_seed_intake_can_checkpoint_and_resume_without_cursor_mismatch():
    source_plan, source_local, _ = cancel_after_intake()
    source = solver_for(source_plan, seeds=(10.,))
    task = task_wrappers(source_plan)["local"]
    assert source.step().status == "cancelled"
    before = task.task_status
    assert before["status"] == "running" and before["steps"] == 0
    assert source.evaluation_count == 0 and not source.problem.calls
    input_key = task.get_state()["pool_task"]["input"]
    assert source.solution_pool.input_remaining(input_key) == 1
    assert source_local.current_x is None
    target_plan, target_local, _ = cancel_after_intake(cancel=False)
    target = solver_for(target_plan)
    restore_into(source, target)
    restored_task = task_wrappers(target_plan)["local"]
    assert restored_task.task_status == before
    assert target.step().committed
    assert target_local.current_score == 100.
    assert target.step().committed
    assert restored_task.task_status["status"] == "done"
    assert restored_task.task_status["request"] == before["request"]
    assert target.problem.calls == [10., 9.]
    assert target.problem.selections == 0


def test_role_adapter_forwards_activation_without_replaying_setup():
    child = TrackedProbe("work", 2.)
    role = RoleAdapter("wrapped", child)
    solver = solver_for(role)
    role.on_schedule_activation(solver, "parent:one")
    role.on_schedule_activation(solver, "parent:two")
    assert child.activations == ["parent:one", "parent:two"]
    assert child.setup_calls == 1 and child.teardown_calls == 0


def test_old_router_forwards_a_new_parent_activation_to_its_completed_child_plan():
    work = TrackedProbe("work", 2.)
    inner = SearchPlanAdapter(ExecutionPlan.leaf("work", steps=1),
        strategies=[StrategySpec(work, "work")], name="inner")
    bridge = StrategyRouterAdapter(strategies=[StrategySpec(inner, "inner")],
        config=MultiStrategyConfig(total_batch_size=1, adapt_weights=False), name="bridge")
    outer = SearchPlanAdapter(
        ExecutionPlan.repeat(ExecutionPlan.leaf("bridge", steps=1), count=2),
        strategies=[StrategySpec(bridge, "bridge")],
        config=MultiStrategyConfig(total_batch_size=1, adapt_weights=False), name="outer")
    solver = solver_for(outer)
    assert solver.step().committed
    assert solver.step().committed
    assert outer.cursor.completed and inner.cursor.completed
    assert work.updates == 2 and solver.problem.calls == [2., 2.]
    assert work.setup_calls == 1 and work.teardown_calls == 0


def test_checkpoint_mid_second_parent_activation_keeps_that_requests_frozen_scope():
    source_inner, source_local = local_plan()
    source_outer = repeated_inner(source_inner)
    source = solver_for(source_outer, seeds=(10.,))
    for _ in range(3):
        assert source.step().committed
    source_task = task_wrappers(source_inner)["local"]
    request = source_task.task_status["request"]
    assert source_task.task_status["steps"] == 1
    target_inner, target_local = local_plan()
    target_outer = repeated_inner(target_inner)
    target = solver_for(target_outer)
    restore_into(source, target)
    target_task = task_wrappers(target_inner)["local"]
    assert target_task.task_status["request"] == request
    assert target.step().committed
    assert target_task.task_status["request"] == request
    assert target_task.task_status["status"] == "done"
    assert target.problem.calls == [9.]
    assert target.problem.selections == 0
    assert source_local.setup_calls == target_local.setup_calls == 1


def test_failed_update_after_child_reactivation_restores_its_old_completed_scope():
    work = TrackedProbe("work", 2.)
    inner = SearchPlanAdapter(ExecutionPlan.leaf("work", steps=1),
        strategies=[StrategySpec(work, "work")], name="inner")
    outer = repeated_inner(inner)
    solver = solver_for(outer)
    assert solver.step().committed
    baseline = copy.deepcopy(outer.get_state())
    work.fail_update = True
    with pytest.raises(RuntimeError, match="probe child update failed"):
        solver.step()
    assert outer.get_state() == baseline
    assert inner.cursor.completed and work.updates == 1
    assert solver.evaluation_count == 2
    work.fail_update = False
    assert solver.step().committed
    assert inner.cursor.completed and work.updates == 2
    assert work.setup_calls == 1


def grouped(kind, children):
    if kind == "composite":
        return CompositeAdapter(children, name="bridge")
    return RoleRouterAdapter([RoleAdapter(f"r{index}", child)
        for index, child in enumerate(children)], name="bridge")


@pytest.mark.parametrize("kind", ["composite", "roles"])
def test_other_existing_composites_forward_parent_activation_to_completed_plans(kind):
    work = TrackedProbe("work", 2.)
    inner = SearchPlanAdapter(ExecutionPlan.leaf("work", steps=1),
        strategies=[StrategySpec(work, "work")], name="inner")
    bridge = grouped(kind, [inner])
    outer = SearchPlanAdapter(
        ExecutionPlan.repeat(ExecutionPlan.leaf("bridge", steps=1), count=2),
        strategies=[StrategySpec(bridge, "bridge")],
        config=MultiStrategyConfig(total_batch_size=1, adapt_weights=False), name="outer")
    solver = solver_for(outer)
    assert solver.step().committed
    assert solver.step().committed
    assert outer.cursor.completed and inner.cursor.completed
    assert work.updates == 2 and solver.problem.calls == [2., 2.]
    assert work.setup_calls == 1 and work.teardown_calls == 0


@pytest.mark.parametrize("kind", ["composite", "roles"])
def test_other_composites_cancel_and_rewind_nested_pool_intake_before_checkpoint(kind):
    source_inner, source_local = local_plan()
    stopper = TrackedProbe("stopper", 3., empty="cancel")
    source_group = grouped(kind, [source_inner, stopper])
    source = solver_for(source_group, seeds=(10.,))
    assert source.step().status == "cancelled"
    source_task = task_wrappers(source_inner)["local"]
    request = source_task.task_status["request"]
    assert source_task.task_status["steps"] == 0
    assert source_local.current_x is None
    assert source.evaluation_count == 0 and not source.problem.calls
    target_inner, target_local = local_plan()
    target_group = grouped(kind, [target_inner, TrackedProbe("stopper", 3., empty="wait")])
    target = solver_for(target_group)
    restore_into(source, target)
    restored_stop = target_group.get_empty_proposal_outcome(target, {})
    assert restored_stop.status == "cancelled" and restored_stop.reason == "cancel_probe"
    assert target.step().committed
    assert target.step().committed
    target_task = task_wrappers(target_inner)["local"]
    assert target_task.task_status["status"] == "done"
    assert target_task.task_status["request"] == request
    assert target_local.current_score == 81.
    assert target.problem.calls == [10., 9.]
    assert target.problem.selections == 0


@pytest.mark.parametrize("payload", [
    StepOutcome(status="cancelled").as_dict(),
    {"status": "cancelled"},
    {"status": "terminal", "evaluations": 0, "proposals": 0,
     "stop_requested": False, "reason": "local_complete", "metadata": {}},
    {"status": "committed", "evaluations": 0, "proposals": 0,
     "stop_requested": True, "reason": "not_an_empty_stop", "metadata": {}},
])
def test_dispatch_stop_restore_requires_exact_dataclass_fields_and_global_stop(payload):
    with pytest.raises(ValueError):
        _decode_dispatch_stop_outcome(payload)


def test_dispatch_stop_codec_preserves_cancel_reason_and_wire_metadata():
    outcome = StepOutcome(status="cancelled", reason="cancel_scope",
                          metadata={"owner": "nested", "path": ["a", "b"]})
    assert _decode_dispatch_stop_outcome(_encode_dispatch_stop_outcome(outcome)) == outcome
