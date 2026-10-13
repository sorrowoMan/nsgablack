"""Producer-scoped direction views, local projections and transactional tasks."""
import copy

import numpy as np
import pytest

from nsgablack.adapters import (MOEADAdapter, NSGA2Adapter, VNSAdapter, RoleSpec,
    StrategyRouterAdapter, MultiStrategyConfig, PoolTaskSpec, subpools)
from nsgablack.adapters.subpools import adapter_path
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.core.evaluation_feedback import OptimizationFeedbackBatch
from nsgablack.core.state.pool_views import ObjectiveProjection
from nsgablack.representation import RepresentationPipeline


class Delivery(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, objectives=["min", "min"], bounds=[(-20., 20.)])

    def evaluate(self, x):
        return [float(x[0] ** 2), float((x[0] - 10.) ** 2)]


class Routes:
    context_requires = ("vns_k",)

    def initialize(self, problem, context):
        return np.array([8.])

    def mutate(self, candidate, context):
        return candidate - 1.


def phases(ctx):
    if ctx["step"] == 0:
        return "explore"
    tasks = [v for k, v in ctx["pool_tasks"].items() if k.startswith("local:")]
    return "return" if tasks and all(v["status"] == "done" for v in tasks) else "refine"


def build(*, n=6, take=None, workers=2, steps=2, second=False, ga=False, setup=True,
          method="weighted_sum"):
    producer = MOEADAdapter(name="directions", population_size=n, batch_size=2,
                           neighborhood_size=2, decomposition=method)
    selector = subpools.all(producer) if take is None else subpools.random(take, producer)
    roles = [RoleSpec("producer", producer,
        pool_task=PoolTaskSpec("refined", mode="compete", phases=("return",)))]
    search_roles = ["producer"]
    if second:
        # Same type AND same name: only the concrete instance distinguishes it.
        roles.append(RoleSpec("other", MOEADAdapter(name="directions", population_size=4,
            batch_size=2, decomposition="weighted_sum")))
        search_roles.append("other")
    if ga:
        roles.append(RoleSpec("ga", NSGA2Adapter(name="ga", population_size=4, offspring_size=2),
                              pool_task=PoolTaskSpec(mode="initialize")))
        search_roles.append("ga")
    roles.append(RoleSpec("local", lambda i: VNSAdapter(name=f"vns_{i}", batch_size=1,
        restart_on_stagnation=False), n_units=workers,
        pool_task=PoolTaskSpec(selector, steps=steps, output="refined", shuffle=False)))
    router = StrategyRouterAdapter(name="mixed", roles=roles,
        config=MultiStrategyConfig(total_batch_size=max(workers, 12), adapt_weights=False,
            phase_policy=phases, phase_roles={"explore": search_roles,
            "refine": ["local"], "return": ["producer"]}))
    solver = ComposableSolver(Delivery(), adapter=router,
        representation_pipeline=RepresentationPipeline(initializer=Routes(), mutator=Routes()))
    solver.set_random_seed(37)
    if setup:
        solver.setup()
    return solver, producer, router


def refiners(router):
    return [u.adapter for u in router.units if u.role == "local"]


@pytest.mark.parametrize("method", ["weighted_sum", "tchebycheff"])
def test_projection_keeps_raw_evidence_and_constraints(method):
    source = OptimizationFeedbackBatch.from_arrays([[4., 5.], [6., 2.]], [0., 3.])
    projection = ObjectiveProjection(method, (.8, .2), (1., 1.) if method == "tchebycheff" else ())
    result = projection.apply(source)
    expected = [4.2, 5.2] if method == "weighted_sum" else [2.4, 4.]
    np.testing.assert_allclose(result.objectives[:, 0], expected)
    np.testing.assert_array_equal(result.raw_objectives, source.objectives)
    np.testing.assert_array_equal(result.raw_violations, source.violations)
    np.testing.assert_array_equal(source.objectives, [[4., 5.], [6., 2.]])


