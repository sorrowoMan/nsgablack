"""Collection maintenance plans are detached, scoped and side-effect free."""
import pytest
from blackbase.context import create_snapshot_store
from blackbase.types import CandidateBatch

from nsgablack.adapters import ChangeResult, PoolEdit, PoolOutput
from nsgablack.adapters.change_pool import ChangePool
from nsgablack.core.state.pool_views import ObjectiveProjection
from nsgablack.core.state.solution_pool import SolutionPool


def prepared():
    pool = SolutionPool(create_snapshot_store(backend="memory"), run_id="pool-edit-plans")
    refs = pool.put(CandidateBatch.from_candidates([[1.], [2.], [3.]],
        candidate_tokens=("first", "second", "third")), stage="accepted")
    pool.create_subpool("elite", refs[:2])
    return pool, refs


def test_helpers_only_plan_and_keep_the_frozen_expected_identity():
    pool, refs = prepared()
    before = pool.subpool_descriptor("elite")
    scope = ChangePool(pool)
    plans = (
        scope.replace_members("elite", (refs[2], refs[2])),
        scope.update_members("elite", add=(refs[2],), remove=refs[:1]),
        scope.remove_members("elite", refs[:1]),
        scope.trim_members("elite", 0),
    )
    assert [plan.members for plan in plans] == [(refs[2], refs[2]), refs[1:], refs[1:2], ()]
    assert all(plan.as_dict()["expected"] == before for plan in plans)
    assert pool.subpool_refs("elite") == refs[:2]
    assert pool.subpool_descriptor("elite") == before
    with pytest.raises(ValueError, match="not a collection member"):
        scope.remove_members("elite", refs[2:])
    with pytest.raises(ValueError, match="overlap"):
        scope.update_members("elite", add=refs[:1], remove=refs[:1])
    assert pool.subpool_descriptor("elite") == before


def test_noop_trim_and_removal_plans_preserve_repeated_coordinates():
    pool, refs = prepared()
    repeated = (refs[0], refs[0], refs[1], refs[2], refs[2])
    pool.create_subpool("queue", repeated)
    scope = ChangePool(pool)
    assert scope.trim_members("queue", 10).members == repeated
    assert scope.trim_members("queue", 4).members == repeated[:4]
    assert scope.update_members("queue").members == repeated
    assert scope.remove_members("queue", refs[1:2]).members == (refs[0], refs[0], refs[2], refs[2])
    assert scope.update_members("queue", add=(refs[0], refs[0])).members == repeated


def test_describe_uses_frozen_metadata_without_loading_candidates(monkeypatch):
    pool, refs = prepared()
    scope = ChangePool(pool)

    def no_candidate_reads(*args, **kwargs):
        pytest.fail("describing a collection must not read candidate values")

    monkeypatch.setattr(pool, "read", no_candidate_reads)
    description = scope.describe("elite")
    pool.add_to_subpool("elite", refs[2:])
    assert description["members"] == scope.describe("elite")["members"] == 2
    assert description["descriptor"]["revision"] < pool.subpool_descriptor("elite")["revision"]
    assert scope.describe()["subpools"] == ("elite",)
    assert scope.used_refs == ()
    with pytest.raises(TypeError):
        description["descriptor"]["revision"] = 999


def test_edits_cannot_bypass_source_permissions_or_write_algorithm_views():
    pool, refs = prepared()
    restricted = ChangePool(pool, allowed_refs=refs[:1], allow_main=False)
    with pytest.raises(ValueError, match="declared inputs"):
        restricted.trim_members("elite", 1)
    scope = ChangePool(pool, allowed_refs=(), allowed_subpools=("elite",), allow_main=False)
    with pytest.raises(ValueError, match="declared inputs"):
        scope.update_members("elite", add=refs[2:])
    scope.close()
    with pytest.raises(RuntimeError, match="ended"):
        scope.describe()
    with pytest.raises(RuntimeError, match="ended"):
        scope.trim_members("elite", 1)
    pool.publish_projection_subpool("direction", refs[:1], created_by=("moead",),
        slot=0, projection=ObjectiveProjection("weighted_sum", (1.,)))
    with pytest.raises(ValueError, match="ordinary"):
        ChangePool(pool).replace_members("direction", refs[:1])


def test_plan_is_detached_wire_data_and_conflicting_updates_are_rejected():
    pool, refs = prepared()
    scope = ChangePool(pool)
    first = scope.replace_members("elite", refs[:1])
    second = scope.replace_members("elite", refs[1:2])
    data = first.as_dict()
    data["expected"]["revision"] = 999
    data["members"].clear()
    scope.close()
    assert first.as_dict()["expected"]["revision"] == 1
    assert first.members == refs[:1]
    assert ChangeResult([0.], edits=(first, first)).edits == (first,)
    with pytest.raises(ValueError, match="conflicting"):
        ChangeResult([0.], edits=(first, second))
    with pytest.raises(ValueError, match="append and replace"):
        ChangeResult([0.], outputs=(PoolOutput("elite"),), edits=(first,))
    with pytest.raises(TypeError, match="PoolEdit"):
        ChangeResult([0.], edits=("elite",))
    with pytest.raises(ValueError, match="another collection"):
        PoolEdit("other", refs[:1], expected=first.expected)
    other, other_refs = prepared()
    with pytest.raises(ValueError, match="another pool"):
        PoolEdit("elite", other_refs[:1], expected=first.expected)
