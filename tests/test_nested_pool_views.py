"""Nested views preserve frozen lineage without copying or pinning parent data."""
import copy

import pytest

from nsgablack.core.state.pool_retention import PoolRetentionPolicy
from nsgablack.core.state.pool_views import ObjectiveProjection
from nsgablack.core.state.solution_pool import SolutionPool
from tests.test_solution_pool import batch, pool
from tests.test_solution_pool_retention import commit_retention


PROJECTION = ObjectiveProjection("weighted_sum", (.8, .2))


def publish(p, name, refs, *, parent=None, projection=PROJECTION):
    p.publish_projection_subpool(name, refs, created_by=("router", name), slot=0,
                                 projection=projection, parent=parent)


def hierarchy():
    p = pool()
    refs = p.put(batch(), stage="accepted")
    publish(p, "direction", refs)
    root = p.subpool_descriptor("direction")
    publish(p, "coarse", refs[:1], parent=root)
    middle = p.subpool_descriptor("coarse")
    publish(p, "fine", refs[:1], parent=middle)
    return p, refs, root, middle


def test_nested_views_share_candidate_snapshots_and_detach_descriptors():
    p, refs, root, middle = hierarchy()
    assert p.record_count == 1
    assert p.subpool_refs("coarse") == p.subpool_refs("fine") == refs[:1]
    assert p.children_subpools("direction") == ("coarse",)
    assert p.children_subpools(root, recursive=True) == ("coarse", "fine")
    assert p.children_subpools("coarse") == ("fine",)
    fine = p.subpool_descriptor("fine")
    assert [a["view_id"] for a in fine["ancestors"]] == [root["view_id"], middle["view_id"]]
    fine["ancestors"][0]["name"] = "changed"
    assert p.subpool_descriptor("fine")["ancestors"][0]["name"] == "direction"
    assert len(p.get_state()["payloads"]) == 1


def test_revisions_change_only_for_membership_or_effective_projection():
    p, refs, root, _ = hierarchy()
    publish(p, "direction", refs)
    assert p.subpool_descriptor("direction") == root
    publish(p, "direction", refs[:1])
    changed = p.subpool_descriptor("direction")
    assert changed["view_id"] == root["view_id"]
    assert changed["revision"] == root["revision"] + 1
    publish(p, "direction", refs[:1], projection=ObjectiveProjection("weighted_sum", (.2, .8)))
    assert p.subpool_descriptor("direction")["revision"] == changed["revision"] + 1
    assert p.subpool_metadata("coarse")["projection"] == PROJECTION.as_dict()
    assert p.subpool_metadata("coarse")["parent"] == root
    with pytest.raises(ValueError, match="parent is immutable"):
        publish(p, "coarse", refs[:1], parent=p.subpool_descriptor("direction"))


def test_staged_view_hides_previously_published_members_and_rolls_back():
    p, refs, root, _ = hierarchy()
    baseline = p.snapshot_step_state()
    p.begin_attempt()
    publish(p, "new-child", refs, parent=root)
    assert p.subpool_refs("new-child") == ()
    assert "new-child" not in p.children_subpools(root)
    with pytest.raises(ValueError, match="committed"):
        p.subpool_descriptor("new-child")
    publish(p, "direction", refs[:1])
    assert p.subpool_refs("direction") == ()
    p.restore_step_state(baseline)
    assert not p.has_subpool("new-child")
    assert p.subpool_descriptor("direction") == root
    assert p.subpool_refs("direction") == refs


def test_publication_commits_lineage_and_membership_together():
    p = pool()
    refs = p.put(batch(), stage="accepted")
    publish(p, "parent", refs)
    parent = p.subpool_descriptor("parent")
    p.begin_attempt()
    child_refs = p.put(batch((9.,), ("child",)), stage="accepted")
    publish(p, "child", child_refs, parent=parent)
    manifest = p.prepare_publication()
    assert p.children_subpools(parent) == ()
    assert p.subpool_refs("child") == ()
    p.commit_publication()
    assert p.children_subpools(parent) == ("child",)
    assert p.subpool_refs("child") == child_refs
    restored = SolutionPool(p.snapshots)
    restored.restore_publication(manifest)
    assert restored.subpool_descriptor("child") == p.subpool_descriptor("child")
    assert restored.subpool_refs("child") == child_refs


def test_historical_parent_can_advance_drop_and_reuse_name_without_rebinding():
    p, refs, root, _ = hierarchy()
    publish(p, "direction", refs[1:])
    publish(p, "late", refs[:1], parent=root)
    p.drop_subpool("direction")
    publish(p, "after-drop", refs[:1], parent=root)
    assert p.children_subpools(root) == ("coarse", "late", "after-drop")
    publish(p, "direction", refs[1:])
    new_root = p.subpool_descriptor("direction")
    assert new_root["view_id"] != root["view_id"]
    assert p.children_subpools("direction") == ()
    assert p.children_subpools(root, recursive=True) == ("coarse", "fine", "late", "after-drop")


def test_dropped_ancestor_candidates_are_collectable_but_child_candidates_survive():
    p = pool()
    p.set_retention_policy(PoolRetentionPolicy(idle_steps=1, retained_publications=1))
    source = p.put(batch((1.,), ("source",)), stage="accepted")
    result = p.put(batch((2.,), ("result",)), stage="accepted")
    publish(p, "parent", source)
    parent = p.subpool_descriptor("parent")
    publish(p, "child", result, parent=parent)
    p.drop_subpool("parent")
    commit_retention(p)
    assert p.children_subpools(parent) == ("child",)
    assert p.subpool_refs("child") == result
    with pytest.raises(ValueError, match="unavailable"):
        p.read(source)
    assert p.record_count == 1
    p.drop_subpool("child")
    commit_retention(p)
    assert p.record_count == 0


