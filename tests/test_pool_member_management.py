"""Ordinary reference collections keep identity while membership changes."""
from dataclasses import replace

import pytest

from nsgablack.core.state.pool_views import ObjectiveProjection
from tests.test_solution_pool import batch, pool
from tests.test_solution_pool_retention import commit_retention, make_pool


def collection():
    value = pool()
    refs = value.put(batch((1., 1., 3., 4.), ("a", "b", "c", "d")), stage="accepted")
    value.create_subpool("elite", refs[:2])
    return value, refs


def test_explicit_member_replacement_preserves_exact_ordered_coordinates():
    p, refs = collection()
    p.create_subpool("duplicates", (refs[0], refs[0], refs[1]))
    # Existing creation also serves ordered task queues. Repeated references
    # can represent different direction jobs and must retain their positions.
    assert p.subpool_refs("duplicates") == (refs[0], refs[0], refs[1])
    assert p.replace_subpool_members("duplicates", (refs[0], refs[0], refs[1])) == (refs[0], refs[0], refs[1])
    descriptor = p.subpool_descriptor("elite")
    result = p.replace_subpool_members("elite", (refs[2], refs[1], refs[2]), expected=descriptor)
    assert result == p.subpool_refs("elite") == (refs[2], refs[1], refs[2])
    after = p.subpool_descriptor("elite")
    assert after == dict(descriptor, revision=descriptor["revision"] + 1)
    # Equal numeric values have distinct identities. A new version of one token
    # is also a distinct member, even though both its value and token are equal.
    newer = p.put(batch((1.,), ("a",)), stage="accepted")
    p.replace_subpool_members("elite", (refs[0], refs[1], newer[0]))
    assert p.subpool_refs("elite") == (refs[0], refs[1], newer[0])
    assert p.read((refs[0], newer[0])).candidate_tokens == ("a", "a")


def test_atomic_update_preserves_survivor_order_then_appends_new_members():
    p, refs = collection()
    result = p.update_subpool_members("elite", add=(refs[3], refs[1], refs[2], refs[3]),
                                     remove=(refs[0], refs[0]))
    assert result == (refs[1], refs[3], refs[2])
    assert p.remove_from_subpool("elite", (refs[3],)) == (refs[1], refs[2])
    assert p.trim_subpool("elite", 1) == refs[1:2]
    assert p.trim_subpool("elite", 0) == ()
    assert p.has_subpool("elite")


def test_invalid_batch_does_not_partly_modify_collection_or_revision():
    p, refs = collection()
    before = p.subpool_descriptor("elite")
    for invoke, message in (
        (lambda: p.update_subpool_members("elite", add=refs[2:], remove=refs[3:]), "overlap"),
        (lambda: p.update_subpool_members("elite", add=refs[2:3], remove=refs[3:]), "not a subpool member"),
        (lambda: p.replace_subpool_members("elite", (refs[2], replace(refs[3], candidate_token="wrong"))), "token"),
        (lambda: p.remove_from_subpool("elite", refs[2:3]), "not a subpool member"),
    ):
        with pytest.raises(ValueError, match=message):
            invoke()
        assert p.subpool_refs("elite") == refs[:2]
        assert p.subpool_descriptor("elite") == before


def test_descriptor_rejects_stale_revision_wrong_pool_and_same_name_recreation():
    p, refs = collection()
    old = p.subpool_descriptor("elite")
    p.replace_subpool_members("elite", refs[1:3], expected=old)
    with pytest.raises(ValueError, match="stale"):
        p.trim_subpool("elite", 1, expected=old)
    fresh = p.subpool_descriptor("elite")
    with pytest.raises(ValueError, match="another pool"):
        p.replace_subpool_members("elite", (), expected=dict(fresh, pool_id="other"))
    with pytest.raises(ValueError, match="descriptor"):
        p.replace_subpool_members("elite", (), expected={k: v for k, v in fresh.items() if k != "ancestors"})
    p.drop_subpool("elite")
    p.create_subpool("elite", refs[1:3])
    with pytest.raises(ValueError, match="stale"):
        p.remove_from_subpool("elite", refs[1:2], expected=fresh)
    assert p.subpool_refs("elite") == refs[1:3]
    assert p.subpool_descriptor("elite")["view_id"] != fresh["view_id"]


def test_no_op_writes_keep_revision_and_publication():
    p, refs = collection()
    before = p.subpool_descriptor("elite")
    p.begin_attempt()
    assert p.replace_subpool_members("elite", refs[:2], expected=before) == refs[:2]
    assert p.update_subpool_members("elite", add=refs[:1], expected=before) == refs[:2]
    assert p.remove_from_subpool("elite", (), expected=before) == refs[:2]
    assert p.trim_subpool("elite", 100, expected=before) == refs[:2]
    assert p.subpool_descriptor("elite") == before
    assert p.subpool_refs("elite") == refs[:2]


def test_updates_and_trim_preserve_existing_repeated_coordinates():
    p, refs = collection()
    repeated = (refs[0], refs[0], refs[1], refs[2], refs[0])
    p.replace_subpool_members("elite", repeated)
    descriptor = p.subpool_descriptor("elite")
    assert p.update_subpool_members("elite", expected=descriptor) == repeated
    assert p.update_subpool_members("elite", add=(refs[0], refs[0]), expected=descriptor) == repeated
    assert p.subpool_descriptor("elite") == descriptor
    # Adding an existing coordinate and deleting another ref cannot collapse
    # the positions already representing separate direction jobs.
    updated = p.update_subpool_members("elite", add=(refs[0], refs[3], refs[3]), remove=(refs[1],))
    assert updated == (refs[0], refs[0], refs[2], refs[0], refs[3])
    p.add_to_subpool("elite", (refs[0], refs[1], refs[1]))
    assert p.subpool_refs("elite") == (*updated, refs[1])
    assert p.trim_subpool("elite", 4) == updated[:4]
    assert p.remove_from_subpool("elite", (refs[0],)) == (refs[2],)


