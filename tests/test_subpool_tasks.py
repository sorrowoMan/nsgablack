import numpy as np
import pytest

from blackbase.types import CandidateBatch, UnknownState
from blackbase.context import create_snapshot_store
from nsgablack.core import BlackBoxProblem, ComposableSolver, PoolRetentionPolicy
from nsgablack.core.state.solution_pool import SolutionPool
from nsgablack.adapters import (
    NSGA2Adapter, VNSAdapter, StrategyRouterAdapter, RoleSpec,
    MultiStrategyConfig, PoolTaskSpec,
)
from nsgablack.representation import RepresentationPipeline


class Sphere(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, objectives=["min"], bounds=[(-100., 100.)])

    def evaluate(self, x):
        return [float(x[0] ** 2)]


class Operator:
    context_requires = ("vns_k",)

    def __init__(self, delta=0.):
        self.delta = delta

    def initialize(self, problem, context):
        return np.array([10.])

    def mutate(self, candidate, context):
        return candidate - self.delta


def top_twenty(control, context):
    refs = control.solution_pool.select()
    f, v = control.solution_pool.read_raw_feedback(refs)
    order = np.argsort(f[:, 0] + 1e6*v, kind="stable")[:20]
    return tuple(refs[i] for i in order)


def phases(ctx):
    if ctx["step"] < 1:
        return "explore"
    tasks = ctx["pool_tasks"]
    refiners = [v for k, v in tasks.items() if not k.startswith("ga:")]
    return "return" if refiners and all(v["status"] == "done" for v in refiners) else "refine"


def build(*, retention=False):
    def vns(name, operator):
        adapter = VNSAdapter(name=name, batch_size=2, restart_on_stagnation=False)
        adapter.set_mutation_operator(operator)
        return adapter
    ga = NSGA2Adapter(name="ga", population_size=20, offspring_size=20)
    plan = PoolTaskSpec(top_twenty, steps=2, output="refined")
    router = StrategyRouterAdapter(roles=[
        RoleSpec("ga", ga, pool_task=PoolTaskSpec("refined", mode="compete", phases=("return",))),
        RoleSpec("fine", lambda uid: vns(f"fine_{uid}", "fine"), n_units=2, pool_task=plan),
        RoleSpec("coarse", lambda uid: vns(f"coarse_{uid}", "coarse"), n_units=2, pool_task=plan),
    ], config=MultiStrategyConfig(total_batch_size=40, adapt_weights=False, phase_policy=phases,
         phase_roles={"explore": ["ga"], "refine": ["fine", "coarse"], "return": ["ga"]}))
    pipeline = RepresentationPipeline(initializer=Operator(), mutator=Operator(),
                                      mutation_operators={"fine": Operator(1.), "coarse": Operator(2.)})
    solver = ComposableSolver(Sphere(), adapter=router, representation_pipeline=pipeline)
    if retention:
        solver.set_solution_pool_retention(PoolRetentionPolicy(idle_steps=2))
    solver.setup()
    return solver, router, ga


def test_twenty_seeds_two_vns_variants_return_to_ga_selection():
    solver, router, ga = build(retention=True)
    assert solver.step().committed
    original_tokens = tuple(ga.get_population_candidate_tokens())
    assert len(set(original_tokens)) == 20  # Equal values still have distinct identities.
    assert solver.step().committed  # Every worker evaluates its assigned seed.
    for unit in router.units[1:]:
        assert unit.adapter.inner.current_x[0] == 10.
        assert unit.adapter.inner.current_score == 100.
    for _ in range(19):
        assert solver.step().committed
    assert all(u.adapter.task_status["status"] == "done" for u in router.units[1:])
    for _ in range(3):  # Router budget admits the returned subpool in chunks.
        assert solver.step().committed
        if router.units[0].adapter.task_status["status"] == "done":
            break
    assert ga.population.shape == (20, 1)
    assert np.all(ga.population[:, 0] == 8.)
    assert set(ga.get_population_candidate_tokens()).isdisjoint(original_tokens)
    refs = solver.solution_pool.subpool_refs(f"{router.name}/refined")
    batch = solver.read_solutions(refs)
    assert {8., 9., 10.} == set(batch.numeric_matrix[:, 0])
    # Results belong to their values, not to the original input score.
    f, _ = solver.solution_pool.read_raw_feedback(refs)
    np.testing.assert_array_equal(f[:, 0], batch.numeric_matrix[:, 0]**2)


