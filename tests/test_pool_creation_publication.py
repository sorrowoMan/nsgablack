import pytest
from nsgablack.adapters import NSGA2Adapter, subpools
from nsgablack.adapters.subpools import adapter_path
from nsgablack.plugins import CheckpointResumePlugin, CheckpointResumeConfig
from tests.test_solution_pool import pool, batch
from tests.test_pool_final_members_maintenance import archive_final_members, MaintenanceSphere
from nsgablack.core import ComposableSolver


@pytest.mark.parametrize("stage", ["mutation", "proposal", "repair"])
def test_outside_attempt_drafts_need_explicit_publication(stage):
    p = pool()
    refs = p.put(batch(), stage=stage)
    assert p.select(stage=None) == ()
    with pytest.raises(ValueError, match="uncommitted"):
        p.read(refs)
    assert p.read(refs, allow_pending=True).candidate_tokens == ("a", "b")
    restored = pool()
    restored.set_state(p.get_state())
    assert restored.select(stage=None) == ()
    published = p.put(batch(), stage=stage, publish=True)
    assert p.select(stage=None) == published


def test_active_attempt_cannot_force_publication():
    p = pool()
    p.begin_attempt()
    with pytest.raises(ValueError, match="before commit"):
        p.put(batch(), stage="accepted", publish=True)
    assert p.record_count == 0


def test_collection_creator_is_explicit_and_selection_kind_preserves_defaults():
    p = pool()
    refs = p.put(batch())
    p.create_subpool("unowned", refs)
    p.create_subpool("elite", refs, created_by=("ga",))
    assert p.subpools_created_by(("ga",)) == ()
    assert p.subpools_created_by(("ga",), kind="candidate_collection") == ("elite",)
    with pytest.raises(TypeError, match="segments"):
        p.create_subpool("bad", created_by="ga")
    clone = pool()
    clone.set_state(p.get_state())
    assert clone.subpool_metadata("elite")["created_by"] == ["ga"]
    assert clone.subpool_metadata("unowned")["created_by"] is None


def test_real_maintenance_records_creator_and_keeps_it_after_checkpoint(tmp_path, monkeypatch):
    monkeypatch.setenv("NSGABLACK_CHECKPOINT_HMAC_KEY", "pool-creator-test")
    def make():
        ga = NSGA2Adapter(name="ga", population_size=4, offspring_size=4)
        ga.set_pool_maintenance(archive_final_members)
        return ComposableSolver(MaintenanceSphere(), adapter=ga)
    solver, other = make(), make()
    config = CheckpointResumeConfig(checkpoint_dir=str(tmp_path), save_on_finish=False, strict=True)
    writer, reader = CheckpointResumePlugin(config=config), CheckpointResumePlugin(config=config)
    solver.add_plugin(writer)
    other.add_plugin(reader)
    solver.setup()
    try:
        assert solver.step().committed and solver.step().committed
        path = adapter_path(solver.adapter, solver.adapter)
        assert solver.solution_pool.subpool_metadata("archive")["created_by"] == list(path)
        assert all(solver.solution_pool.subpool_metadata(name)["kind"] != "candidate_collection"
                   for name in solver.solution_pool.subpools_created_by(path))
        assert set(solver.solution_pool.subpools_created_by(path, kind="candidate_collection")) == {"archive", "empty"}
        checkpoint = writer.save_checkpoint(reason="pool-creator")
        assert reader.resume(str(checkpoint))
        other.run(max_steps=1)
        assert other.solution_pool.subpool_metadata("archive")["created_by"] == list(path)
        assert subpools.all(solver.adapter, kind="candidate_collection").identity()["kind"] == "candidate_collection"
    finally:
        solver.teardown()


def test_collection_selector_drives_real_ga_to_vns_tasks():
    from blackbase.orchestration import ExecutionPlan
    from nsgablack.adapters import (SearchPlanAdapter, StrategySpec, PoolTaskSpec,
                                   MultiStrategyConfig, VNSAdapter)
    ga = NSGA2Adapter(name="ga", population_size=4, offspring_size=4)
    ga.set_pool_maintenance(archive_final_members)
    vns = VNSAdapter(name="vns")
    plan = SearchPlanAdapter(
        ExecutionPlan.serial(ExecutionPlan.leaf("ga", steps=2), ExecutionPlan.leaf("vns")),
        strategies=[StrategySpec(ga, "ga"), StrategySpec(vns, "vns", pool_task=PoolTaskSpec(
            subpools.all(ga, kind="candidate_collection"), count="all", steps=2,
            shuffle=False, on_insufficient="available"))],
        config=MultiStrategyConfig(total_batch_size=4, adapt_weights=False))
    from nsgablack.representation import RepresentationPipeline, ContextGaussianMutation
    solver = ComposableSolver(MaintenanceSphere(), adapter=plan,
        representation_pipeline=RepresentationPipeline(mutator=ContextGaussianMutation(base_sigma=0.1)))
    assert solver.run(max_steps=6)["status"] == "ok"
    assert plan.cursor.completed
    results = plan.get_pool_task_results(solver, "vns")
    assert len(results) == 2
    assert solver.solution_pool.subpool_metadata("archive")["created_by"] == list(adapter_path(plan, ga))
