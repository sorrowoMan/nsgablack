"""Structured schedules exercise the normal Solver evaluation/commit route."""
from __future__ import annotations

import copy
import numpy as np
import pytest

from nsgablack.adapters import (
    AlgorithmAdapter, SearchPlanAdapter, StrategySpec, MultiStrategyConfig,
    stage, serial, multi, repeat,
)
from nsgablack.core import ComposableSolver
from nsgablack.core.state import StepOutcome
from tests.test_composite_working_pool import CountedSphere


class Counter(AlgorithmAdapter):
    def __init__(self, name, *, terminal_at=None, wait=False):
        super().__init__(name=name)
        self.updates = 0
        self.setups = 0
        self.ends = 0
        self.phases = []
        self.terminal_at = terminal_at
        self.wait = wait

    def setup(self, control):
        self.setups += 1
        self.updates = 0
        self.phases = []

    def teardown(self, control):
        self.ends += 1

    def propose(self, control, context):
        if self.wait or self.terminal_at is not None and self.updates >= self.terminal_at:
            return []
        return [np.array([1.])]

    def get_empty_proposal_outcome(self, control, context):
        if self.terminal_at is not None and self.updates >= self.terminal_at:
            return StepOutcome(status="terminal", reason="goal_reached",
                               metadata={"completion": "success"})
        return None

    def update(self, control, candidates, feedback, context):
        self.updates += 1
        self.phases.append(context["phase"])

    def get_state(self):
        return {"updates": self.updates, "phases": list(self.phases)}

    def set_state(self, state):
        self.updates = state["updates"]
        self.phases = list(state["phases"])


def build(plan, *children, until=None, metrics=None):
    group = SearchPlanAdapter(plan,
        [StrategySpec(child, name=child.name) for child in children],
        config=MultiStrategyConfig(total_batch_size=4, adapt_weights=False),
        until=until, metrics=metrics)
    solver = ComposableSolver(CountedSphere(), adapter=group)
    solver.setup()
    return solver, group


def raw_best(feedback):
    return float(np.min(feedback.raw_objectives[:, 0]))


def stagnant_twice(progress):
    return progress.stagnant_updates >= 2


def broken_condition(progress):
    raise ValueError("condition failed")


def test_repeated_serial_reuses_instances_and_counts_each_activation():
    ga, vns = Counter("ga"), Counter("vns")
    solver, group = build(repeat(times=3, body=serial(
        stage("ga", steps=2), stage("vns", steps=1))), ga, vns)
    identities = []
    for _ in range(9):
        identities.append(group.cursor.active()[0].activation_id)
        assert solver.step().committed
    assert group.cursor.completed
    assert (ga.updates, vns.updates) == (6, 3)
    assert (ga.setups, vns.setups, ga.ends, vns.ends) == (1, 1, 0, 0)
    assert identities[0] == identities[1] != identities[3]
    assert solver.step().reason == "search_plan_completed"
    assert solver.evaluation_count == 9
    solver.teardown()
    assert (ga.ends, vns.ends) == (1, 1)


def test_multi_waits_for_every_branch_without_extra_work_from_finished_one():
    a, b, c = Counter("a"), Counter("b"), Counter("c")
    solver, group = build(serial(multi(stage("a", steps=3),
        serial(stage("b", steps=1), stage("c", steps=1))), stage("a", steps=1)), a, b, c)
    assert solver.step().committed  # a+b
    assert solver.step().committed  # a+c
    assert solver.step().committed  # a only
    assert (a.updates, b.updates, c.updates) == (3, 1, 1)
    assert solver.step().committed  # a in next serial position
    assert group.cursor.completed
    assert solver.evaluation_count == 6


def test_local_goal_completion_advances_serial_and_does_not_stop_root():
    a, b = Counter("a", terminal_at=1), Counter("b")
    solver, group = build(serial(stage("a"), stage("b", steps=2)), a, b)
    assert solver.step().committed
    assert solver.step().committed  # consumes local terminal, then runs b
    assert (a.updates, b.updates) == (1, 1)
    assert not group.cursor.completed
    assert solver.step().committed
    assert group.cursor.completed


