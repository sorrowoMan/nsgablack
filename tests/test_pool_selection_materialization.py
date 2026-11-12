"""One verified pool load feeds values and lineage; numeric drafts stay numeric."""
from collections import Counter
from dataclasses import replace

import numpy as np
import pytest

from blackbase.context import create_snapshot_store
from blackbase.types import CandidateBatch, UnknownState
from nsgablack.core import BlackBoxProblem, SolverBase
from nsgablack.core.state.incumbent import CandidateProvenance
from nsgablack.core.state.solution_pool import SolutionPool
from nsgablack.representation import RepresentationPipeline
from nsgablack.representation import structure_builders


class Problem(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=2, objectives=["minimize"], bounds=[(-10., 10.)] * 2)

    def evaluate(self, candidate):
        return [float(np.sum(np.asarray(candidate) ** 2))]


def make_solver(backend, folder, *, pipeline=None):
    solver = SolverBase(Problem(), representation_pipeline=pipeline)
    solver.solution_pool = SolutionPool(
        create_snapshot_store(backend=backend, base_dir=str(folder)), run_id="materialization-test",
    )
    return solver


def watch_verified_reads(monkeypatch, pool):
    counts = Counter()
    original = pool.snapshots.read_verified
    def read(identity):
        counts[identity.key] += 1
        return original(identity)
    monkeypatch.setattr(pool.snapshots, "read_verified", read)
    return counts


def seeds(solver):
    states = (UnknownState([1., 2.], {"label": "left"}),
              UnknownState([1., 2.], {"label": "right"}))
    refs = solver.store_solutions(
        CandidateBatch.from_candidates(states, candidate_tokens=("left", "right")),
        stage="accepted",
        provenance=(CandidateProvenance("left", parent_token="ancestor-left"),
                    CandidateProvenance("right", parent_token="ancestor-right")),
    )
    return refs


@pytest.mark.parametrize("backend", ["memory", "file"])
def test_read_solutions_verifies_each_record_once_with_repeated_refs_and_lineage(backend, tmp_path, monkeypatch):
    solver = make_solver(backend, tmp_path / backend)
    left, right = seeds(solver)
    counts = watch_verified_reads(monkeypatch, solver.solution_pool)
    batch = solver.read_solutions((right, left, right))
    key = solver.solution_pool._record(left).snapshot.key
    assert counts == {key: 1}
    assert batch.candidate_tokens == ("right", "left", "right")
    assert [state.metadata["label"] for state in batch.semantic_states] == ["right", "left", "right"]
    assert [solver.candidate_provenance_for(state).parent_token for state in batch.semantic_states] == [
        "ancestor-right", "ancestor-left", "ancestor-right",
    ]
    solver.read_solutions((left, right))
    assert counts == {key: 2}  # no cache crosses calls or hides later corruption.
    with pytest.raises(ValueError, match="token"):
        solver.read_solutions((replace(left, candidate_token="right"),))


@pytest.mark.parametrize("backend", ["memory", "file"])
def test_joint_projection_still_checks_pending_visibility_and_detaches_lineage(backend, tmp_path):
    solver = make_solver(backend, tmp_path / backend)
    pool = solver.solution_pool
    pool.begin_attempt()
    refs = seeds(solver)
    with pytest.raises(ValueError, match="uncommitted"):
        solver.read_solutions(refs)
    batch, lineage = pool._read_selection(refs, allow_pending=True, include_provenance=True)
    lineage[0]["parent_token"] = "caller-only"
    copy = np.array(batch.numeric_matrix, copy=True)
    copy[:] = 99
    assert pool.read_provenance(refs, allow_pending=True)[0]["parent_token"] == "ancestor-left"
    np.testing.assert_array_equal(pool.read(refs, allow_pending=True).numeric_matrix, [[1., 2.], [1., 2.]])


def test_later_durable_corruption_cannot_be_hidden_by_previous_joint_read(tmp_path):
    solver = make_solver("memory", tmp_path)
    refs = seeds(solver)
    solver.read_solutions(refs)
    record = solver.solution_pool._record(refs[0])
    solver.solution_pool.snapshots._data[record.snapshot.key].data["source"] = "tampered"
    with pytest.raises(ValueError, match="digest"):
        solver.read_solutions(refs)


@pytest.mark.parametrize("backend", ["memory", "file"])
def test_missing_population_source_window_reads_values_and_lineage_together(backend, tmp_path, monkeypatch):
    solver = make_solver(backend, tmp_path / backend)
    left, right = seeds(solver)
    counts = watch_verified_reads(monkeypatch, solver.solution_pool)
    # No previous population/evaluation window is supplied. Explicit tokens
    # resolve saved members, including repeated slots, without value matching.
    selected = solver.commit_candidate_population(
        np.array([[1., 2.], [1., 2.], [1., 2.]]),
        (right.candidate_token, left.candidate_token, right.candidate_token),
    )
    key = solver.solution_pool._record(left).snapshot.key
    assert counts == {key: 1}
    assert selected.candidate_tokens == ("right", "left", "right")
    assert [state.metadata["label"] for state in selected.semantic_states] == ["right", "left", "right"]
    assert [record.parent_token for record in solver.get_candidate_population_provenance()] == [
        "ancestor-right", "ancestor-left", "ancestor-right",
    ]