def test_moead_automatically_exports_100_views_and_selection_is_by_instance():
    solver, producer, router = build(n=100, second=True, ga=True)
    pool = solver.solution_pool
    path = adapter_path(router, producer)
    names = pool.projection_subpools(path)
    assert len(names) == 100
    assert len({pool.subpool_metadata(name)["slot"] for name in names}) == 100
    assert all(pool.subpool_metadata(name)["created_by"] == list(path) for name in names)
    assert sum(len(pool.subpool_refs(name)) for name in names) == 100
    other = router.units[1].adapter
    assert len(pool.projection_subpools(adapter_path(router, other))) == 4
    assert pool.projection_subpools(adapter_path(router, router.units[2].adapter)) == ()
    # Views do not copy or synthesize candidate records.
    assert len({r.candidate_token for name in names for r in pool.subpool_refs(name)}) == 100


def test_random_20_selects_views_once_across_workers_and_keeps_source_scope():
    solver, producer, router = build(n=100, take=20, workers=4, second=True, ga=True)
    assert solver.step().committed
    assert solver.step().committed
    workers = refiners(router)
    jobs = [job for worker in workers for job in worker._local["jobs"]]
    assert len(jobs) == len({j["source_view"] for j in jobs}) == 20
    assert all(j["created_by"] == list(adapter_path(router, producer)) for j in jobs)
    before = copy.deepcopy(jobs)
    assert solver.step().committed
    assert before == [j for w in workers for j in w._local["jobs"]]


@pytest.mark.parametrize("method", ["weighted_sum", "tchebycheff"])
def test_all_views_refine_new_candidates_then_return_raw_objectives_to_moead(method):
    solver, producer, router = build(method=method)
    assert solver.step().committed
    assert solver.step().committed
    workers = refiners(router)
    for worker in workers:
        job = worker._local["jobs"][0]
        x = float(worker.inner.current_x[0])
        expected = ObjectiveProjection.from_dict(job["projection"]).apply(
            OptimizationFeedbackBatch.from_arrays([[x*x, (x-10)**2]], [0.]))
        assert worker.inner.current_score == pytest.approx(expected.objectives[0, 0])
    for _ in range(5):
        assert solver.step().committed
    assert all(w.task_status["status"] == "done" for w in workers)
    refs = solver.solution_pool.subpool_refs("mixed/refined")
    x = solver.read_solutions(refs).numeric_matrix[:, 0]
    f, v = solver.solution_pool.read_raw_feedback(refs)
    np.testing.assert_allclose(f, np.stack([x*x, (x-10)**2], axis=1))
    assert f.shape[1] == 2
    assert solver.step().committed
    assert producer.pop_F.shape == (6, 2)
    np.testing.assert_allclose(producer.pop_F,
        np.stack([producer.pop_X[:, 0]**2, (producer.pop_X[:, 0]-10)**2], axis=1))


def test_selected_projection_is_frozen_while_producer_views_change():
    solver, producer, router = build(steps=3)
    solver.step()
    solver.step()
    worker = refiners(router)[0]
    job = copy.deepcopy(worker._local["jobs"][0])
    pool = solver.solution_pool
    name = job["source_view"]
    meta = pool.subpool_metadata(name)
    pool.publish_projection_subpool(name, pool.subpool_refs(name), created_by=meta["created_by"],
        slot=meta["slot"], projection=ObjectiveProjection("weighted_sum", (.3, .7)))
    assert solver.step().committed
    assert worker._local["jobs"][0] == job
    assert worker.inner._projection_frame == job["projection"]