def test_waiting_sibling_does_not_stop_a_runnable_branch_or_consume_quota():
    a, b = Counter("a", wait=True), Counter("b")
    solver, group = build(multi(stage("a", steps=1), stage("b", steps=2)), a, b)
    assert solver.step().committed
    assert solver.step().committed
    assert solver.step().status == "idle"
    assert a.updates == 0 and b.updates == 2
    assert group.cursor.active()[0].count == 0
    a.wait = False
    assert solver.step().committed
    assert group.cursor.completed


def test_stagnation_uses_only_new_local_updates_and_rearms_on_next_activation():
    ga, vns = Counter("ga"), Counter("vns")
    solver, group = build(repeat(times=2, body=serial(stage("ga", steps=100),
        stage("vns", steps=2))), ga, vns,
        until={"ga": stagnant_twice}, metrics={"ga": raw_best})
    for _ in range(10):  # each cycle: 3 ga samples, then 2 vns updates
        assert solver.step().committed
    assert (ga.updates, vns.updates) == (6, 4)
    assert group.cursor.completed


def test_condition_exception_rolls_back_control_and_does_not_evaluate():
    ga, vns = Counter("ga"), Counter("vns")
    solver, group = build(serial(stage("ga", steps=3), stage("vns", steps=1)),
                           ga, vns, until={"ga": broken_condition})
    assert solver.step().committed
    before = copy.deepcopy(group.cursor.get_state())
    with pytest.raises(ValueError, match="condition failed"):
        solver.step()
    assert group.cursor.get_state() == before
    assert solver.evaluation_count == 1
    assert (ga.updates, vns.updates) == (1, 0)


def test_empty_finite_structure_finishes_without_evaluation_or_generation():
    ga = Counter("ga")
    solver, group = build(repeat(times=100, body=serial(stage("ga", steps=0))), ga)
    result = solver.step()
    assert result.terminal and not result.committed
    assert solver.generation == solver.evaluation_count == 0
    assert ga.updates == 0


def test_checkpoint_round_trip_keeps_position_conditions_and_unique_owners():
    plan = repeat(times=2, body=serial(stage("ga", steps=3), stage("vns", steps=2)))
    a, b = Counter("ga"), Counter("vns")
    solver, group = build(plan, a, b)
    for _ in range(4):
        assert solver.step().committed
    state = group.get_state()
    c, d = Counter("ga"), Counter("vns")
    other, resumed = build(plan, c, d)
    resumed.set_state(state)
    assert resumed.cursor.get_state() == group.cursor.get_state()
    for _ in range(6):
        assert other.step().committed
    assert resumed.cursor.completed
    assert (c.updates, d.updates) == (6, 4)


def test_same_owner_in_parallel_is_rejected_but_serial_reuse_is_allowed():
    with pytest.raises(ValueError, match="share.*owner"):
        multi(stage("ga", steps=2), stage("ga", steps=1))
    ga = Counter("ga")
    solver, group = build(serial(stage("ga", steps=1, label="first"),
                                stage("ga", steps=1, label="second")), ga)
    assert solver.step().committed and solver.step().committed
    assert ga.phases == ["first", "second"]
    assert len(group.units) == 1


def test_small_candidate_budget_rotates_between_parallel_owners():
    a, b = Counter("a"), Counter("b")
    group = SearchPlanAdapter(multi(stage("a"), stage("b", steps=1)),
        [StrategySpec(a, "a"), StrategySpec(b, "b")],
        config=MultiStrategyConfig(total_batch_size=1, adapt_weights=False))
    solver = ComposableSolver(CountedSphere(), adapter=group)
    solver.setup()
    assert solver.step().committed and solver.step().committed
    assert a.updates == b.updates == 1
    assert not group.cursor.completed  # unbounded a did not starve finite b


def test_condition_cannot_abandon_a_running_pool_task():
    from nsgablack.adapters import PoolTaskSpec, VNSAdapter
    with pytest.raises(ValueError, match="until cannot abandon"):
        SearchPlanAdapter(repeat(times=2, body=stage("vns")),
            [StrategySpec(VNSAdapter(), "vns", pool_task=PoolTaskSpec(steps=30))],
            until={"vns": stagnant_twice})


