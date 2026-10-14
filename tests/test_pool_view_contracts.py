"""A view's meaning survives locator choice, nesting, rollback and restore."""
import copy

import numpy as np
import pytest

from blackbase.types import CandidateBatch, UnknownState
from nsgablack.adapters import (
    NSGA2Adapter, VNSAdapter, SimulatedAnnealingAdapter, PoolTaskSpec,
    RoleSpec, StrategyRouterAdapter, MultiStrategyConfig, subpools,
)
from nsgablack.adapters.subpools import adapter_path
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.core.state.pool_views import ObjectiveProjection
from nsgablack.representation import RepresentationPipeline
from tests.test_solution_pool import pool, batch


class Problem(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, objectives=["min", "min"], bounds=[(-20., 20.)])

    def evaluate(self, x):
        return [float(x[0] ** 2), float((x[0] - 10.) ** 2)]


class Operators:
    context_requires = ("vns_k", "temperature")

    def initialize(self, problem, context):
        return np.array([8.])

    def mutate(self, candidate, context):
        return candidate - 1.


def seed(solver):
    value = np.array([[8.]])
    return solver.solution_pool.put(CandidateBatch((UnknownState(value[0]),), value, ("seed",)), stage="initial")


def test_plain_views_have_stable_identity_revision_and_frozen_lineage():
    p = pool()
    refs = p.put(batch(), stage="accepted")
    p.create_subpool("source", refs)
    original = p.subpool_descriptor("source")
    p.publish_subpool_view("child", refs[:1], created_by=("search",), parent=original)
    p.add_to_subpool("source", refs)  # unchanged membership
    assert p.subpool_descriptor("source") == original
    p.add_to_subpool("source", p.put(batch((3.,), ("new",)), stage="accepted"))
    assert p.subpool_descriptor("source")["revision"] == original["revision"] + 1
    assert p.subpool_metadata("child")["parent"] == original
    assert p.children_subpools(original) == ("child",)
    restored = pool()
    restored.set_state(p.get_state())
    assert restored.subpool_descriptor("child") == p.subpool_descriptor("child")
    p.drop_subpool("source")
    assert p.subpool_refs("child") == refs[:1]


def test_result_view_and_plain_membership_are_hidden_until_commit():
    p = pool()
    refs = p.put(batch(), stage="accepted")
    baseline = p.snapshot_step_state()
    p.begin_attempt()
    p.create_subpool("collection", refs)
    p.publish_subpool_view("result", refs, created_by=("search",))
    assert p.subpool_refs("collection") == p.subpool_refs("result") == ()
    assert p.subpools_created_by(("search",)) == ()
    p.prepare_publication()
    p.commit_publication()
    assert p.subpool_refs("result") == refs
    assert p.subpools_created_by(("search",)) == ("result",)
    p.restore_step_state(baseline)
    assert not p.has_subpool("result")


@pytest.mark.parametrize("algorithm", [VNSAdapter, SimulatedAnnealingAdapter])
def test_named_projection_preserves_comparison_and_returns_selected_view(algorithm):
    refiner = algorithm(name="local", batch_size=1)
    router = StrategyRouterAdapter(name="named", roles=[RoleSpec("local", refiner,
        pool_task=PoolTaskSpec("direction", steps=2, output="results", shuffle=False))],
        config=MultiStrategyConfig(total_batch_size=2, adapt_weights=False))
    solver = ComposableSolver(Problem(), adapter=router,
        representation_pipeline=RepresentationPipeline(initializer=Operators(), mutator=Operators()))
    solver.setup()
    refs = seed(solver)
    projection = ObjectiveProjection("weighted_sum", (.8, .2))
    solver.solution_pool.publish_projection_subpool("named/direction", refs,
        created_by=("producer",), slot=7, projection=projection)
    assert solver.step().committed
    assert refiner.current_score == pytest.approx(52.)
    source = copy.deepcopy(router.units[0].adapter._local["jobs"])
    bad = router.units[0].adapter.get_state()
    del bad["pool_task"]["jobs"]
    with pytest.raises(ValueError, match="missing its jobs"):
        router.units[0].adapter.set_state(bad)
    bad["pool_task"]["uses_view_jobs"] = False
    with pytest.raises(ValueError, match="interpretation differs"):
        router.units[0].adapter.set_state(bad)
    assert solver.step().committed
    names = solver.solution_pool.subpools_created_by(adapter_path(router, refiner))
    assert len(names) == 1
    metadata = solver.solution_pool.subpool_metadata(names[0])
    assert metadata["projection"] == projection.as_dict()
    assert metadata["parent"] == source[0]["source_descriptor"]
    assert solver.solution_pool.read_raw_feedback(solver.solution_pool.subpool_refs(names[0]))[0].shape == (1, 2)


