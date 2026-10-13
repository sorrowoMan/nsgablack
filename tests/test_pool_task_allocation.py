"""Pool input selection is separate from population membership and trajectories."""
import copy

import numpy as np
import pytest

from blackbase.types import CandidateBatch, UnknownState
from nsgablack.adapters import (
    NSGA2Adapter, PoolTaskSpec, RoleSpec, StrategyRouterAdapter,
    MultiStrategyConfig, VNSAdapter,
)
from nsgablack.core import ComposableSolver
from nsgablack.representation import RepresentationPipeline
from tests.test_subpool_tasks import Sphere, Operator


def make_solver(spec, *, workers=2, capacity=3, budget=None, vns=False):
    def factory(uid):
        if vns:
            return VNSAdapter(name=f"local_{uid}", batch_size=1, restart_on_stagnation=False)
        return NSGA2Adapter(name=f"ga_{uid}", population_size=capacity, offspring_size=1)
    router = StrategyRouterAdapter(name="allocation", roles=[
        RoleSpec("search", factory, n_units=workers, pool_task=spec),
    ], config=MultiStrategyConfig(total_batch_size=budget or workers * capacity, adapt_weights=False))
    solver = ComposableSolver(Sphere(), adapter=router,
        representation_pipeline=RepresentationPipeline(initializer=Operator(), mutator=Operator(1.)))
    solver.set_random_seed(17)
    solver.setup()
    return solver, router


def seeds(solver, n):
    # Same numeric value, distinct identities: sampling must not compare arrays.
    return solver.store_solutions(CandidateBatch.from_candidates(
        [UnknownState([10.], {"source_index": i}) for i in range(n)],
        candidate_tokens=tuple(f"seed:{i}" for i in range(n))))


def parents(solver, router):
    tokens = tuple(t for u in router.units for t in (u.adapter.inner.get_population_candidate_tokens() or ()))
    refs = solver.solution_pool.refs_for_tokens(tokens)
    records = {r["candidate_token"]: r for r in solver.solution_pool.read_provenance(refs, allow_pending=True)}
    return [tuple(records[t]["metadata"]["solution_source_ref"]["candidate_token"]
                  for t in u.adapter.inner.get_population_candidate_tokens()) for u in router.units]


def sources(solver):
    return [r["metadata"]["solution_source_ref"] for r in
            solver.solution_pool.read_provenance(solver.solution_pool.select())]


def test_300_candidates_seed_30_independent_populations_of_100():
    solver, router = make_solver(PoolTaskSpec(mode="initialize"), workers=30, capacity=100)
    original = seeds(solver, 300)
    assert solver.step().committed
    allocated = parents(solver, router)
    assert all(len(group) == len(set(group)) == 100 for group in allocated)
    assert len({tuple(group) for group in allocated}) == 30
    assert set().union(*map(set, allocated)) <= {r.candidate_token for r in original}
    assert sum(map(len, allocated)) == 3000
    assert len(set().union(*map(set, allocated))) <= 300
    assert len({id(u.adapter.inner.algorithm_unit) for u in router.units}) == 30
    # Ordinary search continues after intake, rather than allocating 3000 again.
    assert solver.step().committed
    assert len(solver.solution_pool.select()) == 3030
    assert all(u.adapter.task_status["status"] == "done" for u in router.units)


def test_partition_allocates_without_cross_worker_overlap():
    solver, router = make_solver(PoolTaskSpec(mode="initialize", distribution="partition"))
    seeds(solver, 6)
    assert solver.step().committed
    a, b = map(set, parents(solver, router))
    assert len(a) == len(b) == 3 and a.isdisjoint(b)


def test_explicit_subpool_restricts_input_and_shared_distribution_reuses_refs():
    spec = PoolTaskSpec("chosen", mode="initialize", distribution="shared", shuffle=False)
    solver, router = make_solver(spec)
    source = seeds(solver, 20)
    solver.solution_pool.create_subpool("allocation/chosen", source[10:13])
    assert solver.step().committed
    groups = parents(solver, router)
    assert groups[0] == groups[1] == tuple(r.candidate_token for r in source[10:13])
    assert set(router.units[0].adapter.inner.get_population_candidate_tokens()).isdisjoint(
        router.units[1].adapter.inner.get_population_candidate_tokens())


def test_missing_subpool_is_error_even_when_shortage_waits():
    solver, _ = make_solver(PoolTaskSpec("misspelled", mode="initialize", on_insufficient="wait"))
    seeds(solver, 20)
    with pytest.raises(ValueError, match="input subpool does not exist: allocation/misspelled"):
        solver.step()
    assert solver.evaluation_count == 0


