"""Count repeated work while checking identity, rollback and publication boundaries."""
from collections import Counter
from dataclasses import replace

import numpy as np
import pytest

from blackbase.context import create_snapshot_store
from blackbase.types import CandidateBatch, UnknownState
from nsgablack.adapters import MOEADAdapter, NSGA2Adapter
from nsgablack.adapters.population_pool_refs import validate_population_state
from nsgablack.core import BlackBoxProblem, ComposableSolver, EvolutionSolver
from nsgablack.core.evaluation_feedback import OptimizationFeedbackBatch
from nsgablack.core.state.incumbent import CandidateProvenance
from nsgablack.core.state.pool_views import ObjectiveProjection
from nsgablack.core.state.solution_pool import SolutionPool
from nsgablack.representation import RepresentationPipeline


def evaluated_pool(backend, folder):
    pool = SolutionPool(create_snapshot_store(backend=backend, base_dir=str(folder)), run_id="work-reuse")
    batch = CandidateBatch.from_candidates(
        (UnknownState([1., 2.], {"label": "left"}), UnknownState([1., 2.], {"label": "right"})),
        candidate_tokens=("left", "right"))
    records = (CandidateProvenance("left", parent_token="a"), CandidateProvenance("right", parent_token="b"))
    feedback = OptimizationFeedbackBatch.from_arrays([[3., 4.], [5., 6.]], [0., .5])
    refs = pool.put(batch, stage="accepted", feedback=feedback, provenance=[r.as_dict() for r in records])
    return pool, batch, records, feedback, refs


@pytest.mark.parametrize("backend", ["memory", "file"])
def test_complete_population_handoff_reads_each_record_once_and_revalidates(backend, tmp_path, monkeypatch):
    pool, batch, records, feedback, refs = evaluated_pool(backend, tmp_path / backend)
    control = type("Control", (), {"solution_pool": pool})()
    calls = Counter()
    read = pool.snapshots.read_verified

    def counted(identity):
        calls[identity.key] += 1
        return read(identity)

    monkeypatch.setattr(pool.snapshots, "read_verified", counted)
    bindings, saved = validate_population_state(control, batch, feedback, solution_refs=refs, provenance=records)
    assert calls == {pool._record(refs[0]).snapshot.key: 1}
    assert tuple(binding["ref"] for binding in bindings) == tuple(ref.as_dict() for ref in refs)
    assert saved == tuple(record.as_dict() for record in records)
    # All three comparisons are still active; equal numeric rows cannot swap semantics.
    different_semantics = CandidateBatch.from_candidates(
        (UnknownState([1., 2.], {"label": "right"}), batch.semantic_states[1]),
        candidate_tokens=batch.candidate_tokens)
    with pytest.raises(ValueError, match="semantic"):
        validate_population_state(control, different_semantics, feedback, solution_refs=refs, provenance=records)
    with pytest.raises(ValueError, match="raw feedback"):
        validate_population_state(control, batch, OptimizationFeedbackBatch.from_arrays([[7., 8.], [5., 6.]], [0., .5]),
                                  solution_refs=refs, provenance=records)
    with pytest.raises(ValueError, match="provenance"):
        validate_population_state(control, batch, feedback, solution_refs=refs,
                                  provenance=(replace(records[0], parent_token="tampered"), records[1]))
    # No materialization survives the call, including detached provenance.
    saved[0]["parent_token"] = "caller-only"
    _, restored = validate_population_state(control, batch, feedback, solution_refs=refs, provenance=records)
    assert restored[0]["parent_token"] == "a"


def test_row_lookup_does_not_expand_or_scan_available_rows(monkeypatch, tmp_path):
    pool, _, _, _, refs = evaluated_pool("memory", tmp_path)
    record = pool._record(refs[0])
    record_type = type(record)
    # _record and row projection no longer need the whole available_rows tuple.
    def unavailable(_):
        raise AssertionError("expanded all rows for one reference")
    monkeypatch.setattr(record_type, "available_rows", property(unavailable))
    assert pool._record(refs[1]) is record
    assert record.row_position(1) == 1
    with pytest.raises(ValueError, match="token"):
        pool._record(replace(refs[0], candidate_token="right"))
    compact = replace(record, rows=(2, 9))
    assert compact.row_position(9) == 1
    assert compact.row_position(2) == 0
    with pytest.raises(ValueError, match="retired"):
        compact.row_position(1)
    assert replace(compact, rows=(4, 9)).row_position(4) == 0


def test_joint_projection_keeps_pending_visibility_and_detaches_raw_rows(tmp_path):
    pool, batch, records, feedback, _ = evaluated_pool("memory", tmp_path)
    pool.begin_attempt()
    pending = pool.put(batch, stage="accepted", feedback=feedback, provenance=[r.as_dict() for r in records])
    with pytest.raises(ValueError, match="uncommitted"):
        pool._read_selection(pending, include_provenance=True, include_raw_feedback=True)
    _, lineage, (raw_f, raw_v) = pool._read_selection(pending[::-1], allow_pending=True,
        include_provenance=True, include_raw_feedback=True)
    raw_f[:] = 99
    raw_v[:] = 99
    lineage[0]["parent_token"] = "caller-only"
    _, saved, (raw_f, raw_v) = pool._read_selection(pending, allow_pending=True,
        include_provenance=True, include_raw_feedback=True)
    np.testing.assert_array_equal(raw_f, feedback.raw_objectives)
    np.testing.assert_array_equal(raw_v, feedback.raw_violations)
    assert saved[1]["parent_token"] == "b"