def test_portable_checkpoint_preserves_children_after_parent_drop():
    p, refs, root, _ = hierarchy()
    p.drop_subpool("direction")
    restored = pool()
    restored.set_state(p.get_state())
    assert restored.children_subpools(root, recursive=True) == ("coarse", "fine")
    assert restored.subpool_descriptor("fine") == p.subpool_descriptor("fine")
    assert restored.subpool_refs("fine") == refs[:1]


@pytest.mark.parametrize("corruption", ["cross_pool", "cycle", "duplicate_id", "future_revision", "wrong_name", "wrong_ancestry"])
def test_malformed_checkpoint_lineage_is_rejected_atomically(corruption):
    p, _, _, _ = hierarchy()
    original = p.get_state()
    bad = copy.deepcopy(original)
    views = bad["subpool_metadata"]
    if corruption == "cross_pool":
        views["coarse"]["parent"]["pool_id"] = "another-pool"
    elif corruption == "cycle":
        views["coarse"]["parent"]["view_id"] = views["coarse"]["view_id"]
    elif corruption == "duplicate_id":
        views["coarse"]["view_id"] = views["direction"]["view_id"]
    elif corruption == "future_revision":
        views["coarse"]["parent"]["revision"] += 1
    elif corruption == "wrong_name":
        views["coarse"]["parent"]["name"] = "forged"
    else:
        views["fine"]["parent"]["ancestors"] = []
    with pytest.raises(ValueError, match="subpool"):
        p.set_state(bad)
    assert p.get_state()["subpool_metadata"] == original["subpool_metadata"]
    assert p.get_state()["retention"]["owners"] == original["retention"]["owners"]


def test_zero_admission_retains_input_queues_but_never_new_projected_outputs():
    p = pool()
    refs = p.put(batch(), stage="accepted")
    publish(p, "parent", refs)
    baseline = p.snapshot_step_state()
    p.begin_attempt()
    p.create_subpool("queue", refs)
    publish(p, "child", refs, parent=p.subpool_descriptor("parent"))
    p.reject_attempt(baseline)
    assert p.subpool_refs("queue") == refs
    assert not p.has_subpool("child")
    assert p.children_subpools("parent") == ()


def test_append_to_projected_view_uses_transactional_revision():
    p = pool()
    refs = p.put(batch(), stage="accepted")
    publish(p, "direction", refs[:1])
    before = p.subpool_descriptor("direction")
    p.add_to_subpool("direction", refs[:1])
    assert p.subpool_descriptor("direction") == before
    p.begin_attempt()
    p.add_to_subpool("direction", refs[1:])
    assert p.subpool_refs("direction") == ()
    p.prepare_publication()
    p.commit_publication()
    assert p.subpool_refs("direction") == refs
    assert p.subpool_descriptor("direction")["revision"] == before["revision"] + 1


def test_descriptor_validation_is_available_without_live_pool():
    p, _, root, _ = hierarchy()
    detached = SolutionPool.validate_subpool_descriptor(root, pool_id=p.pool_id)
    assert detached == root and detached is not root
    with pytest.raises(ValueError, match="another pool"):
        SolutionPool.validate_subpool_descriptor(root, pool_id="other")
    with pytest.raises(ValueError, match="identity"):
        SolutionPool.validate_subpool_descriptor({**root, "revision": True})


def test_generic_create_cannot_publish_projection_metadata_during_attempt():
    p, refs, _, _ = hierarchy()
    metadata = p.subpool_metadata("direction")
    metadata["view_id"] = "forged-published-view"
    p.begin_attempt()
    with pytest.raises(ValueError, match="publish_projection_subpool"):
        p.create_subpool("bypass", refs, metadata=metadata)
    assert not p.has_subpool("bypass")


def test_generic_retention_writers_cannot_bypass_subpool_revisions():
    p, refs, root, _ = hierarchy()
    for owner in ("subpool/direction", "subpool/unpublished"):
        with pytest.raises(ValueError, match="dedicated subpool APIs"):
            p.retain(owner, refs[1:])
    for prefix, values in (("subpool/", {"subpool/direction": refs[1:]}),
                           ("subpool/direction", {}), ("subpool/", {}), ("s", {})):
        with pytest.raises(ValueError, match="dedicated subpool APIs"):
            p.replace_roots(prefix, values)
    assert p.subpool_descriptor("direction") == root
    assert p.subpool_refs("direction") == refs
    assert not p.has_subpool("unpublished")


def test_dedicated_plain_subpool_writers_and_generic_consumer_roots_still_work():
    p = pool()
    refs = p.put(batch(), stage="accepted")
    p.create_subpool("ordinary", refs[:1])
    p.add_to_subpool("ordinary", refs[1:])
    assert p.subpool_refs("ordinary") == refs
    p.retain("consumer", refs)
    p.replace_roots("consumer", {"consumer": refs[1:]})
    assert p.get_state()["retention"]["owners"]["consumer"] == [refs[1].as_dict()]
    p.release("subpool/ordinary")
    assert not p.has_subpool("ordinary")

