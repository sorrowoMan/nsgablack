"""The workbench's main Case runs through the real build/Case/L0 entrypoints."""
from __future__ import annotations

import json
from pathlib import Path
import shutil

import numpy as np
import pytest
from blackbase.project import build_case, load_case_builder, run_case
from blackbase.resources import ResourceAllocator, ResourceContext, ResourceRequest
from nsgablack.plugins import CheckpointResumePlugin
from nsgablack.project.project_runner import execute_project


PROJECT = Path(__file__).resolve().parents[1] / "examples" / "cases" / "assembly_workbench"


@pytest.fixture
def grant():
    allocator = ResourceAllocator()
    lease = allocator.acquire(ResourceRequest(threads=1, workers=1),
                              owner_id="hybrid_workbench_test", scope="optimization")
    try:
        yield ResourceContext.from_mapping(lease.resource_context(namespace="assembly_workbench"))
    finally:
        allocator.release(lease)


def assemble(grant, output, **options):
    return build_case(load_case_builder(PROJECT, "hybrid_search"), resource_context=grant,
        component_overrides={"config": {"output_dir": str(output), **options}})


@pytest.mark.parametrize("mode", ["problem", "provider"])
def test_complete_hybrid_case_exercises_real_component_seams(tmp_path, grant, mode):
    output = tmp_path / mode
    solver = assemble(grant, output, evaluation_mode=mode)
    assert solver.adapter.units[0].adapter.inner.algorithm_unit is None
    assert solver.resource_binding_audit["current"] is True
    run_case(solver)
    trace = json.loads((output / "trace.json").read_text(encoding="utf-8"))
    assert trace["run_id"] == solver.run_session.run_id
    assert trace["initial"]["pool_records"] == 0
    assert trace["initial"]["ga_unit_exists"] is False
    assert solver.run_progress_steps == len(trace["records"]) == 14
    assert solver.evaluation_count == 36
    assert trace["final"]["problem_calls"] == (36 if mode == "problem" else 0)
    assert {tuple(record["phase"]) for record in trace["records"]} == {("ga",), ("vns",), ("return",)}
    assert all(record["authority_epoch"] is not None for record in trace["records"])
    # Pipeline.init 自带问题 repair，另外每个送评候选再走规范的提案修复。
    assert trace["final"]["repair"]["calls"] == solver.evaluation_count + 6
    assert trace["final"]["repair"]["changed"] > 0
    assert len(trace["final"]["member_refs"]) == 6
    assert len(trace["final"]["elite_refs"]) == 2
    assert len(trace["final"]["refined_selected_refs"]) == 2
    assert len(trace["final"]["member_age"]) == 6
    assert max(trace["final"]["member_age"]) > 0
    assert np.max(trace["final"]["raw_violations"]) <= 1e-9
    assert not np.array_equal(trace["final"]["raw_objectives"], trace["final"]["selection_objectives"])
    assert list((output / "checkpoints").glob("*.pkl"))
    provider_types = [entry["type"] for entry in trace["components"] if entry["path"] == "evaluation_provider"]
    assert provider_types == (["RecipeProvider"] if mode == "provider" else [])
    authority = solver.get_population_authority_identity()
    assert solver.snapshot_store.read_verified(authority.snapshot).data["solution_pool_ref"] == solver.solution_pool.publication_ref()


def test_hybrid_budget_can_cut_a_batch_without_faking_a_complete_plan(tmp_path, grant):
    solver = assemble(grant, tmp_path, evaluation_budget=11)
    run_case(solver)
    assert solver.evaluation_count == 11
    assert solver.evaluation_budget_reserved == 0
    assert solver.run_progress_steps == 2
    assert not solver.adapter.cursor.completed
    trace = json.loads((tmp_path / "trace.json").read_text(encoding="utf-8"))
    assert len(trace["records"]) == 2
    assert trace["final"]["evaluations"] == 11