def test_existing_empty_subpool_can_wait_and_later_receive_input():
    solver, router = make_solver(PoolTaskSpec("later", mode="initialize", on_insufficient="wait"))
    source = seeds(solver, 6)
    solver.solution_pool.create_subpool("allocation/later")
    assert not solver.step().committed
    solver.solution_pool.add_to_subpool("allocation/later", source)
    assert solver.step().committed
    assert all(len(group) == 3 for group in parents(solver, router))


@pytest.mark.parametrize("policy", ["error", "available"])
def test_insufficient_partition_does_not_duplicate_or_synthesize(policy):
    spec = PoolTaskSpec(mode="initialize", distribution="partition", on_insufficient=policy)
    solver, router = make_solver(spec)
    seeds(solver, 4)
    if policy == "error":
        with pytest.raises(ValueError, match="needs 6 distinct references; available=4"):
            solver.step()
        assert solver.evaluation_count == 0
    else:
        assert solver.step().committed
        groups = list(map(set, parents(solver, router)))
        assert len(groups[0]) == len(groups[1]) == 2
        assert groups[0].isdisjoint(groups[1])


@pytest.mark.parametrize("distribution,expected", [(None, 4), ("shared", 1)])
def test_vns_default_one_seed_per_instance_or_explicit_shared_seed(distribution, expected):
    solver, router = make_solver(PoolTaskSpec(distribution=distribution, steps=1), workers=4, vns=True)
    seeds(solver, 20)
    assert solver.step().committed
    selected = [r["candidate_token"] for r in sources(solver)]
    assert len(selected) == 4 and len(set(selected)) == expected
    assert all(u.adapter.task_status["count"] == 1 for u in router.units)


def each_dispatch(control, context):
    return str(context["task"]["step"])


def test_checkpoint_preserves_random_allocation_for_next_request():
    from nsgablack.plugins import CheckpointResumePlugin
    spec = PoolTaskSpec("fixed", steps=1, request_key=each_dispatch)
    source, first = make_solver(spec, workers=2, vns=True)
    refs = seeds(source, 20)
    source.solution_pool.create_subpool("allocation/fixed", refs)
    source.step()
    target, second = make_solver(spec, workers=2, vns=True)
    writer, reader = CheckpointResumePlugin(), CheckpointResumePlugin()
    writer.attach(source)
    reader.attach(target)
    reader._restore_payload(solver=target, payload=writer._build_payload(solver=source, reason="allocation"))
    assert source.step().committed and target.step().committed
    a, b = sources(source), sources(target)
    assert a == b


def test_failed_update_rolls_back_sampling_rng_and_assignment():
    solver, router = make_solver(PoolTaskSpec(mode="initialize"))
    seeds(solver, 20)
    worker = router.units[0].adapter
    before = copy.deepcopy(worker._rng_state())
    child = router.units[1].adapter.inner
    update = child.update
    attempted = []
    def fail(*args, **kwargs):
        attempted.append(parents(solver, router)[0])
        raise RuntimeError("allocation update failure")
    child.update = fail
    with pytest.raises(RuntimeError, match="allocation update failure"):
        solver.step()
    assert worker._rng_state() == before
    child.update = update
    assert solver.step().committed
    assert parents(solver, router)[0] == attempted[0]


def test_role_factory_with_different_default_counts_requires_explicit_plan():
    router = StrategyRouterAdapter(roles=[RoleSpec("mixed", lambda uid: NSGA2Adapter(population_size=uid+2),
        n_units=2, pool_task=PoolTaskSpec(mode="initialize"))])
    with pytest.raises(ValueError, match="equal intake counts"):
        router.step_transaction_children()


def test_nested_same_named_tasks_own_separate_sampling_streams():
    def inner():
        return StrategyRouterAdapter(name="inner", roles=[
            RoleSpec("local", VNSAdapter(), pool_task=PoolTaskSpec()),
        ])
    left, right = inner(), inner()
    outer = StrategyRouterAdapter(roles=[RoleSpec("a", left), RoleSpec("b", right)])
    solver = ComposableSolver(Sphere(), adapter=outer,
        representation_pipeline=RepresentationPipeline(initializer=Operator(), mutator=Operator()))
    solver.set_random_seed(17)
    solver.setup()
    a, b = left.units[0].adapter, right.units[0].adapter
    before = b.snapshot_step_state()["pool_task_rng"]
    a._rng.random(10)
    assert b.snapshot_step_state()["pool_task_rng"] == before
    assert a.get_state()["pool_task_rng"] != b.get_state()["pool_task_rng"]


