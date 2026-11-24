"""Exact-version, lazy and call-scoped inputs for ordinary change functions."""
from dataclasses import replace

import numpy as np
import pytest
from blackbase.context import create_snapshot_store
from blackbase.types import CandidateBatch, Feedback, UnknownState

from nsgablack.adapters.change_pool import ChangePool, ChangeResult, ChangeSelection, PoolOutput
from nsgablack.core.evaluation_feedback import OptimizationFeedbackBatch
from nsgablack.core.state.pool_views import ObjectiveProjection
from nsgablack.core.state.solution_pool import SolutionPool


def pool():
    return SolutionPool(create_snapshot_store(backend="memory"), run_id="change-test")


def put(p, values=(1.0, 2.0), tokens=("a", "b"), **kwargs):
    batch = CandidateBatch.from_candidates(
        [UnknownState([x], {"source": token}) for x, token in zip(values, tokens)],
        candidate_tokens=tokens)
    return p.put(batch, stage="accepted", **kwargs)


def test_main_cutoff_exact_versions_and_lazy_readonly_values():
    p = pool()
    first = put(p, (1., 1.), ("a", "b"))
    second = put(p, (1.,), ("a",))
    scope = ChangePool(p)
    later = put(p, (8.,), ("c",))
    chosen = scope.main()
    assert chosen.refs == first + second
    assert scope.used_refs == ()
    assert len(chosen) == 3
    values = chosen.values
    np.testing.assert_array_equal(values, [[1.], [1.], [1.]])
    assert scope.used_refs == first + second
    with pytest.raises(ValueError):
        values.setflags(write=True)
    with pytest.raises(ValueError):
        values[0, 0] = 9
    with pytest.raises(ValueError, match="cutoff"):
        scope.read(later)
    assert scope.read(first).candidates[0].metadata["source"] == "a"
    assert first[0] != first[1] != second[0]
    with pytest.raises(ValueError, match="token"):
        scope.read((replace(first[0], candidate_token="b"),))


def test_subpool_membership_freezes_and_missing_or_pending_cannot_look_empty():
    p = pool()
    refs = put(p)
    p.create_subpool("elite", refs[:1])
    scope = ChangePool(p)
    p.add_to_subpool("elite", refs[1:])
    assert scope.subpool("elite").refs == refs[:1]
    p.drop_subpool("elite")
    p.create_subpool("elite", refs[1:])
    assert scope.subpool("elite").refs == refs[:1]
    p.create_subpool("later", refs)
    with pytest.raises(ValueError, match="cutoff"):
        scope.subpool("later")
    with pytest.raises(KeyError, match="does not exist"):
        scope.subpool("missing")
    p.begin_attempt()
    p.create_subpool("pending", refs)
    assert "pending" not in p.published_subpool_names()
    during = ChangePool(p)
    with pytest.raises(ValueError, match="uncommitted"):
        during.subpool("pending")
    pending = put(p, (8.,), ("pending",))
    with pytest.raises(ValueError, match="uncommitted"):
        during.read(pending)


def test_random_take_and_merge_are_identity_operations_and_never_global_rng():
    p = pool()
    refs = put(p, (1., 1., 2.), ("a", "b", "c"))
    scope = ChangePool(p)
    chosen = scope.main()
    assert chosen.random(2, rng=np.random.default_rng(4)).refs == chosen.random(
        2, rng=np.random.default_rng(4)).refs
    assert chosen.take((2, 0)).refs == (refs[2], refs[0])
    assert chosen.take((0, 1)).merge(chosen.take((1, 2))).refs == refs
    assert len(chosen.take(())) == 0
    with pytest.raises(ValueError, match="empty"):
        chosen.take(()).values
    with pytest.raises(ValueError, match="different"):
        chosen.merge(ChangePool(p).main())
    for invalid in (-1, 4, True, 1.5):
        with pytest.raises(ValueError, match="count"):
            chosen.random(invalid, rng=np.random.default_rng(0))
    with pytest.raises(IndexError):
        chosen.take((-1,))
    with pytest.raises(TypeError):
        chosen.take((True,))
    with pytest.raises(TypeError, match="Generator"):
        chosen.random(1, rng=None)


def test_pending_at_scope_start_stays_hidden_if_published_during_the_call():
    p = pool()
    previous = put(p)
    p.begin_attempt()
    pending = put(p, (9.,), ("pending",))
    p.create_subpool("pending-view", previous)
    scope = ChangePool(p)
    p.prepare_publication()
    p.commit_publication()
    assert p.select(stage=None) == previous + pending
    assert scope.main().refs == previous
    with pytest.raises(ValueError, match="uncommitted at"):
        scope.read(pending)
    with pytest.raises(ValueError, match="cutoff"):
        scope.subpool("pending-view")
    assert ChangePool(p).main().refs == previous + pending


def test_projected_subpool_reads_raw_feedback_and_tracks_materialized_refs():
    p = pool()
    feedback = OptimizationFeedbackBatch.from_feedback((Feedback(objectives=[0.], info={
        "raw_evaluation": {"objectives": [3., 7.], "constraint_violation": 5.}
    }),), violations=[0.])
    refs = put(p, (1.,), ("a",), feedback=feedback)
    p.publish_projection_subpool("direction", refs, created_by=("moead",), slot=0,
        projection=ObjectiveProjection("weighted_sum", (0.8, 0.2)))
    scope = ChangePool(p)
    f, v = scope.subpool("direction").raw_feedback()
    np.testing.assert_array_equal(f, [[3., 7.]])
    np.testing.assert_array_equal(v, [5.])
    assert scope.used_refs == refs
    with pytest.raises(ValueError):
        f.setflags(write=True)
    unevaluated = p.put(CandidateBatch.from_candidates([[4.]], candidate_tokens=("seed",)))
    before = ChangePool(p)
    with pytest.raises(ValueError, match="no raw evaluation"):
        before.read(unevaluated).raw_feedback()
    assert before.used_refs == ()