def test_accepted_rows_stage_membership_but_private_drafts_never_enter_collection():
    p, refs = collection()
    descriptor = p.subpool_descriptor("elite")
    p.begin_attempt()
    draft = p.put(batch((5.,), ("draft",)), stage="mutation")
    accepted = p.put(batch((6.,), ("accepted",)), stage="accepted")
    with pytest.raises(ValueError, match="published or accepted"):
        p.update_subpool_members("elite", add=(*accepted, *draft), expected=descriptor)
    assert p.subpool_refs("elite") == refs[:2]
    assert p.subpool_descriptor("elite") == descriptor
    result = p.update_subpool_members("elite", add=accepted, expected=descriptor)
    assert result == (*refs[:2], *accepted)
    assert p.subpool_refs("elite") == ()
    assert "elite" not in p.published_subpool_names()
    with pytest.raises(ValueError, match="committed"):
        p.subpool_descriptor("elite")
    p.prepare_publication()
    p.commit_publication()
    assert p.subpool_refs("elite") == result
    assert p.subpool_descriptor("elite") == dict(descriptor, revision=descriptor["revision"] + 1)


@pytest.mark.parametrize("kind", ["candidate_view", "objective_projection"])
def test_general_membership_methods_reject_algorithm_owned_views(kind):
    p, refs = collection()
    if kind == "candidate_view":
        p.publish_subpool_view("owned", refs[:2], created_by=("ga",))
    else:
        p.publish_projection_subpool("owned", refs[:2], created_by=("moead",), slot=0,
                                    projection=ObjectiveProjection("weighted_sum", (1.,)))
    for invoke in (
        lambda: p.replace_subpool_members("owned", refs[1:]),
        lambda: p.update_subpool_members("owned", add=refs[2:]),
        lambda: p.remove_from_subpool("owned", refs[:1]),
        lambda: p.trim_subpool("owned", 1),
    ):
        with pytest.raises(ValueError, match="candidate_collection"):
            invoke()
    assert p.subpool_refs("owned") == refs[:2]


def test_membership_rollback_and_portable_checkpoint_keep_identity_and_roots():
    p, refs = collection()
    before = p.subpool_descriptor("elite")
    baseline = p.snapshot_step_state()
    p.begin_attempt()
    p.update_subpool_members("elite", add=refs[2:], remove=refs[:1], expected=before)
    p.prepare_publication()
    p.restore_step_state(baseline)
    assert p.subpool_refs("elite") == refs[:2]
    assert p.subpool_descriptor("elite") == before
    p.begin_attempt()
    p.replace_subpool_members("elite", refs[2:])
    p.prepare_publication()
    p.commit_publication()
    restored = pool()
    restored.set_state(p.get_state())
    assert restored.subpool_refs("elite") == refs[2:]
    assert restored.subpool_descriptor("elite") == dict(before, revision=before["revision"] + 1)
    assert restored.read(refs).candidate_tokens == ("a", "b", "c", "d")


def test_removal_releases_only_one_owner_and_retention_keeps_original_row_identity():
    p = make_pool(idle_steps=1)
    refs = p.put(batch((1., 2., 3.), ("a", "b", "c")), stage="accepted")
    p.create_subpool("elite", refs)
    p.create_subpool("other", refs[1:2])
    p.retain("archive", refs[2:])
    p.remove_from_subpool("elite", refs[1:])
    assert p.read(refs[1:]).candidate_tokens == ("b", "c")
    commit_retention(p)
    assert p.select() == refs
    p.drop_subpool("other")
    commit_retention(p)
    assert p.select() == (refs[0], refs[2])
    assert p.subpool_refs("elite") == refs[:1]
    assert p.select()[1].row == 2


def test_prepared_publication_freezes_all_membership_methods_including_no_ops():
    p, refs = collection()
    p.begin_attempt()
    p.prepare_publication()
    for invoke in (
        lambda: p.replace_subpool_members("elite", refs[:2]),
        lambda: p.update_subpool_members("elite"),
        lambda: p.remove_from_subpool("elite", ()),
        lambda: p.trim_subpool("elite", 100),
        lambda: p.add_to_subpool("elite", ()),
    ):
        with pytest.raises(RuntimeError, match="frozen"):
            invoke()


@pytest.mark.parametrize("limit", [-1, True, 1.5, "1", None])
def test_trim_rejects_non_integer_or_negative_limits_without_changing_members(limit):
    p, refs = collection()
    descriptor = p.subpool_descriptor("elite")
    with pytest.raises(ValueError, match="nonnegative integer"):
        p.trim_subpool("elite", limit)
    assert p.subpool_refs("elite") == refs[:2]
    assert p.subpool_descriptor("elite") == descriptor


def test_missing_collection_is_not_implicitly_created():
    p, refs = collection()
    for invoke in (
        lambda: p.replace_subpool_members("missing", refs),
        lambda: p.update_subpool_members("missing", add=refs),
        lambda: p.remove_from_subpool("missing", ()),
        lambda: p.trim_subpool("missing", 0),
    ):
        with pytest.raises(KeyError):
            invoke()