@pytest.mark.parametrize("algorithm", ["vns", "sa"])
@pytest.mark.parametrize("mode", ["initialize", "refine"])
def test_trajectory_source_and_mutation_parent_survive_checkpoint(algorithm, mode):
    from nsgablack.adapters import SimulatedAnnealingAdapter
    from nsgablack.plugins import CheckpointResumePlugin
    def build():
        def factory(uid):
            if algorithm == "vns":
                return VNSAdapter(name=f"vns_{uid}", batch_size=1, restart_on_stagnation=False)
            return SimulatedAnnealingAdapter(name=f"sa_{uid}", batch_size=1, random_seed=uid)
        router = StrategyRouterAdapter(name="lineage", roles=[
            RoleSpec("local", factory, n_units=2,
                     pool_task=PoolTaskSpec(mode=mode, steps=3, shuffle=False, distribution="partition")),
        ], config=MultiStrategyConfig(total_batch_size=2, adapt_weights=False))
        solver = ComposableSolver(Sphere(), adapter=router,
            representation_pipeline=RepresentationPipeline(initializer=Operator(), mutator=Operator(1.)))
        solver.setup()
        return solver
    source = build()
    initial = seeds(source, 2)
    assert source.step().committed
    baseline = source.solution_pool.select()
    records = source.solution_pool.read_provenance(baseline)
    assert [r["parent_token"] for r in records] == [r.candidate_token for r in initial]
    target = build()
    writer, reader = CheckpointResumePlugin(), CheckpointResumePlugin()
    writer.cfg.strict = reader.cfg.strict = True
    writer.attach(source)
    reader.attach(target)
    reader._restore_payload(solver=target, payload=writer._build_payload(solver=source, reason="lineage"))
    assert target.step().committed
    all_refs = target.solution_pool.select()
    neighbors = tuple(ref for ref in all_refs if ref not in baseline)
    records = target.solution_pool.read_provenance(neighbors)
    assert [r["parent_token"] for r in records] == [r.candidate_token for r in baseline]
    assert [r["metadata"]["solution_source_ref"] for r in records] == [r.as_dict() for r in initial]
    batch = target.read_solutions(neighbors)
    assert [s.metadata["source_index"] for s in batch.semantic_states] == [0, 1]
    np.testing.assert_array_equal(batch.numeric_matrix, [[9.], [9.]])


def test_checkpoint_cannot_silently_skip_changed_task_configuration():
    from nsgablack.plugins import CheckpointResumePlugin
    source, _ = make_solver(PoolTaskSpec(mode="initialize", count=2))
    seeds(source, 10)
    source.step()
    target, _ = make_solver(PoolTaskSpec(mode="initialize", count=3))
    writer, reader = CheckpointResumePlugin(), CheckpointResumePlugin()
    writer.attach(source)
    reader.attach(target)
    with pytest.raises(ValueError, match="pool task checkpoint configuration mismatch"):
        reader._restore_payload(solver=target, payload=writer._build_payload(solver=source, reason="config"))


def two_phases(context):
    return "start" if context["step"] == 0 else "search"


def test_initialization_is_not_repeated_after_phase_change():
    solver, router = make_solver(PoolTaskSpec(mode="initialize"))
    router.cfg.phase_policy = two_phases
    seeds(solver, 20)
    solver.step()
    assert all(u.adapter.task_status["request"] == "start" for u in router.units)
    assert solver.step().committed
    assert router._current_phase_name == "search"
    assert all(u.adapter.task_status["request"] == "start" for u in router.units)
    assert len(solver.solution_pool.select()) == 8  # Six intake rows, two ordinary offspring.


def test_small_dispatch_budget_consumes_the_same_initial_allocation_in_chunks():
    solver, router = make_solver(PoolTaskSpec(mode="initialize", distribution="partition", shuffle=False), budget=2)
    source = seeds(solver, 6)
    for size in range(1, 4):
        assert solver.step().committed
        assert all(len(group) == size for group in parents(solver, router))
    allocated = parents(solver, router)
    assert set().union(*map(set, allocated)) == {ref.candidate_token for ref in source}
    assert set(allocated[0]).isdisjoint(allocated[1])
    assert all(u.adapter.task_status["status"] == "done" for u in router.units)


def test_new_request_waits_without_running_previous_completed_search():
    spec = PoolTaskSpec("input", mode="initialize", request_key=each_dispatch, on_insufficient="wait")
    solver, router = make_solver(spec)
    solver.solution_pool.create_subpool("allocation/input", seeds(solver, 6))
    assert solver.step().committed
    solver.solution_pool.drop_subpool("allocation/input")
    solver.solution_pool.create_subpool("allocation/input")
    evaluated = solver.evaluation_count
    assert not solver.step().committed
    assert solver.evaluation_count == evaluated
    assert all(u.adapter.task_status["status"] != "done" for u in router.units)