def test_scope_closure_invalidates_retained_selections_without_copying_whole_pool(monkeypatch):
    p = pool()
    refs = put(p)
    original = p.read
    calls = []

    def track(refs, **kwargs):
        calls.append(tuple(refs))
        return original(refs, **kwargs)

    monkeypatch.setattr(p, "read", track)
    p.create_subpool("elite", refs)
    scope = ChangePool(p)
    chosen = scope.subpool("elite").take((1,))
    assert calls == []
    chosen.values
    assert calls == [refs[1:]]
    scope.close()
    for operation in (lambda: chosen.refs, lambda: len(chosen), lambda: chosen.values,
                      lambda: chosen.raw_feedback(), lambda: scope.main(), lambda: scope.read(refs),
                      lambda: scope.subpool("elite"), lambda: chosen.take((0,)),
                      lambda: chosen.merge(chosen), lambda: scope.used_refs):
        with pytest.raises(RuntimeError, match="ended"):
            operation()
    scope.close()


def test_restricted_scope_cannot_read_donors_outside_explicit_sources():
    p = pool()
    refs = put(p)
    p.create_subpool("elite", refs[1:])
    scope = ChangePool(p, allowed_refs=refs[:1], allow_main=False)
    assert scope.read(refs[:1]).refs == refs[:1]
    with pytest.raises(ValueError, match="declared inputs"):
        scope.main()
    with pytest.raises(ValueError, match="declared inputs"):
        scope.subpool("elite")
    with pytest.raises(ValueError, match="declared inputs"):
        scope.read(refs[1:])
    with pytest.raises(ValueError, match="declared inputs"):
        ChangeSelection(scope, refs[1:])
    explicit = ChangePool(p, allowed_refs=refs[:1], allowed_subpools=("elite",), allow_main=False)
    assert explicit.subpool("elite").refs == refs[1:]
    assert explicit.read(refs[1:]).refs == refs[1:]
    main = ChangePool(p, allowed_refs=(), allow_main=True)
    assert main.main().refs == refs
    assert main.read(refs).refs == refs


def test_retired_or_foreign_versions_fail_instead_of_resolving_new_token_versions():
    p = pool()
    refs = put(p)
    scope = ChangePool(p)
    chosen = scope.read(refs[:1])
    state = p.snapshot_step_state()
    state["index"]["records"] = []
    state["index"]["retention"]["last_used"] = {}
    p.restore_step_state(state)
    with pytest.raises(ValueError, match="unavailable"):
        chosen.values
    other = pool()
    with pytest.raises(ValueError, match="another pool"):
        ChangePool(other).read(refs)


def test_change_result_validates_outputs_without_creating_pools():
    p = pool()
    refs = put(p)
    output = PoolOutput("elite", create=True)
    result = ChangeResult([2.], source_refs=refs[:1], outputs=(output, output))
    assert result.outputs == (output,)
    assert result.source_refs == refs[:1]
    assert not p.has_subpool("elite")
    assert ChangeResult([1.]).source_refs is None
    with pytest.raises(ValueError, match="conflicting"):
        ChangeResult([1.], outputs=(output, PoolOutput("elite")))
    with pytest.raises(TypeError, match="SolutionRef"):
        ChangeResult([1.], source_refs=("a",))
    with pytest.raises(TypeError, match="PoolOutput"):
        ChangeResult([1.], outputs=("elite",))
    with pytest.raises(ValueError, match="nonempty"):
        PoolOutput(" ")
    with pytest.raises(TypeError, match="boolean"):
        PoolOutput("elite", create=1)
    with pytest.raises(TypeError):
        PoolOutput("elite", True)


def test_restricted_scope_only_freezes_declared_donors_without_enumerating_views(monkeypatch):
    p = pool()
    refs = put(p)
    p.create_subpool("donor", refs[:1])
    p.create_subpool("unrelated-direction", refs[1:])
    calls = []

    def must_not_enumerate():
        pytest.fail("a restricted change enumerated all published views")

    monkeypatch.setattr(p, "published_subpool_names", must_not_enumerate)
    for method in ("subpool_metadata", "subpool_descriptor", "subpool_refs"):
        original = getattr(p, method)

        def track(name, _original=original, _method=method):
            calls.append((_method, name))
            return _original(name)

        monkeypatch.setattr(p, method, track)
    ChangePool(p, allowed_refs=refs[:1], allow_main=False)
    assert calls == []
    scope = ChangePool(p, allowed_refs=(), allowed_subpools=("donor", "missing"), allow_main=False)
    assert calls and all(name == "donor" for _, name in calls)
    assert {method for method, _ in calls} == {"subpool_metadata", "subpool_descriptor", "subpool_refs"}
    assert scope.subpool("donor").refs == refs[:1]
    with pytest.raises(KeyError, match="does not exist"):
        scope.subpool("missing")
