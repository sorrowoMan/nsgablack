"""Pool handoffs follow real plan activations, not global generations."""
from __future__ import annotations

import numpy as np
import pytest

from blackbase.contracts import BatchDisposition
from blackbase.orchestration import ExecutionPlan
from blackbase.types import CandidateBatch, UnknownState
from nsgablack.adapters import (
    FixedCandidateAdapter, MultiStrategyConfig, NSGA2Adapter, PoolTaskSpec,
    RoleSpec, StrategyRouterAdapter, StrategySpec, VNSAdapter,
)
from nsgablack.adapters.pool_tasks import PoolTaskAdapter
from nsgablack.adapters.search_plan import SearchPlanAdapter
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.plugins import CheckpointResumePlugin
from nsgablack.representation import RepresentationPipeline


class Sphere(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, objectives=["min"], bounds=[(-100., 100.)])
        self.calls = []
        self.selections = 0

    def evaluate(self, candidate):
        self.calls.append(float(candidate[0]))
        return [float(candidate[0] ** 2)]


class Descend:
    def initialize(self, problem, context):
        return np.array([10.])

    def mutate(self, candidate, context):
        return candidate - 1.


def initial_refs(control, context):
    control.problem.selections += 1
    return control.solution_pool.select(stage="initial")


def task_wrappers(adapter):
    found, seen = {}, set()

    def visit(item):
        if id(item) in seen:
            return
        seen.add(id(item))
        if isinstance(item, PoolTaskAdapter):
            found[item.role] = item
        for child in item.step_transaction_children():
            visit(child)

    visit(adapter)
    return found


def add_seeds(solver, values):
    states = [UnknownState([float(value)], {"seed_index": index})
              for index, value in enumerate(values)]
    batch = CandidateBatch.from_candidates(states,
        candidate_tokens=tuple(f"seed:{index}:{value}" for index, value in enumerate(values)))
    return solver.store_solutions(batch)


def build(plan, *, counts=None, seeds=(10.,), shortage="error"):
    counts = {"local": 1} if counts is None else counts
    leaves = {name: VNSAdapter(name=f"{name}_vns", batch_size=1,
                              restart_on_stagnation=False) for name in counts}
    specs = [StrategySpec(adapter=leaves[name], name=name,
        pool_task=PoolTaskSpec(initial_refs, mode="refine", steps=2,
            count=count, shuffle=False, output=f"{name}_trials",
            on_insufficient=shortage)) for name, count in counts.items()]
    adapter = SearchPlanAdapter(plan, strategies=specs,
        config=MultiStrategyConfig(total_batch_size=max(1, len(counts)), adapt_weights=False))
    operator = Descend()
    solver = ComposableSolver(Sphere(), adapter=adapter,
        representation_pipeline=RepresentationPipeline(initializer=operator, mutator=operator))
    solver.set_random_seed(71)
    solver.setup()
    if seeds:
        add_seeds(solver, seeds)
    return solver, adapter, leaves


def repeated_local():
    return ExecutionPlan.repeat(ExecutionPlan.leaf("local"), count=2)


def test_each_repeated_refinement_gets_a_new_request_but_keeps_one_algorithm_owner():
    solver, plan, leaves = build(repeated_local())
    task = task_wrappers(plan)["local"]
    assert solver.step().committed
    first = task.task_status["request"]
    assert task.task_status["steps"] == 1
    assert solver.step().committed
    assert task.task_status["status"] == "done"
    assert task.task_status["request"] == first
    assert leaves["local"].current_x[0] == 9.
    assert solver.step().committed
    assert task.task_status["request"] != first
    assert task.task_status["steps"] == 1
    assert leaves["local"].current_x[0] == 10.
    assert solver.step().committed
    assert task.task_status["status"] == "done"
    assert plan.cursor.completed
    assert solver.problem.selections == 2
    assert solver.problem.calls == [10., 9., 10., 9.]
    assert task.inner is leaves["local"]


def test_multi_waits_for_every_seed_without_redispatching_a_finished_branch():
    plan = ExecutionPlan.multi(ExecutionPlan.leaf("fast"), ExecutionPlan.leaf("many"))
    solver, adapter, _ = build(plan, counts={"fast": 1, "many": "all"}, seeds=(10., 20.))
    tasks = task_wrappers(adapter)
    assert solver.step().committed
    assert solver.step().committed
    assert tasks["fast"].task_status["status"] == "done"
    assert len(tasks["fast"].get_pool_task_results(solver)) == 1
    assert tasks["many"].task_status["status"] == "running"
    assert tasks["many"].task_status["next"] == 1
    assert not adapter.cursor.completed
    request = tasks["many"].task_status["request"]
    assert solver.step().committed
    assert tasks["many"].task_status["request"] == request
    assert solver.step().committed
    assert tasks["many"].task_status["status"] == "done"
    assert tasks["many"].task_status["next"] == 2
    final = tasks["many"].get_pool_task_results(solver)
    assert len(final) == 2
    np.testing.assert_array_equal(solver.solution_pool.read(final).numeric_matrix, [[9.], [19.]])
    assert adapter.cursor.completed
    assert len(solver.problem.calls) == 6
    assert solver.evaluation_count == 6