def test_failure_rolls_back_selection_membership_and_random_draw():
    solver, _, router = build(n=8, take=4)
    solver.step()
    before = solver.solution_pool.get_state()
    workers = refiners(router)
    captured = []
    original = workers[1].inner.update
    def fail(*args, **kwargs):
        captured.extend(copy.deepcopy(workers[0]._local["jobs"]))
        raise RuntimeError("second projected refiner failed")
    workers[1].inner.update = fail
    with pytest.raises(RuntimeError, match="second projected"):
        solver.step()
    assert solver.solution_pool.get_state()["subpool_metadata"] == before["subpool_metadata"]
    assert workers[0].task_status["status"] is None
    workers[1].inner.update = original
    assert solver.step().committed
    assert workers[0]._local["jobs"] == captured


def test_checkpoint_resumes_frozen_projection_and_random_selection():
    from nsgablack.plugins import CheckpointResumePlugin
    source, _, first = build(n=8, take=4, steps=3)
    source.step()
    source.step()
    target, _, second = build(n=8, take=4, steps=3, setup=False)
    writer, reader = CheckpointResumePlugin(), CheckpointResumePlugin()
    writer.attach(source)
    reader.attach(target)
    payload = writer._build_payload(solver=source, reason="projection")
    target.queue_restore_envelope(lambda: reader._restore_payload(solver=target, payload=payload))
    target.setup()
    target._apply_pending_restore_envelopes()
    for a, b in zip(refiners(first), refiners(second)):
        assert a._local["jobs"] == b._local["jobs"]
        assert a.inner._projection_frame == b.inner._projection_frame
    assert source.step().committed and target.step().committed
    for a, b in zip(refiners(first), refiners(second)):
        assert a.inner.current_score == b.inner.current_score
        np.testing.assert_array_equal(a.inner.current_x, b.inner.current_x)


def test_unmounted_creator_is_rejected_by_runtime_contract():
    from nsgablack.adapters import PoolTaskAdapter
    external = MOEADAdapter()
    wrapper = PoolTaskAdapter(VNSAdapter(), PoolTaskSpec(subpools.all(external)), role="local")
    with pytest.raises(ValueError, match="not an instance"):
        wrapper.validate_pool_task(NSGA2Adapter())


def test_same_candidate_in_different_directions_remains_separate_jobs():
    solver, producer, router = build(steps=1)
    solver.step()
    pool = solver.solution_pool
    names = pool.projection_subpools(adapter_path(router, producer))
    shared = pool.subpool_refs(names[0])
    for name in names:
        meta = pool.subpool_metadata(name)
        pool.publish_projection_subpool(name, shared, created_by=meta["created_by"],
            slot=meta["slot"], projection=ObjectiveProjection.from_dict(meta["projection"]))
    for _ in range(3):
        assert solver.step().committed
    jobs = [job for worker in refiners(router) for job in worker._local["jobs"]]
    assert len(jobs) == len({job["source_view"] for job in jobs}) == 6
    assert len({job["ref"]["candidate_token"] for job in jobs}) == 1
    assert all(worker.task_status["status"] == "done" for worker in refiners(router))


def test_zero_and_partial_admission_keep_projection_job_and_input_cursor():
    from blackbase.contracts import BatchDisposition
    solver, _, router = build(take=4)
    solver.step()
    class Accept:
        policy_id = "projection_test"
        indices = ()
        def select(self, candidates, feedback, context):
            return BatchDisposition(len(candidates.semantic_states), self.indices)
    policy = Accept()
    solver.set_evaluation_acceptance_policy(policy)
    assert not solver.step().committed
    workers = refiners(router)
    jobs = [copy.deepcopy(w._local["jobs"]) for w in workers]
    policy.indices = (0,)
    assert solver.step().committed
    assert [w._local["steps"] for w in workers] == [1, 0]
    assert workers[1].inner.current_score is None
    solver.set_evaluation_acceptance_policy(None)
    assert solver.step().committed
    assert [w._local["jobs"] for w in workers] == jobs
    assert workers[1].inner._projection_frame == jobs[1][0]["projection"]