def test_hybrid_configuration_rejects_a_nonexistent_evaluation_mode(tmp_path, grant):
    with pytest.raises(ValueError, match="evaluation_mode"):
        assemble(grant, tmp_path, evaluation_mode="guess")
    assert not (tmp_path / "trace.json").exists()


def test_hybrid_explicit_pipeline_codec_restores_rng_counters_and_continues_same_search(tmp_path, grant):
    source = assemble(grant, tmp_path / "source")
    source.setup()
    for _ in range(3):
        assert source.step().committed
    before = source.representation_pipeline.get_state()
    target = assemble(grant, tmp_path / "target")
    target.setup()
    writer, reader = CheckpointResumePlugin(), CheckpointResumePlugin()
    writer.cfg.strict = reader.cfg.strict = True
    writer.attach(source)
    reader.attach(target)
    payload = writer._build_payload(solver=source, reason="hybrid-explicit-pipeline-codec")
    assert payload["stateful_components"]["representation"]["state"] == before
    reader._restore_payload(solver=target, payload=payload)
    assert target.representation_pipeline.get_state() == before
    assert target.evaluation_count == source.evaluation_count
    assert target.problem.evaluation_count == 0
    normalize = lambda owner: json.loads(json.dumps(owner.get_state(), default=lambda value: value.tolist()))
    assert normalize(target.adapter) == normalize(source.adapter)
    for _ in range(3):
        assert source.step().committed and target.step().committed
        np.testing.assert_array_equal(source.population, target.population)
        np.testing.assert_array_equal(source.objectives, target.objectives)
    assert target.representation_pipeline.get_state() == source.representation_pipeline.get_state()
    assert target.adapter.cursor.get_state() == source.adapter.cursor.get_state()
    source_ga = source.adapter.units[0].adapter.inner
    target_ga = target.adapter.units[0].adapter.inner
    np.testing.assert_array_equal(source_ga.algorithm_unit.member_age, target_ga.algorithm_unit.member_age)


def test_real_project_group_publishes_the_hybrid_summary_with_an_authoritative_receipt(tmp_path):
    project = tmp_path / "project"
    shutil.copytree(PROJECT, project,
        ignore=shutil.ignore_patterns("results", "__pycache__", ".blackbase", "*.pyc"))
    result = execute_project(project, group="hybrid", record=False)
    assert result.ok, result.as_dict()
    case, = result.case_results
    assert case.request.case_name == "hybrid_search"
    assert "summary" in case.artifact_publications
    assert case.artifact_publications["summary"].artifact_name == "summary"
    assert result.artifact_bindings["hybrid_search.summary"].ref == case.artifact_refs["summary"]
    trace = json.loads((project / "results" / "hybrid_search" / "trace.json").read_text(encoding="utf-8"))
    assert trace["run_id"].startswith(case.identity.case_run_id + ":solver-run:")


def test_public_checkpoint_resume_reads_a_saved_file_and_only_runs_remaining_evaluations(tmp_path, grant):
    output = tmp_path / "checkpoint_file"
    source = assemble(grant, output)
    run_case(source)
    # keep_last retains step 8, step 12 and the final checkpoint. The g field
    # is zero-based generation; the payload cursor still records eight commits.
    checkpoint, = (output / "checkpoints").glob("*_g000007_*.pkl")
    target = assemble(grant, output)
    reader = target.get_plugin("checkpoint_resume")
    assert reader.resume(str(checkpoint)) is True
    run_case(target)
    assert target.run_progress_steps == 14 and target.evaluation_count == 36
    assert target.problem.evaluation_count == 12
    np.testing.assert_array_equal(target.population, source.population)
    np.testing.assert_array_equal(target.objectives, source.objectives)
    np.testing.assert_array_equal(target.adapter.units[0].adapter.inner.algorithm_unit.member_age,
                                  source.adapter.units[0].adapter.inner.algorithm_unit.member_age)
