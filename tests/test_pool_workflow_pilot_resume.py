"""Resume the actual assembled pilot Cases through public Case and checkpoint APIs."""
from __future__ import annotations

from pathlib import Path
import shutil

import numpy as np
import pytest

from blackbase.project import build_case, load_case_builder
from blackbase.resources import ResourceAllocator, ResourceContext, ResourceRequest
from nsgablack.plugins import CheckpointResumeConfig, CheckpointResumePlugin


@pytest.fixture(scope="module")
def pilot_project(tmp_path_factory):
    # WorkflowTrace intentionally publishes beside its Project. Run an exact
    # source copy so this test never overwrites checked-in demonstration output.
    source = Path(__file__).resolve().parents[1] / "examples" / "cases" / "pool_workflow_pilot"
    destination = tmp_path_factory.mktemp("pool_workflow_resume") / "project"
    shutil.copytree(source, destination,
        ignore=shutil.ignore_patterns("results", "__pycache__", ".blackbase", "*.pyc"))
    return destination


def plugin(solver, name):
    return next(item for item in solver.plugin_manager.list_plugins() if item.name == name)


def leaf(solver):
    return solver.adapter.units[0].adapter.inner


def evaluated_inputs(monkeypatch, solver):
    seen = []
    original = solver.problem.evaluate

    def evaluate(candidate):
        seen.append(np.array(candidate, copy=True))
        return original(candidate)

    monkeypatch.setattr(solver.problem, "evaluate", evaluate)
    return seen


def result_refs(solver, case_name):
    worker = leaf(solver)
    return (worker.get_population_solution_refs(solver) if case_name != "vns_search"
            else worker.get_pool_refinement_results(solver))


@pytest.mark.parametrize("case_name", ["vns_search", "moead_search", "ga_search"])
def test_formal_pilot_case_resume_never_replays_source_and_preserves_change(
    pilot_project, tmp_path, monkeypatch, case_name,
):
    monkeypatch.setenv("NSGABLACK_CHECKPOINT_HMAC_KEY", "pool-workflow-formal-resume-test")
    allocator = ResourceAllocator()
    lease = allocator.acquire(ResourceRequest(threads=1, workers=1),
        owner_id=case_name, scope="pool_workflow_resume")
    resource = ResourceContext.from_mapping(
        lease.resource_context(namespace=f"pool_workflow_resume.{case_name}"))
    config = CheckpointResumeConfig(checkpoint_dir=str(tmp_path / "checkpoints"),
        save_every=3, save_on_finish=False, strict=True)
    try:
        source = build_case(load_case_builder(pilot_project, case_name), resource_context=resource)
        assert source.resource_binding_audit["current"] is True
        assert source.resource_context.lease["lease_id"] == lease.lease_id
        original_identity = leaf(source).get_local_operator_bindings()["change"].get_state()["identity"]
        source_values = evaluated_inputs(monkeypatch, source)
        initializations = []
        initializer = source.representation_pipeline.initializer
        initialize = initializer.initialize

        def record_initialize(problem, context=None):
            value = initialize(problem, context)
            initializations.append(np.array(value, copy=True))
            return value

        monkeypatch.setattr(initializer, "initialize", record_initialize)
        source.add_plugin(CheckpointResumePlugin(config=config))
        source.run(max_steps=6)
        assert source.run_progress_steps == 6
        source_plugin = plugin(source, "pipeline_source")
        assert len(initializations) == source_plugin.count
        initial_refs = source.solution_pool.select(stage="initial")
        assert len(initial_refs) == source_plugin.count
        saved_evaluations = plugin(source, "workflow_trace").records[2]["evaluations"]
        # Filenames use the zero-based generation index; completed logical
        # steps, which determine save_every, are already three here.
        checkpoint, = tuple((tmp_path / "checkpoints").glob("*_g000002_*.pkl"))

        # Re-import the canonical Case to exercise module/ordinary-function
        # identity stability, rather than restoring into the original object.
        restored = build_case(load_case_builder(pilot_project, case_name), resource_context=resource)
        assert leaf(restored) is not leaf(source)
        assert leaf(restored).get_local_operator_bindings()["change"].get_state()["identity"] == original_identity
        restored_values = evaluated_inputs(monkeypatch, restored)

        def source_must_not_restart(*args, **kwargs):
            raise AssertionError("a restored Pipeline source must not generate new seeds")

        monkeypatch.setattr(restored.representation_pipeline.initializer,
                            "initialize", source_must_not_restart)
        reader = CheckpointResumePlugin(config=config)
        restored.add_plugin(reader)
        assert reader.resume(str(checkpoint))
        restored.run(max_steps=6)

        assert restored.run_progress_steps == source.run_progress_steps == 6
        assert restored.evaluation_count == source.evaluation_count
        np.testing.assert_array_equal(restored_values, source_values[saved_evaluations:])
        assert restored.run_session.run_id == source.run_session.run_id
        assert restored.solution_pool.timestamp.run_id == source.run_session.run_id
        assert plugin(restored, "pipeline_source").get_state() == source_plugin.get_state()
        assert restored.solution_pool.select(stage="initial") == initial_refs
        # Checkpoint references retain their exact identities. New continuation
        # proposals use fresh UUIDs, so compare their selected values/feedback,
        # rather than requiring two independent continuations to reuse IDs.
        assert plugin(restored, "workflow_trace").records[2]["elite"] == plugin(source, "workflow_trace").records[2]["elite"]
        restored_elite = restored.solution_pool.subpool_refs("elite")
        source_elite = source.solution_pool.subpool_refs("elite")
        np.testing.assert_array_equal(restored.read_solutions(restored_elite).numeric_matrix,
                                      source.read_solutions(source_elite).numeric_matrix)
        for actual_raw, expected_raw in zip(restored.solution_pool.read_raw_feedback(restored_elite),
                source.solution_pool.read_raw_feedback(source_elite), strict=True):
            np.testing.assert_array_equal(actual_raw, expected_raw)
        assert restored.solution_pool.subpool_descriptor("elite") == source.solution_pool.subpool_descriptor("elite")
        assert leaf(restored).get_local_operator_bindings()["change"].get_state()["identity"] == original_identity

        expected_refs, actual_refs = result_refs(source, case_name), result_refs(restored, case_name)
        expected = source.read_solutions(expected_refs).numeric_matrix
        actual = restored.read_solutions(actual_refs).numeric_matrix
        np.testing.assert_array_equal(actual, expected)
        for expected_view, actual_view in zip(
            source.solution_pool.read_raw_feedback(expected_refs),
            restored.solution_pool.read_raw_feedback(actual_refs), strict=True,
        ):
            np.testing.assert_array_equal(actual_view, expected_view)
        provenance = restored.solution_pool.read_provenance(actual_refs)
        assert all(record["source_run_id"] == source.run_session.run_id for record in provenance)
        if case_name == "vns_search":
            assert leaf(restored).current_unit.unit_id == leaf(source).current_unit.unit_id
            assert leaf(restored).current_score == leaf(source).current_score
        else:
            assert leaf(restored).get_unit_id() == leaf(source).get_unit_id()
            if case_name == "moead_search":
                np.testing.assert_array_equal(leaf(restored).weights, leaf(source).weights)
                np.testing.assert_array_equal(leaf(restored).ideal, leaf(source).ideal)
            else:
                assert leaf(restored).get_bound_selector().checkpoint_identity() == leaf(source).get_bound_selector().checkpoint_identity()
    finally:
        allocator.release(lease)
