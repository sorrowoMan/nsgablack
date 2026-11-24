"""Quality-diversity decisions survive real repair, disposition and transactions."""
import json
from pathlib import Path

import numpy as np
import pytest
from blackbase.contracts import BatchDisposition
from blackbase.project import build_case, load_case_builder, run_case
from blackbase.resources import ResourceAllocator, ResourceContext, ResourceRequest
from nsgablack.adapters.map_elites import (
    MapElitesAdapter, MapElitesConfig, SequenceEmitter, GaussianArchiveEmitter, GridCells,
)
from nsgablack.core import ComposableSolver
from nsgablack.plugins import CheckpointResumeConfig, CheckpointResumePlugin
from nsgablack.representation import RepresentationPipeline
from examples.cases.algorithm_semantics.cases.map_elites_archive.problem import ArchiveProblem


POINTS = ((.1, .1), (.4, .4), (.6, .4), (.6, .8), (.8, .2))
PROJECT = Path(__file__).resolve().parents[1] / "examples/cases/algorithm_semantics"


def make(points=POINTS, *, batch_size=5, repair=None, acceptance=None, emitter=None, cells=None):
    adapter = MapElitesAdapter(MapElitesConfig(batch_size=batch_size),
        emitter=emitter or SequenceEmitter(points), cells=cells)
    solver = ComposableSolver(ArchiveProblem(), adapter=adapter,
        representation_pipeline=RepresentationPipeline(repair=repair),
        evaluation_acceptance_policy=acceptance, snapshot_strict=True, plugin_strict=True)
    solver.set_random_seed(42)
    return solver


def archive(solver):
    return {tuple(entry["cell"]): np.asarray(entry["candidate"]).tolist()
            for entry in solver.adapter.algorithm_unit.entries}


def normalized_state(adapter):
    return json.loads(json.dumps(adapter.get_state(), default=lambda value: value.tolist()))


def test_five_true_evaluations_produce_three_exact_champions_and_one_view():
    solver = make()
    assert solver.adapter.algorithm_unit is None
    assert solver.adapter.get_state()["algorithm_unit"] is None
    result = solver.step()
    assert result.committed and solver.evaluation_count == solver.problem.calls == 5
    assert archive(solver) == {(0, 0): [.4, .4], (1, 0): [.6, .4], (1, 1): [.6, .8]}
    unit = solver.adapter.algorithm_unit
    assert unit.evaluations == 5 and unit.replacements == 4  # A insertion, B replacement, C/D insertions
    refs = solver.adapter.get_population_solution_refs(solver)
    assert solver.solution_pool.subpool_refs("map_elites/archive") == refs
    np.testing.assert_allclose(solver.objectives[:, 0], [.20, .32, .16])
    np.testing.assert_array_equal(solver.population, solver.solution_pool.read(refs).numeric_matrix)
    assert solver.adapter.get_population_candidate_tokens() == tuple(ref.candidate_token for ref in refs)
    snapshot = solver.read_snapshot(solver._latest_snapshot_handle.key)
    np.testing.assert_array_equal(snapshot["population"], solver.population)
    assert len(solver.solution_pool.select(stage="accepted")) == 5


class RoundFirst:
    def repair(self, candidate, context=None):
        value = np.asarray(candidate).copy()
        value[0] = np.round(value[0], 1)
        return value


def test_repair_recomputes_behavior_cell_and_scores_actual_evaluated_version():
    solver = make(((.49, .6),), repair=RoundFirst())
    assert solver.step().committed
    assert archive(solver) == {(1, 1): [.5, .6]}
    entry, = solver.adapter.algorithm_unit.entries
    np.testing.assert_allclose(entry["descriptor"], [.5, .6])
    assert entry["quality"] == pytest.approx(.13)
    ref, = solver.adapter.get_solution_pool_roots(solver)
    np.testing.assert_array_equal(solver.solution_pool.read((ref,)).numeric_matrix, [[.5, .6]])
    assert solver.evaluation_count == 1


class SelectRows:
    policy_id = "test-fixed-original-indices/v1"
    def select(self, candidates, feedback, context):
        return BatchDisposition(proposed_count=feedback.candidate_count, accepted_indices=(1, 2, 4))


def test_partial_acceptance_preserves_original_indices_and_still_competes_within_cell():
    solver = make(acceptance=SelectRows())
    outcome = solver.step()
    assert outcome.committed
    assert solver.evaluation_count == solver.problem.calls == 5
    assert archive(solver) == {(0, 0): [.4, .4], (1, 0): [.6, .4]}
    assert solver.adapter.algorithm_unit.evaluations == 3
    refs = solver.adapter.get_solution_pool_roots(solver)
    assert tuple(ref.row for ref in refs) == (0, 1)  # accepted Pool batch has its own precise row coordinates
    assert solver._last_evaluated_event_batch.numeric_matrix.shape == (5, 2)
    np.testing.assert_allclose(solver._last_evaluated_event_feedback.raw_objectives[:, 0], [.5, .2, .32, .16, .72])