def test_second_worker_failure_restores_first_worker_and_subpool_membership():
    solver, router, _ = build()
    solver.step()
    before = solver.solution_pool.get_state()
    first = router.units[1].adapter
    original = router.units[2].adapter.inner.update
    def fail(*args, **kwargs):
        raise RuntimeError("second worker failed")
    router.units[2].adapter.inner.update = fail
    with pytest.raises(RuntimeError, match="second worker failed"):
        solver.step()
    assert first.task_status["status"] is None
    assert solver.solution_pool.get_state()["retention"]["owners"] == before["retention"]["owners"]
    router.units[2].adapter.inner.update = original
    assert solver.step().committed
    assert first.inner.current_score == 100.


def test_rejected_seed_is_retried_instead_of_random_restart():
    from blackbase.contracts import BatchDisposition
    solver, router, _ = build()
    solver.step()
    class Reject:
        policy_id = "reject"
        def select(self, candidates, feedback, context):
            return BatchDisposition(len(candidates.semantic_states), ())
    solver.set_evaluation_acceptance_policy(Reject())
    assert not solver.step().committed
    solver.set_evaluation_acceptance_policy(None)
    assert solver.step().committed
    for unit in router.units[1:]:
        assert unit.adapter.inner.current_x[0] == 10.
        assert unit.adapter.inner.current_score == 100.


def test_subpools_share_refs_detach_membership_and_restore_portably():
    pool = SolutionPool(create_snapshot_store(backend="memory"))
    states = (UnknownState(values=np.array([3.]), metadata={"label": "seed"}),)
    refs = pool.put(CandidateBatch(states, np.array([[3.]]), ("token",)), stage="accepted")
    pool.create_subpool("left", refs)
    pool.create_subpool("right", refs)
    assert pool.record_count == 1
    baseline = pool.snapshot_step_state()
    pool.drop_subpool("left")
    assert pool.subpool_refs("right") == refs
    pool.restore_step_state(baseline)
    assert pool.subpool_refs("left") == refs
    restored = SolutionPool(create_snapshot_store(backend="memory"))
    restored.set_state(pool.get_state())
    assert restored.select(subpool="right") == refs
    np.testing.assert_array_equal(restored.read(refs).numeric_matrix, [[3.]])


def test_subpool_outputs_are_hidden_until_commit_and_rollback_removes_them():
    pool = SolutionPool(create_snapshot_store(backend="memory"))
    pool.create_subpool("results")
    batch = CandidateBatch((UnknownState(values=np.array([3.])),), np.array([[3.]]), ("token",))
    baseline = pool.snapshot_step_state()
    pool.begin_attempt()
    pending = pool.put(batch, stage="accepted")
    pool.add_to_subpool("results", pending)
    assert pool.subpool_refs("results") == ()
    pool.restore_step_state(baseline)
    assert pool.subpool_refs("results") == ()
    assert pool.record_count == 0
    pool.begin_attempt()
    pending = pool.put(batch, stage="accepted")
    pool.add_to_subpool("results", pending)
    pool.prepare_publication()
    assert pool.subpool_refs("results") == ()
    pool.commit_publication()
    assert pool.subpool_refs("results") == pending