class NumericMutation:
    def mutate(self, candidate, context):
        candidate += 3
        return candidate


class NumericRepair:
    def repair(self, candidate, context):
        candidate[:] = np.minimum(candidate, 4.)
        return candidate


@pytest.mark.parametrize("backend", ["memory", "file"])
def test_real_handoff_mutate_repair_reads_once_per_record_without_numeric_codec(backend, tmp_path, monkeypatch):
    solver = make_solver(backend, tmp_path / backend, pipeline=RepresentationPipeline(
        mutator=NumericMutation(), repair=NumericRepair(),
    ))
    left, right = seeds(solver)
    source_key = solver.solution_pool._record(left).snapshot.key
    reads = watch_verified_reads(monkeypatch, solver.solution_pool)
    original_encode = structure_builders.encode_unit_value
    numeric_encodes = []
    def encode(value):
        if isinstance(value, np.ndarray):
            numeric_encodes.append(value.shape)
        return original_encode(value)
    monkeypatch.setattr(structure_builders, "encode_unit_value", encode)
    source = solver.propose_solutions((left,))
    row = source.numeric_rows()[0]
    lineage = solver.candidate_provenance_for(source.semantic_states[0])
    solver.bind_candidate_provenance((row,), (lineage,), activate=False)
    changed = solver.mutate_candidate(row)
    repaired = solver.repair_candidate(changed)
    assert reads[source_key] == 1  # formerly value read + provenance read.
    # Four distinct durable stages remain; each is still read and verified.
    assert len(reads) == 5 and all(count == 1 for count in reads.values())
    assert numeric_encodes == []  # formerly two ndarray.tolist codec roundtrips.
    np.testing.assert_array_equal(row, [1., 2.])
    np.testing.assert_array_equal(changed, [4., 5.])
    np.testing.assert_array_equal(repaired, [4., 4.])
    changed_lineage = solver.candidate_provenance_for(changed)
    repaired_lineage = solver.candidate_provenance_for(repaired)
    assert changed_lineage.parent_token == lineage.candidate_token
    assert changed_lineage.candidate_token == repaired_lineage.candidate_token
    assert repaired_lineage.transform_stage == "repair"
    assert solver.semantic_candidate_state(repaired).metadata["label"] == "left"
    np.testing.assert_array_equal(solver.read_solutions((right,)).numeric_matrix, [[1., 2.]])


@pytest.mark.parametrize("dtype", ["bool", "int16", "uint32", ">f8", "float32"])
def test_numeric_draft_copy_preserves_values_dtype_shape_and_closed_array_storage(dtype):
    source = np.array([[0, 1], [2, 3]], dtype=dtype, order="F")
    source.setflags(write=False)
    draft = SolverBase._copy_candidate_draft(source)
    assert draft.dtype == source.dtype and draft.shape == source.shape
    assert type(draft) is np.ndarray and draft.flags.c_contiguous and draft.flags.writeable
    assert not np.shares_memory(draft, source)
    np.testing.assert_array_equal(draft, source)


def test_semantic_draft_uses_codec_and_preserves_nested_metadata(monkeypatch):
    original = UnknownState([1., 2.], {"layout": {"shape": [2]}, "tag": "semantic"})
    calls = []
    encode = structure_builders.encode_unit_value
    def record(value):
        calls.append(type(value))
        return encode(value)
    monkeypatch.setattr(structure_builders, "encode_unit_value", record)
    draft = SolverBase._copy_candidate_draft(original)
    assert calls == [UnknownState]
    assert draft is not original
    assert draft.as_dict() == original.as_dict()
    assert not np.shares_memory(draft.values, original.values)


@pytest.mark.parametrize("special", ["subclass", "dtype-metadata"])
def test_special_arrays_keep_the_existing_closed_codec_path(monkeypatch, special):
    if special == "subclass":
        class TaggedArray(np.ndarray):
            pass
        value = np.array([1., 2.]).view(TaggedArray)
        value.runtime_object = object()
    else:
        value = np.array([1., 2.], dtype=np.dtype("float64", metadata={"label": "dtype-only"}))
    original = structure_builders.encode_unit_value
    calls = []
    def encode(item):
        calls.append(type(item))
        return original(item)
    monkeypatch.setattr(structure_builders, "encode_unit_value", encode)
    draft = SolverBase._copy_candidate_draft(value)
    assert calls == [type(value)]
    assert type(draft) is np.ndarray and draft.dtype.metadata is None
    assert not hasattr(draft, "runtime_object")
    np.testing.assert_array_equal(draft, value)
    assert not np.shares_memory(draft, value)


@pytest.mark.parametrize("value", [np.array([object()]), np.array([1 + 2j]), object()])
def test_draft_copy_does_not_admit_runtime_objects_or_complex_arrays(value):
    with pytest.raises(TypeError):
        SolverBase._copy_candidate_draft(value)