def test_equal_quality_retains_existing_champion_but_observations_keep_distinct_tokens():
    # Same numeric point is two independent evaluated proposals; archive ties keep first.
    solver = make(((.4, .4), (.4, .4)))
    solver.step()
    refs = solver.solution_pool.select(stage="accepted")
    assert len(refs) == 2 and refs[0].candidate_token != refs[1].candidate_token
    assert solver.adapter.get_solution_pool_roots(solver) == (refs[0],)
    assert solver.adapter.algorithm_unit.evaluations == 2
    assert solver.adapter.algorithm_unit.replacements == 1


@pytest.mark.parametrize("failure", ["update", "pool-staging"])
def test_failure_after_archive_updates_rolls_back_unit_views_rng_and_emitter(monkeypatch, failure):
    solver = make(batch_size=2)
    solver.setup()
    assert solver.step().committed
    before = normalized_state(solver.adapter)
    identity = solver.get_population_authority_identity()
    descriptor = solver.solution_pool.subpool_descriptor("map_elites/archive")
    refs = solver.adapter.get_solution_pool_roots(solver)
    if failure == "update":
        original = solver.adapter.update
        def fail(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError("after archive update")
        monkeypatch.setattr(solver.adapter, "update", fail)
    else:
        monkeypatch.setattr(solver.solution_pool, "prepare_publication",
                            lambda: (_ for _ in ()).throw(RuntimeError("pool staging failure")))
    with pytest.raises(RuntimeError):
        solver.step()
    assert normalized_state(solver.adapter) == before
    assert solver.problem.calls == solver.evaluation_count == 4
    assert solver.get_population_authority_identity() == identity
    assert solver.solution_pool.subpool_descriptor("map_elites/archive") == descriptor
    assert solver.solution_pool.subpool_refs("map_elites/archive") == refs
    assert len(solver.solution_pool.select(stage="accepted")) == 2


def test_numeric_setters_cannot_replace_identity_bound_archive():
    solver = make()
    solver.step()
    x, f, v = solver.adapter.get_population_snapshot()
    assert solver.adapter.set_population_snapshot(x, f, v)
    with pytest.raises(ValueError, match="cannot replace"):
        solver.adapter.set_population_snapshot(x+1, f, v)
    with pytest.raises(ValueError, match="identities"):
        solver.adapter.set_population_candidate_tokens(("made-up",)*3)


def test_grid_edges_and_out_of_range_are_explicit():
    grid = GridCells()
    assert grid.locate([0., 0.]) == (0, 0)
    assert grid.locate([.5, .5]) == grid.locate([1., 1.]) == (1, 1)
    with pytest.raises(ValueError, match="outside"):
        grid.locate([1.01, .2])


def test_changed_grid_checkpoint_is_rejected_without_building_a_unit():
    source = make()
    source.step()
    target = make(cells=GridCells(bins=(3, 3)))
    with pytest.raises(ValueError, match="identity"):
        target.adapter.set_state(source.adapter.get_state())
    assert target.adapter.algorithm_unit is None


def test_restored_wrong_raw_cache_cannot_be_used_for_further_competition():
    solver = make(batch_size=2)
    solver.step()
    state = solver.adapter.get_state()
    saved_unit = solver.adapter.unit_binding.restore(state["algorithm_unit"])
    saved_unit.entries[0]["objectives"] = np.array([-100.])
    saved_unit.entries[0]["quality"] = -100.
    state["algorithm_unit"] = solver.adapter.unit_binding.dump(saved_unit)
    solver.adapter.set_state(state)
    with pytest.raises(ValueError, match="cached raw feedback"):
        solver.adapter.propose(solver, {})
    assert solver.problem.calls == 2


@pytest.mark.parametrize("field,value", [("quality", -2.), ("cell", (1, 1)), ("descriptor", [.8, .8])])
def test_invalid_pure_archive_interpretation_fails_before_restoring_component_cursors(field, value):
    source = make(batch_size=2)
    source.step()
    state = source.adapter.get_state()
    saved_unit = source.adapter.unit_binding.restore(state["algorithm_unit"])
    saved_unit.entries[0][field] = value
    state["algorithm_unit"] = source.adapter.unit_binding.dump(saved_unit)
    target = make(batch_size=2)
    before = normalized_state(target.adapter)
    with pytest.raises(ValueError, match="archive"):
        target.adapter.set_state(state)
    assert normalized_state(target.adapter) == before


def test_two_instances_do_not_share_archive_and_stateful_emitter_reuse_is_rejected():
    first, second = make(), make()
    first.step()
    assert second.adapter.algorithm_unit is None and second.adapter.emitter.cursor == 0
    from nsgablack.adapters import CompositeAdapter
    emitter = SequenceEmitter(POINTS)
    left, right = make(emitter=emitter), make(emitter=emitter)
    solver = ComposableSolver(ArchiveProblem(), adapter=CompositeAdapter([left.adapter, right.adapter]))
    with pytest.raises(ValueError, match="multiple Adapter owners"):
        solver.setup()


def test_real_gaussian_emitter_uses_champion_sources_and_restores_rng():
    solver = make(emitter=GaussianArchiveEmitter(.02), batch_size=3)
    solver.setup()
    solver.step()
    baseline = solver.adapter.snapshot_step_state()
    first = solver.adapter.propose(solver, {})
    solver.adapter.restore_step_state(baseline)
    repeated = solver.adapter.propose(solver, {})
    np.testing.assert_array_equal(np.asarray([row.values for row in first]),
                                  np.asarray([row.values for row in repeated]))
    assert all(solver.candidate_provenance_for(row).parent_token is not None for row in first)


def test_gaussian_emitter_runs_multiple_commits_and_preserves_semantic_metadata():
    from blackbase.types import UnknownState
    class SemanticInitializer:
        def initialize(self, problem, context=None):
            return UnknownState([.4, .4], metadata={"shape": "recipe", "behavior": [.4, .4]})
    from nsgablack.representation import RepresentationPipeline
    solver = make(emitter=GaussianArchiveEmitter(.01), batch_size=3)
    # Direct initializer is used only by the ordinary initialization surface.
    original = solver.init_population
    solver.init_population = lambda count, context=None: tuple(
        solver.init_candidate(context, initializer=SemanticInitializer()) for _ in range(count))
    solver.setup()
    solver.step()
    solver.init_population = original
    assert solver.step().committed
    assert solver.evaluation_count == 6
    refs = solver.adapter.get_solution_pool_roots(solver)
    assert all(state.metadata["shape"] == "recipe"
               for state in solver.solution_pool.read(refs).semantic_states)


def test_descriptor_can_consume_evaluated_semantic_metadata():
    from blackbase.types import UnknownState
    class MetadataEmitter:
        stateless = True
        def checkpoint_identity(self):
            return {"kind": "test.semantic-emitter/v1"}
        def emit(self, archive, count, *, rng, control, context):
            return (UnknownState([.1, .1], metadata={"behavior": [.8, .8]}),)
    class MetadataDescriptor:
        stateless = True
        def checkpoint_identity(self):
            return {"kind": "test.semantic-descriptor/v1"}
        def describe(self, candidate, feedback):
            return candidate.metadata["behavior"]
    adapter = MapElitesAdapter(emitter=MetadataEmitter(), descriptor=MetadataDescriptor())
    solver = ComposableSolver(ArchiveProblem(), adapter=adapter)
    solver.step()
    assert archive(solver) == {(1, 1): [.1, .1]}


def test_empty_custom_emitter_is_idle_until_it_explicitly_declares_completion():
    class WaitingEmitter:
        stateless = True
        def checkpoint_identity(self):
            return {"kind": "test.waiting/v1"}
        def emit(self, archive, count, *, rng, control, context):
            return ()
    solver = make(emitter=WaitingEmitter())
    assert solver.step().status == "idle"
    finite = make(((.4, .4),))
    finite.step()
    assert finite.step().status == "terminal"


def test_public_checkpoint_file_restores_champions_and_only_evaluates_remaining_rows(tmp_path, monkeypatch):
    monkeypatch.setenv("NSGABLACK_CHECKPOINT_HMAC_KEY", "map-elites-semantic-test-key")
    def assembled():
        solver = make(batch_size=2)
        solver.set_max_steps(3)
        solver.add_plugin(CheckpointResumePlugin(config=CheckpointResumeConfig(
            checkpoint_dir=str(tmp_path), save_every=1, save_on_finish=False, keep_last=10, strict=True)))
        return solver
    source = assembled()
    source.run()
    checkpoint, = tmp_path.glob("*_g000000_*.pkl")
    target = assembled()
    assert target.get_plugin("checkpoint_resume").resume(str(checkpoint))
    target.run()
    assert source.evaluation_count == target.evaluation_count == 5
    assert target.problem.calls == 3
    assert archive(source) == archive(target)
    assert target.adapter.emitter.cursor == source.adapter.emitter.cursor == 5
    refs = target.adapter.get_population_solution_refs(target)
    assert target.solution_pool.subpool_refs("map_elites/archive") == refs
    np.testing.assert_array_equal(target.solution_pool.read(refs).numeric_matrix, target.population)


def test_standard_case_uses_effective_resource_context_and_real_components(tmp_path):
    allocator = ResourceAllocator()
    lease = allocator.acquire(ResourceRequest(threads=1, workers=1), owner_id="map_semantics_test", scope="optimization")
    try:
        grant = ResourceContext.from_mapping(lease.resource_context(namespace="algorithm_semantics"))
        solver = build_case(load_case_builder(PROJECT, "map_elites_archive"), resource_context=grant,
            component_overrides={"config": {"output_dir": str(tmp_path)}})
        assert isinstance(solver.adapter, MapElitesAdapter) and solver.adapter.algorithm_unit is None
        assert solver.resource_binding_audit["current"]
        run_case(solver)
        report = json.loads((tmp_path / "summary.json").read_text())
        assert report["evaluations"] == report["problem_calls"] == 5
        assert report["cells"] == [[0, 0], [1, 0], [1, 1]]
        np.testing.assert_allclose(report["costs"], [.2, .32, .16])
    finally:
        allocator.release(lease)