def test_direction_batch_checks_one_graph_and_is_atomic_on_late_failure(tmp_path, monkeypatch):
    pool, _, _, _, refs = evaluated_pool("memory", tmp_path)
    pool.begin_attempt()
    publications = [dict(name=f"owner/direction:{i}", refs=(refs[i % 2],), created_by=("owner",),
                         slot=i, projection=ObjectiveProjection("weighted_sum", (.5, .5))) for i in range(200)]
    calls = []
    validate = pool._validate_view_graph

    def counted(metadata, pool_id):
        calls.append(len(metadata))
        return validate(metadata, pool_id)

    monkeypatch.setattr(pool, "_validate_view_graph", counted)
    pool._publish_projection_subpools(publications)
    assert calls == [200]
    assert pool.published_subpool_names() == ()
    first = pool.subpool_metadata("owner/direction:0")
    owners, metadata = dict(pool._owners), dict(pool._subpool_metadata)
    broken = [dict(publications[0], refs=(refs[1],)),
              dict(publications[1], created_by=("different-owner",))]
    with pytest.raises(ValueError, match="different creator"):
        pool._publish_projection_subpools(broken)
    assert pool._owners == owners and pool._subpool_metadata == metadata
    # A failed final graph check also publishes none of the validated prefix.
    def fail_graph(*args):
        raise ValueError("bad frozen ancestry")
    monkeypatch.setattr(pool, "_validate_view_graph", fail_graph)
    with pytest.raises(ValueError, match="ancestry"):
        pool._publish_projection_subpools([dict(publications[0], refs=(refs[1],))])
    assert pool._owners == owners and pool._subpool_metadata == metadata
    monkeypatch.setattr(pool, "_validate_view_graph", counted)
    pool._publish_projection_subpools(publications)
    assert pool.subpool_metadata("owner/direction:0") == first
    pool._publish_projection_subpools([dict(publications[0], refs=(refs[1],))])
    changed = pool.subpool_metadata("owner/direction:0")
    assert changed["view_id"] == first["view_id"] and changed["revision"] == first["revision"] + 1
    pool.prepare_publication()
    pool.commit_publication()
    assert len(pool.published_subpool_names()) == 200


class Sphere(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=2, bounds=[(-10., 10.)] * 2, objectives=["min", "min"])

    def evaluate(self, x):
        return [float(np.sum(np.asarray(x) ** 2)), float(np.sum((np.asarray(x) - 1) ** 2))]


@pytest.mark.parametrize("kind", ["ga", "moead"])
def test_step_snapshot_owns_one_unit_projection_and_restores_without_build(kind, monkeypatch):
    adapter = (NSGA2Adapter(population_size=4, offspring_size=2) if kind == "ga" else
               MOEADAdapter(population_size=4, batch_size=2))
    solver = ComposableSolver(Sphere(), adapter=adapter, representation_pipeline=RepresentationPipeline())
    solver.setup()
    assert solver.step().committed
    before = adapter.get_state()
    expected = adapter.population.copy() if kind == "ga" else adapter.pop_X.copy()
    builder = adapter.unit_binding.builder
    dump, restore = builder.dump, builder.restore
    calls = Counter()

    def counted_dump(unit):
        calls["dump"] += 1
        return dump(unit)
    def counted_restore(payload):
        calls["restore"] += 1
        return restore(payload)
    def no_build(*args, **kwargs):
        raise AssertionError("rollback replayed Unit builder")
    def no_checkpoint():
        raise AssertionError("rollback expanded portable compatibility fields")

    monkeypatch.setattr(builder, "dump", counted_dump)
    monkeypatch.setattr(builder, "restore", counted_restore)
    monkeypatch.setattr(builder, "build", no_build)
    monkeypatch.setattr(adapter, "_get_algorithm_state", no_checkpoint)
    snapshot = adapter.snapshot_step_state()
    assert calls == {"dump": 1}
    assert not {"population", "objectives", "violations", "weights", "neighbors"}.intersection(snapshot)
    assert not {"weights", "neighbors", "candidate_tokens", "pending_indices", "pending_modes"}.intersection(
        snapshot.get("adapter_state", {}))
    adapter.algorithm_unit.population[:] = 99
    with pytest.raises(ValueError, match="changed since feedback"):
        adapter.algorithm_unit.require_current_feedback()
    adapter._rng.random(5)
    adapter._population_pool_bindings = ()
    adapter.restore_step_state(snapshot)
    assert calls == {"dump": 1, "restore": 1}
    np.testing.assert_array_equal(adapter.algorithm_unit.population, expected)
    adapter.algorithm_unit.require_current_feedback()
    monkeypatch.undo()
    after = adapter.get_state()
    assert before == after


def test_evolution_known_provenance_is_not_read_separately(monkeypatch):
    solver = EvolutionSolver(Sphere(), pop_size=4, max_generations=1)
    solver.setup()
    def no_separate_read(*args, **kwargs):
        raise AssertionError("known lineage read separately")
    monkeypatch.setattr(solver.solution_pool, "read_provenance", no_separate_read)
    solver.initialize_population()
    assert len(solver.get_candidate_population_provenance()) == 4


@pytest.mark.parametrize("base", [NSGA2Adapter, MOEADAdapter])
def test_custom_algorithm_state_extension_retains_its_explicit_snapshot_contract(base):
    class Extended(base):
        def _get_algorithm_state(self):
            return {**super()._get_algorithm_state(), "extra_local": list(self.extra_local)}

        def _set_algorithm_state(self, state):
            super()._set_algorithm_state(state)
            self.extra_local = list(state["extra_local"])

    adapter = Extended(population_size=4)
    adapter.extra_local = [1, 2]
    snapshot = adapter.snapshot_step_state()
    adapter.extra_local.append(3)
    adapter.ensure_unit()
    adapter.restore_step_state(snapshot)
    assert adapter.algorithm_unit is None
    assert adapter.extra_local == [1, 2]
