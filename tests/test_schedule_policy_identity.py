"""A restored local schedule must keep its declared completion policy."""
import pytest

from nsgablack.adapters import SerialPhaseSpec, SerialStrategyConfig, StrategyChainAdapter
from nsgablack.adapters.search_plan import SearchPlanAdapter, stage
from nsgablack.adapters.multi_strategy import StrategySpec
from tests.test_schedule_activation import TrackedProbe, solver_for


def threshold(limit):
    def reached(progress):
        return progress.updates >= limit
    return reached


def advance_after(limit):
    def advance(context):
        return context.get("generation", 0) >= limit
    return advance


def chain(*, repeat_last=False, steps=1, limit=3):
    return StrategyChainAdapter([
        SerialPhaseSpec("a", TrackedProbe("a", 2.), steps=steps,
                        advance_when=advance_after(limit)),
        SerialPhaseSpec("b", TrackedProbe("b", 3.), steps=2),
    ], config=SerialStrategyConfig(repeat_last=repeat_last))


@pytest.mark.parametrize("kind", ["checkpoint", "transaction"])
@pytest.mark.parametrize("change", [dict(repeat_last=True), dict(steps=2), dict(limit=4)])
def test_chain_rejects_changed_completion_policy_before_applying_state(kind, change):
    source, target = chain(), chain(**change)
    solver_for(source)
    solver_for(target)
    state = source.get_state() if kind == "checkpoint" else source.snapshot_step_state()
    state["current_idx"] = 1
    restore = target.set_state if kind == "checkpoint" else target.restore_step_state
    with pytest.raises(ValueError, match="configuration mismatch"):
        restore(state)
    assert target._current_idx == 0


def test_plan_condition_pure_closure_parameters_are_part_of_restore_identity():
    def build(limit):
        plan = SearchPlanAdapter(stage("work"), [StrategySpec(TrackedProbe("work", 2.), "work")],
                                 until={"work": threshold(limit)})
        return solver_for(plan), plan
    source_solver, source = build(1)
    _, target = build(2)
    assert source_solver.step().committed
    with pytest.raises(ValueError, match="identity mismatch"):
        target.set_state(source.get_state())
    assert not target._observations


@pytest.mark.parametrize("kind", ["checkpoint", "transaction"])
def test_chain_quota_payload_cannot_override_the_declared_policy(kind):
    schedule = chain()
    solver_for(schedule)
    state = schedule.get_state() if kind == "checkpoint" else schedule.snapshot_step_state()
    state["phase_steps"][0] += 1
    state["current_idx"] = 1
    restore = schedule.set_state if kind == "checkpoint" else schedule.restore_step_state
    with pytest.raises(ValueError, match="schedule mismatch"):
        restore(state)
    assert schedule._current_idx == 0