def test_checkpoint_continues_partially_completed_tasks():
    from nsgablack.plugins import CheckpointResumePlugin
    source, router, _ = build()
    for _ in range(4):
        source.step()
    target, other, _ = build()
    writer, reader = CheckpointResumePlugin(), CheckpointResumePlugin()
    writer.attach(source)
    reader.attach(target)
    reader._restore_payload(solver=target, payload=writer._build_payload(solver=source, reason="subpool"))
    a = router.units[1].adapter
    b = other.units[1].adapter
    assert a.task_status == b.task_status
    assert a.inner.current_score == b.inner.current_score
    assert a._local["results"] == b._local["results"]
    assert source.step().committed and target.step().committed
    assert a.task_status == b.task_status
    np.testing.assert_array_equal(a.inner.current_x, b.inner.current_x)


def test_task_rejects_algorithm_without_declared_intake():
    from nsgablack.adapters import AlgorithmAdapter, PoolTaskAdapter
    class External(AlgorithmAdapter):
        def propose(self, control, context):
            return []
        def update(self, control, candidates, feedback, context):
            pass
    with pytest.raises(ValueError, match="pool initialize"):
        PoolTaskAdapter(External(name="external"), PoolTaskSpec(top_twenty), role="external")


def initial_refs(control, context):
    return control.solution_pool.select(stage="initial")


def test_nested_same_named_roles_have_distinct_subpool_namespaces():
    def inner():
        return StrategyRouterAdapter(name="inner", roles=[
            RoleSpec("local", VNSAdapter(batch_size=1),
                     pool_task=PoolTaskSpec(initial_refs, steps=1, output="results")),
        ], config=MultiStrategyConfig(total_batch_size=1, adapt_weights=False))
    left, right = inner(), inner()
    outer = StrategyRouterAdapter(roles=[RoleSpec("left", left), RoleSpec("right", right)],
        config=MultiStrategyConfig(total_batch_size=2, adapt_weights=False))
    solver = ComposableSolver(Sphere(), adapter=outer,
        representation_pipeline=RepresentationPipeline(initializer=Operator(), mutator=Operator()))
    solver.setup()
    solver.store_solutions(CandidateBatch((UnknownState(values=np.array([3.])),),
                                          np.array([[3.]]), ("source",)))
    assert solver.step().committed
    outputs = [router.units[0].adapter.task_status["output"] for router in (left, right)]
    assert outputs[0] != outputs[1]
    for name in outputs:
        batch = solver.read_solutions(solver.solution_pool.subpool_refs(name))
        np.testing.assert_array_equal(batch.numeric_matrix, [[3.]])


def test_wrapped_roles_still_reject_shared_child_instance():
    shared = VNSAdapter()
    router = StrategyRouterAdapter(roles=[
        RoleSpec("a", shared, pool_task=PoolTaskSpec(initial_refs)),
        RoleSpec("b", shared, pool_task=PoolTaskSpec(initial_refs)),
    ])
    solver = ComposableSolver(Sphere(), adapter=router)
    with pytest.raises(ValueError, match="independent Adapter objects"):
        solver.setup()


def test_same_task_binding_runs_sa_without_a_vns_specific_branch():
    from nsgablack.adapters import SimulatedAnnealingAdapter
    router = StrategyRouterAdapter(roles=[
        RoleSpec("sa", SimulatedAnnealingAdapter(batch_size=2, random_seed=7),
                 pool_task=PoolTaskSpec(initial_refs, steps=2, output="results")),
    ], config=MultiStrategyConfig(total_batch_size=2, adapt_weights=False))
    solver = ComposableSolver(Sphere(), adapter=router,
        representation_pipeline=RepresentationPipeline(initializer=Operator(), mutator=Operator(1.)))
    solver.setup()
    solver.store_solutions(CandidateBatch((UnknownState(values=np.array([3.])),),
                                          np.array([[3.]]), ("source",)))
    assert solver.step().committed
    assert solver.step().committed
    task = router.units[0].adapter
    assert task.task_status["status"] == "done"
    refs = solver.solution_pool.subpool_refs(task.task_status["output"])
    candidates = solver.read_solutions(refs).numeric_matrix
    assert candidates[0, 0] == 3.
    raw, _ = solver.solution_pool.read_raw_feedback(refs)
    np.testing.assert_array_equal(raw[:, 0], candidates[:, 0] ** 2)