def test_projection_publication_is_atomic_with_pool_manifest():
    solver, producer, router = build()
    pool = solver.solution_pool
    creator = adapter_path(router, producer)
    name = pool.projection_subpools(creator)[0]
    before = pool.subpool_metadata(name)
    baseline = pool.snapshot_step_state()
    def stage():
        pool.begin_attempt()
        pool.publish_projection_subpool(name, pool.subpool_refs(name), created_by=creator,
            slot=before["slot"], projection=ObjectiveProjection("weighted_sum", (.3, .7)))
    stage()
    assert name not in pool.projection_subpools(creator)
    pool.restore_step_state(baseline)
    assert pool.subpool_metadata(name) == before
    stage()
    pool.prepare_publication()
    assert name not in pool.projection_subpools(creator)
    pool.commit_publication()
    assert name in pool.projection_subpools(creator)
    assert pool.subpool_metadata(name)["projection"]["weights"] == [.3, .7]


def test_projected_vns_feasibility_cannot_be_outweighed_by_large_objective():
    adapter = VNSAdapter()
    # Isolate selection from candidate binding; production binding is covered above.
    chosen = []
    adapter._accept_candidate = lambda control, candidates, index, context: chosen.append(index)
    projection = ObjectiveProjection("weighted_sum", (.5, .5))
    feedback = projection.apply(OptimizationFeedbackBatch.from_arrays([[1e20, 1e20], [-1e20, -1e20]], [0., 1.]))
    adapter.update(None, [np.array([0.]), np.array([1.])], feedback, {})
    assert chosen == [0]
    adapter.update(None, [np.array([1.])], feedback.subset([1]), {})
    assert chosen == [0]


def test_projection_checkpoint_rejects_missing_jobs_and_wrong_creator():
    solver, _, router = build()
    solver.step()
    solver.step()
    worker = refiners(router)[0]
    state = worker.get_state()
    invalid = copy.deepcopy(state)
    del invalid["pool_task"]["jobs"]
    with pytest.raises(ValueError, match="missing its jobs"):
        worker.set_state(invalid)
    invalid = copy.deepcopy(state)
    invalid["pool_task"]["jobs"][0]["created_by"] = ["another_adapter"]
    with pytest.raises(ValueError, match="creator differs"):
        worker.set_state(invalid)


def test_shortage_does_not_silently_resample_with_replacement():
    solver, _, _ = build(n=6, take=20)
    solver.step()
    with pytest.raises(ValueError, match="requested 20"):
        solver.step()


def test_nested_creator_uses_full_instance_path():
    solver, producer, router = build(setup=False)
    outer = StrategyRouterAdapter(name="outer", roles=[RoleSpec("nested", router)],
        config=MultiStrategyConfig(total_batch_size=12, adapt_weights=False))
    solver.set_adapter(outer)
    solver.setup()
    path = adapter_path(outer, producer)
    assert path[0] == "outer" and "0:mixed" in path
    assert len(solver.solution_pool.projection_subpools(path)) == 6
    assert solver.step().committed
    assert solver.step().committed
    assert all(job["created_by"] == list(path) for w in refiners(router) for job in w._local["jobs"])


def test_standard_case_runs_refinement_and_return_with_pool_retention():
    from examples.cases.solution_pool.cases.moead_refinement.build_solver import build_solver
    solver = build_solver(dict(directions=8, view_count=4, workers=2, local_steps=2, max_steps=12))
    solver.run()
    router = solver.adapter
    assert all(w.task_status["status"] == "done" for w in refiners(router))
    assert router.units[0].adapter.task_status["status"] == "done"
    assert router.units[1].adapter.task_status["status"] == "done"
    producer = router.units[0].adapter.inner
    pool = solver.solution_pool
    assert len(pool.projection_subpools(adapter_path(router, producer))) == 8
    for name in pool.projection_subpools(adapter_path(router, producer)):
        assert pool.read(pool.subpool_refs(name)).numeric_matrix.shape == (1, 2)