def test_unequal_weights_do_not_overallocate_the_candidate_budget():
    from nsgablack.adapters import StrategyRouterAdapter
    for adapter_type in (StrategyRouterAdapter, SearchPlanAdapter):
        specs = [StrategySpec(Counter("a"), "a", weight=100.),
                 StrategySpec(Counter("b"), "b", weight=1.)]
        config = MultiStrategyConfig(total_batch_size=2, adapt_weights=False)
        args = (multi(stage("a", steps=1), stage("b", steps=1)), specs)
        group = (adapter_type(*args, config=config) if adapter_type is SearchPlanAdapter
                 else adapter_type(strategies=specs, config=config))
        budgets = group._allocate_role_budgets()
        assert sum(budgets.values()) == 2
        assert budgets == {"a": 1, "b": 1}


def test_runtime_inspection_checks_plan_without_running_or_rebuilding_search():
    from blackbase.orchestration import ExecutionCursor
    from nsgablack.utils.runtime_contracts import inspect_runtime_contracts
    ga = Counter("ga")
    solver, group = build(stage("ga", steps=3), ga)
    assert not [item for item in inspect_runtime_contracts(solver)
                if item[0] == "search-plan-contract-invalid"]
    group.cursor = ExecutionCursor(stage("ga", steps=4))
    assert any(code == "search-plan-contract-invalid" for code, _message in inspect_runtime_contracts(solver))
    assert ga.updates == 0 and ga.setups == 1


def test_repeated_initialization_only_task_does_not_turn_into_unbounded_search():
    from blackbase.types import CandidateBatch
    from nsgablack.adapters import NSGA2Adapter, PoolTaskSpec
    ga = NSGA2Adapter(population_size=2, offspring_size=1)
    group = SearchPlanAdapter(repeat(times=2, body=stage("ga")),
        [StrategySpec(ga, "ga", pool_task=PoolTaskSpec(mode="initialize", shuffle=False))])
    solver = ComposableSolver(CountedSphere(), adapter=group)
    solver.setup()
    solver.store_solutions(CandidateBatch.from_candidates([np.array([2.]), np.array([3.])],
                                                       candidate_tokens=("seed:a", "seed:b")))
    assert solver.step().committed
    old_unit = ga.algorithm_unit
    assert solver.step().reason == "search_plan_completed"
    assert group.cursor.completed and ga.algorithm_unit is old_unit
    assert solver.evaluation_count == 2


def test_empty_compete_task_completes_without_unrequested_search_work():
    from nsgablack.adapters import NSGA2Adapter, PoolTaskSpec
    ga = NSGA2Adapter(population_size=2, offspring_size=1)
    group = SearchPlanAdapter(stage("ga"), [StrategySpec(ga, "ga", pool_task=PoolTaskSpec(
        mode="compete", on_insufficient="available"))])
    solver = ComposableSolver(CountedSphere(), adapter=group)
    solver.setup()
    assert solver.step().reason == "search_plan_completed"
    assert solver.evaluation_count == 0 and ga.algorithm_unit is None


def test_completed_schedule_does_not_claim_a_global_goal_inside_an_ordinary_router():
    from nsgablack.adapters import StrategyRouterAdapter
    finished = SearchPlanAdapter(stage("a", steps=0), [StrategySpec(Counter("a"), "a")])
    waiting = Counter("b", wait=True)
    root = StrategyRouterAdapter(strategies=[StrategySpec(finished, "local_plan"),
                                             StrategySpec(waiting, "waiting")])
    solver = ComposableSolver(CountedSphere(), adapter=root)
    solver.setup()
    outcome = solver.step()
    assert outcome.status == "idle" and not outcome.stop_requested
    assert solver.evaluation_count == 0


def test_plain_serial_order_does_not_implicitly_seed_the_next_algorithm():
    class IndependentCounter(Counter):
        def propose(self, control, context):
            assert not context["seeds"]
            return super().propose(control, context)
    ga, local = Counter("ga"), IndependentCounter("local")
    solver, group = build(serial(stage("ga", steps=1), stage("local", steps=1)), ga, local)
    assert solver.step().committed
    assert group.shared_state["best_x"] is not None
    assert solver.step().committed
    assert group.cursor.completed
