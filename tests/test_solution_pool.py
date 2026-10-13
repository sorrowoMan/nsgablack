import copy
from dataclasses import replace

import numpy as np
import pytest
from blackbase.context import create_snapshot_store
from blackbase.types import CandidateBatch, UnknownState

from nsgablack.core.state.solution_pool import SolutionPool, SolutionStamp
from nsgablack.core.evaluation_feedback import OptimizationFeedbackBatch


def batch(values=(1., 2.), tokens=("a", "b")):
    return CandidateBatch.from_candidates(
        [UnknownState([v], {"label": t}) for v,t in zip(values,tokens)], candidate_tokens=tokens)


def pool():
    return SolutionPool(create_snapshot_store(backend="memory"), run_id="run-1")


def test_timestamp_cutoff_and_equal_values_preserve_identity_and_metadata():
    p = pool()
    first = p.put(batch((1., 1.)), stage="accepted")
    cutoff = p.timestamp
    second = p.put(batch((3.,), ("c",)), stage="accepted")
    assert p.select(at=cutoff) == first
    assert p.select() == first + second
    restored = p.read(first)
    assert restored.candidate_tokens == ("a", "b")
    assert [s.metadata["label"] for s in restored.semantic_states] == ["a", "b"]
    with pytest.raises(ValueError):
        p.select(at=SolutionStamp("other-run", 1))
    with pytest.raises(ValueError):
        p.read((replace(first[0], candidate_token="b"),))


def test_drafts_are_private_and_rollback_does_not_reuse_time_or_consume_inputs():
    p = pool()
    seeds = p.put(batch(), stage="accepted")
    key = p.bind_input(seeds)
    before = p.snapshot_step_state()
    p.begin_attempt()
    assert p.take_input(key) == seeds[0]
    refs = p.put(batch((9.,), ("new",)), stage="accepted")
    failed_time = p.timestamp
    assert p.select() == seeds
    with pytest.raises(ValueError, match="uncommitted"):
        p.read(refs)
    assert p.read(refs, allow_pending=True).numeric_matrix[0,0] == 9.
    p.restore_step_state(before)
    assert p.take_input(key) == seeds[0]
    with pytest.raises(ValueError):
        p.read(refs, allow_pending=True)
    p.put(batch((4.,), ("later",)), stage="accepted")
    assert p.timestamp.sequence > failed_time.sequence


def test_publication_manifest_and_portable_checkpoint_restore_validate_values():
    p = pool()
    p.begin_attempt()
    refs = p.put(batch(), stage="accepted")
    manifest = p.prepare_publication()
    assert not p.select()
    p.commit_publication()
    assert p.select() == refs
    restored = pool()
    restored.set_state(p.get_state())
    np.testing.assert_array_equal(restored.read(refs).numeric_matrix, [[1.], [2.]])
    same_store = SolutionPool(p.snapshots)
    same_store.restore_publication(manifest)
    assert same_store.select() == refs
    corrupted = copy.deepcopy(p.get_state())
    corrupted["payloads"][refs[0].record_id]["batch"]["numeric_matrix"][0][0] = 100.
    with pytest.raises(ValueError, match="digest"):
        restored.set_state(corrupted)
    np.testing.assert_array_equal(restored.read(refs).numeric_matrix, [[1.], [2.]])


def test_pool_stores_raw_feedback_and_repair_preserves_previous_version():
    p = pool()
    original = p.put(batch((1.,), ("x",)), stage="accepted")
    changed = p.put(batch((5.,), ("x",)), stage="repair")
    assert original[0].candidate_token == changed[0].candidate_token
    assert original[0].record_id != changed[0].record_id
    assert p.read(original).numeric_matrix[0,0] == 1.
    from blackbase.types import Feedback
    feedback = OptimizationFeedbackBatch.from_feedback((Feedback(
        objectives=[0.], info={"raw_evaluation": {"objectives": [5.], "constraint_violation": 4.}}
    ),), violations=[0.])
    refs = p.put(batch((5.,), ("x",)), stage="accepted", feedback=feedback)
    data = p.snapshots.read_verified(p._record(refs[0]).snapshot).data
    assert data["raw_feedback"] == {"objectives": [[5.]], "violations": [4.]}


def test_empty_selection_and_exhausted_input_do_not_invent_candidates():
    p = pool()
    key = p.bind_input(())
    with pytest.raises(ValueError, match="exhausted"):
        p.take_input(key)
    with pytest.raises(ValueError, match="empty"):
        p.read(())


def test_private_drafts_leave_index_and_published_values_are_detached():
    p = pool()
    p.begin_attempt()
    drafts = p.put(batch(), stage="mutation")
    accepted = p.put(batch(), stage="accepted")
    p.prepare_publication()
    p.commit_publication()
    assert p.record_count == 1
    with pytest.raises(ValueError):
        p.read(drafts, allow_pending=True)
    value = p.read(accepted)
    # CandidateBatch's own read-only views may reject the write. Either way,
    # its detached copy cannot change a persisted pool version.
    copy = np.array(value.numeric_matrix, copy=True)
    copy[0,0] = 99.
    assert p.read(accepted).numeric_matrix[0,0] == 1.


def test_solver_reads_preserve_lineage_and_handoff_is_explicitly_derived():
    from nsgablack.core import BlackBoxProblem, SolverBase
    from nsgablack.core.state.incumbent import CandidateProvenance
    class Problem(BlackBoxProblem):
        def evaluate(self, x):
            return [1.]
    solver = SolverBase(Problem(dimension=1, bounds=[(-10.,10.)], objectives=["min"]))
    values = batch((1.,), ("existing",))
    lineage = CandidateProvenance("existing", source_kind="mutation", parent_token="ancestor")
    refs = solver.store_solutions(values, provenance=(lineage,))
    read = solver.read_solutions(refs)
    assert solver.candidate_provenance_for(read.semantic_states[0]).parent_token == "ancestor"
    proposed = solver.propose_solutions(refs)
    record = solver.candidate_provenance_for(proposed.semantic_states[0])
    assert record.candidate_token != "existing" and record.parent_token == "existing"
    assert dict(record.metadata["solution_source_ref"]) == refs[0].as_dict()
    assert solver.read_solutions(refs).candidate_tokens == ("existing",)


def test_prepared_manifest_freezes_writes_and_input_mutations():
    p = pool()
    refs = p.put(batch(), stage="accepted")
    key = p.bind_input(refs)
    p.begin_attempt()
    p.prepare_publication()
    with pytest.raises(RuntimeError, match="frozen"):
        p.put(batch(), stage="accepted")
    with pytest.raises(RuntimeError, match="frozen"):
        p.take_input(key)
    p.commit_publication()
    assert p.take_input(key) == refs[0]