def test_checkpoint_continues_the_same_frozen_request_then_starts_the_next_activation():
    source, source_plan, _ = build(repeated_local(), counts={"local": "all"}, seeds=(10., 20.))
    assert source.step().committed
    before = task_wrappers(source_plan)["local"].task_status
    initial = source.solution_pool.select(stage="initial")
    historical = source.solution_pool.select()
    target, target_plan, target_leaves = build(repeated_local(), counts={"local": "all"}, seeds=())
    writer, reader = CheckpointResumePlugin(), CheckpointResumePlugin()
    writer.cfg.strict = reader.cfg.strict = True
    writer.attach(source)
    reader.attach(target)
    reader._restore_payload(solver=target,
        payload=writer._build_payload(solver=source, reason="plan-pool-task"))
    restored = task_wrappers(target_plan)["local"]
    assert restored.task_status == before
    assert target.solution_pool.select(stage="initial") == initial
    assert target.solution_pool.select() == historical
    assert not target.problem.calls
    assert target.problem.selections == 0
    for _ in range(3):
        assert target.step().committed
        assert restored.task_status["request"] == before["request"]
    assert restored.task_status["status"] == "done"
    assert target.problem.calls == [9., 20., 19.]
    assert target.problem.selections == 0
    assert target_leaves["local"].current_x[0] == 19.
    assert target.step().committed
    assert restored.task_status["request"] != before["request"]
    assert target.problem.selections == 1


def test_zero_admission_does_not_finish_or_advance_the_active_request():
    solver, plan, _ = build(repeated_local())
    task = task_wrappers(plan)["local"]
    assert solver.step().committed
    before = task.task_status
    accepted = solver.solution_pool.select()

    class Reject:
        policy_id = "reject-plan-neighbor"

        def select(self, candidates, feedback, context):
            return BatchDisposition(len(candidates.semantic_states), ())

    solver.set_evaluation_acceptance_policy(Reject())
    assert not solver.step().committed
    assert task.task_status == before
    assert solver.solution_pool.select() == accepted
    assert not plan.cursor.completed
    assert solver.evaluation_count == 2
    solver.set_evaluation_acceptance_policy(None)
    assert solver.step().committed
    assert task.task_status["status"] == "done"
    assert task.task_status["request"] == before["request"]
    assert solver.problem.selections == 1
    assert solver.step().committed
    assert task.task_status["request"] != before["request"]


def current_ga_member(control, context):
    return task_wrappers(control.adapter)["ga"].inner.get_population_solution_refs(control)[:1]


def current_refined_result(control, context):
    return control.adapter.get_pool_task_results(control, "local")


def test_return_competes_once_per_round_through_the_same_ga_instance():
    ga = NSGA2Adapter(name="ga", population_size=4, offspring_size=1)
    local = VNSAdapter(name="local_vns", batch_size=1, restart_on_stagnation=False)
    cycle = ExecutionPlan.serial(
        ExecutionPlan.leaf("ga", steps=1, label="search"),
        ExecutionPlan.leaf("local", label="refine"),
        ExecutionPlan.leaf("ga", label="return"))
    adapter = SearchPlanAdapter(ExecutionPlan.repeat(cycle, count=2), strategies=[
        StrategySpec(ga, "ga", pool_task=PoolTaskSpec(current_refined_result,
            mode="compete", phases=("return",), shuffle=False)),
        StrategySpec(local, "local", pool_task=PoolTaskSpec(current_ga_member,
            mode="refine", steps=2, output="history", shuffle=False)),
    ], config=MultiStrategyConfig(total_batch_size=4, adapt_weights=False))
    operator = Descend()
    solver = ComposableSolver(Sphere(), adapter=adapter,
        representation_pipeline=RepresentationPipeline(initializer=operator, mutator=operator))
    solver.set_random_seed(5)
    solver.setup()
    assert solver.step().committed
    unit = ga.algorithm_unit
    tasks = task_wrappers(adapter)
    returns, accepted_returns = [], []
    for index in range(7):
        assert solver.step().committed
        assert ga.algorithm_unit is unit
        if index in (2, 6):
            assert tasks["ga"].task_status["status"] == "done"
            returns.append(tasks["ga"].task_status["request"])
            accepted_returns.append(tasks["ga"].task_status["count"])
    assert adapter.cursor.completed
    assert len(set(returns)) == 2
    assert accepted_returns == [1, 1]  # The cumulative trial history is not replayed.
    assert tasks["ga"].inner is ga
    assert ga.population.shape == (4, 1)


def test_available_empty_request_finishes_without_unpublished_handles_or_fake_commit():
    solver, plan, _ = build(ExecutionPlan.leaf("local"), seeds=(), shortage="available")
    outcome = solver.step()
    assert not outcome.committed
    assert not solver.problem.calls
    assert solver.evaluation_count == 0
    assert solver.generation == 0
    assert plan.cursor.completed
    task = task_wrappers(plan)["local"]
    state = task.get_state()["pool_task"]
    assert state["status"] == "done"
    assert state["count"] == 0
    assert state["view"] is None and state["output"] is None
    assert not solver.solution_pool.published_subpool_names()
    assert task.get_pool_task_results(solver) == ()
    task._validate_local(state)