def test_named_projected_intake_cannot_bypass_projection_capability_check():
    consumer = NSGA2Adapter(population_size=2)
    router = StrategyRouterAdapter(name="bad", roles=[RoleSpec("consumer", consumer,
        pool_task=PoolTaskSpec("direction", mode="initialize"))])
    solver = ComposableSolver(Problem(), adapter=router)
    solver.setup()
    refs = seed(solver)
    solver.solution_pool.publish_projection_subpool("bad/direction", refs,
        created_by=("producer",), slot=0, projection=ObjectiveProjection("weighted_sum", (.8, .2)))
    with pytest.raises(ValueError, match="objective projections"):
        solver.step()
    assert solver.solution_pool.select() == ()


def test_plain_refinement_result_can_feed_another_algorithm_by_creator():
    coarse = VNSAdapter(name="coarse", batch_size=1, restart_on_stagnation=False)
    fine = SimulatedAnnealingAdapter(name="fine", batch_size=1)
    def phases(context):
        return "coarse" if context["pool_tasks"]["coarse:0"]["status"] != "done" else "fine"
    router = StrategyRouterAdapter(name="plain", roles=[
        RoleSpec("coarse", coarse, pool_task=PoolTaskSpec(steps=2, output="coarse_results")),
        RoleSpec("fine", fine, pool_task=PoolTaskSpec(subpools.all(coarse), steps=2, output="fine_results")),
    ], config=MultiStrategyConfig(total_batch_size=2, adapt_weights=False, phase_policy=phases,
                                 phase_roles={"coarse": ["coarse"], "fine": ["fine"]}))
    solver = ComposableSolver(Problem(), adapter=router,
        representation_pipeline=RepresentationPipeline(initializer=Operators(), mutator=Operators()))
    solver.setup()
    seed(solver)
    for _ in range(4):
        assert solver.step().committed
    names = solver.solution_pool.subpools_created_by(adapter_path(router, fine))
    assert len(names) == 1
    child = solver.solution_pool.subpool_metadata(names[0])
    assert child["kind"] == "candidate_view"
    assert "projection" not in child
    parent = solver.solution_pool.subpool_metadata(child["parent"]["name"])
    assert parent["created_by"] == list(adapter_path(router, coarse))


def test_legacy_views_without_identity_require_explicit_migration():
    p = pool()
    p.create_subpool("source")
    state = p.get_state()
    del state["subpool_metadata"]["source"]["view_id"]
    with pytest.raises(ValueError, match="identity"):
        pool().set_state(state)


def test_view_membership_cannot_restore_without_its_interpretation():
    p = pool()
    p.create_subpool("source")
    state = p.get_state()
    state["subpool_metadata"] = {}
    with pytest.raises(ValueError, match="missing its view identity"):
        pool().set_state(state)


def test_late_named_worker_uses_frozen_queue_after_source_drop():
    router = StrategyRouterAdapter(name="late", roles=[RoleSpec("local",
        lambda index: VNSAdapter(name=f"local_{index}", batch_size=1), n_units=2,
        pool_task=PoolTaskSpec("seeds", steps=2, shuffle=False))],
        config=MultiStrategyConfig(total_batch_size=1, adapt_weights=False))
    solver = ComposableSolver(Problem(), adapter=router,
        representation_pipeline=RepresentationPipeline(initializer=Operators(), mutator=Operators()))
    solver.setup()
    first = seed(solver)
    second = solver.solution_pool.put(CandidateBatch((UnknownState(np.array([6.])),),
        np.array([[6.]]), ("second",)), stage="initial")
    solver.solution_pool.create_subpool("late/seeds", (*first, *second))
    assert solver.step().committed
    assert router.units[1].adapter.task_status.get("request") is None
    solver.solution_pool.drop_subpool("late/seeds")
    router.units[0].enabled = False
    assert solver.step().committed
    assert router.units[1].adapter.inner.current_x[0] == 6.