def test_results_are_current_request_final_choices_and_are_hidden_until_commit(monkeypatch):
    solver, plan, _ = build(repeated_local())
    task = task_wrappers(plan)["local"]
    with pytest.raises(RuntimeError, match="completion"):
        task.get_pool_task_results(solver)
    assert solver.step().committed
    with pytest.raises(RuntimeError, match="completion"):
        task.get_pool_task_results(solver)
    original = task.update
    hidden = []

    def update(*args, **kwargs):
        original(*args, **kwargs)
        if task.task_status["status"] == "done":
            with pytest.raises(RuntimeError, match="commit"):
                task.get_pool_task_results(solver)
            hidden.append(task.task_status["request"])

    monkeypatch.setattr(task, "update", update)
    assert solver.step().committed
    first = task.get_pool_task_results(solver)
    assert len(first) == 1
    np.testing.assert_array_equal(solver.solution_pool.read(first).numeric_matrix, [[9.]])
    assert solver.step().committed
    with pytest.raises(RuntimeError, match="completion"):
        task.get_pool_task_results(solver)
    assert solver.step().committed
    second = task.get_pool_task_results(solver)
    assert len(second) == 1 and set(first).isdisjoint(second)
    assert len(set(hidden)) == 2
    # Old final views and aggregate trials remain readable; neither is silently
    # substituted for the current request's one selected final candidate.
    np.testing.assert_array_equal(solver.solution_pool.read(first).numeric_matrix, [[9.]])
    history = solver.solution_pool.subpool_refs(task.task_status["output"])
    assert len(history) == 4
    assert set((*first, *second)).issubset(history)


@pytest.mark.parametrize("mode,output,match", [
    ("initialize", "history", "refine"),
    ("compete", "history", "refine"),
])
def test_result_delivery_requires_a_refinement(mode, output, match):
    inner = NSGA2Adapter() if mode == "compete" else VNSAdapter()
    task = PoolTaskAdapter(inner, PoolTaskSpec(mode=mode, output=output),
                           role="isolated", namespace="isolated")
    with pytest.raises(ValueError, match=match):
        task.get_pool_task_results(None)


def test_empty_task_does_not_publish_a_marker_when_the_following_stage_commits():
    local = VNSAdapter(name="empty_vns", batch_size=1, restart_on_stagnation=False)
    after = FixedCandidateAdapter(name="after")
    plan = SearchPlanAdapter(ExecutionPlan.serial(
        ExecutionPlan.leaf("local"), ExecutionPlan.leaf("after", steps=1)), strategies=[
        StrategySpec(local, "local", pool_task=PoolTaskSpec(initial_refs,
            steps=2, output="empty_trials", on_insufficient="available")),
        StrategySpec(after, "after"),
    ], config=MultiStrategyConfig(total_batch_size=1, adapt_weights=False))
    operator = Descend()
    solver = ComposableSolver(Sphere(), adapter=plan,
        representation_pipeline=RepresentationPipeline(initializer=operator, mutator=operator))
    solver.setup()
    outcome = solver.step()
    if not outcome.committed:
        assert solver.generation == solver.evaluation_count == 0
        outcome = solver.step()
    assert outcome.committed
    assert solver.evaluation_count == 1
    assert len(solver.solution_pool.select()) == 1
    assert plan.cursor.completed
    state = task_wrappers(plan)["local"].get_state()["pool_task"]
    assert state["status"] == "done" and state["view"] is state["output"] is None
    assert not any("task:local" in name or "empty_trials" in name
                   for name in solver.solution_pool.published_subpool_names())


def test_empty_partition_worker_does_not_drop_another_workers_frozen_queue():
    def factory(index):
        return VNSAdapter(name=f"worker_{index}", batch_size=1, restart_on_stagnation=False)

    router = StrategyRouterAdapter(name="partition", roles=[RoleSpec(
        "local", factory, n_units=3, pool_task=PoolTaskSpec(initial_refs,
            steps=2, count="all", distribution="partition", shuffle=False,
            output="trials", on_insufficient="available")),
    ], config=MultiStrategyConfig(total_batch_size=3, adapt_weights=False))
    operator = Descend()
    solver = ComposableSolver(Sphere(), adapter=router,
        representation_pipeline=RepresentationPipeline(initializer=operator, mutator=operator))
    solver.setup()
    add_seeds(solver, (10.,))
    assert solver.step().committed
    tasks = [unit.adapter for unit in router.units]
    assert tasks[0].task_status["status"] == "running"
    for task in tasks[1:]:
        state = task.get_state()["pool_task"]
        assert state["status"] == "done" and state["count"] == 0
        assert state["view"] is state["output"] is None
        assert task.get_pool_task_results(solver) == ()
    assert solver.step().committed
    assert all(task.task_status["status"] == "done" for task in tasks)
    assert len(tasks[0].get_pool_task_results(solver)) == 1
    assert solver.problem.selections == 1
    assert solver.problem.calls == [10., 9.]
