"""The existing standard Project repeats one owned GA/VNS pair with real handoff."""
from pathlib import Path
import json
import shutil

import numpy as np
import pytest

from blackbase.project import build_case, load_case_builder, run_case
from blackbase.resources import ResourceAllocator, ResourceContext, ResourceRequest
from nsgablack.plugins import CheckpointResumeConfig, CheckpointResumePlugin
from nsgablack.project.project_runner import execute_project


OPTIONS = {"schedule": "plan", "rounds": 2, "population_size": 6, "ga_steps": 2,
           "local_steps": 2, "local_batch": 1, "refinement_source": "elite", "elite_count": 2}
PHASES = ["ga", "ga", "vns", "vns", "vns", "vns", "return"] * 2


@pytest.fixture(scope="module")
def project(tmp_path_factory):
    source = Path(__file__).resolve().parents[1] / "examples" / "cases" / "assembled_ga_vns"
    target = tmp_path_factory.mktemp("search_plan_project") / "project"
    shutil.copytree(source, target,
        ignore=shutil.ignore_patterns("results", "__pycache__", ".blackbase", "*.pyc"))
    return target


@pytest.fixture
def grant():
    allocator = ResourceAllocator()
    lease = allocator.acquire(ResourceRequest(threads=1, workers=1),
        owner_id="search_plan_project", scope="optimization")
    resource = ResourceContext.from_mapping(lease.resource_context(namespace="search_plan_project"))
    try:
        yield resource
    finally:
        allocator.release(lease)


def trace(solver):
    return next(item for item in solver.plugin_manager.list_plugins() if item.name == "committed_trace")


def build(project, grant):
    return build_case(load_case_builder(project, "hybrid_search"), resource_context=grant,
                      component_overrides={"config": OPTIONS})


def observe_calls(monkeypatch, solver):
    calls = []
    original = solver.problem.evaluate
    def evaluate(candidate):
        calls.append(np.array(candidate, copy=True))
        return original(candidate)
    monkeypatch.setattr(solver.problem, "evaluate", evaluate)
    return calls


def assert_rounds(records):
    assert [row["phase"] for row in records] == PHASES
    assert [row["logical_steps"] for row in records] == list(range(1, 15))
    requests = []
    for start in (0, 7):
        ga_end, first_vns, returned = records[start + 1], records[start + 2], records[start + 6]
        assert first_vns["frozen_refinement_refs"] == ga_end["elite"]["refs"]
        assert len(returned["selected_return"]) == 2
        assert len(returned["aggregate_return"]["refs"]) == (4 if start == 0 else 8)
        assert returned["source_raw_unchanged"] is True
        requests.append(first_vns["refinement_request"])
    assert requests[0] != requests[1]


def test_formal_project_build_check_and_two_round_handoff(project):
    checked = execute_project(project, group="plan", check=True, build_check=True)
    assert checked.ok
    result = execute_project(project, group="plan")
    assert result.ok and len(result.case_results) == 1
    case = result.case_results[0]
    assert case.resource_usage["binding"]["current"] is True
    assert case.output["report"]["evaluation_count"] == 36
    observed = json.loads((project / "results" / "plan" / "trace.json").read_text(encoding="utf-8"))
    assert_rounds(observed["records"])
    assert observed["final_summary"]["execution_plan"]["completed"] is True
    assert all(not unit["structure_exists"] and not unit["current_exists"]
               for unit in observed["initial"]["units"])
    assert not (project / "results" / "trace.json").exists()
    assert not (project / "results" / "elite" / "trace.json").exists()


@pytest.mark.parametrize("saved_steps", [5, 10])
def test_checkpoint_continues_current_round_and_only_returns_its_final_results(
        project, grant, tmp_path, monkeypatch, saved_steps):
    monkeypatch.setenv("NSGABLACK_CHECKPOINT_HMAC_KEY", "search-plan-project-resume-test")
    checkpoint_config = CheckpointResumeConfig(checkpoint_dir=str(tmp_path / "checkpoints"),
        save_every=5, save_on_finish=False, strict=True)
    source = build(project, grant)
    calls = observe_calls(monkeypatch, source)
    ga = source.adapter.units[0].adapter.inner
    owners = []
    returned_batches = []
    original_update = ga.update
    def updated(control, candidates, feedback, context):
        result = original_update(control, candidates, feedback, context)
        owners.append(id(ga.algorithm_unit))
        if context["phase"] == "return":
            returned_batches.append(np.array(candidates, copy=True))
        return result
    monkeypatch.setattr(ga, "update", updated)
    source.add_plugin(CheckpointResumePlugin(config=checkpoint_config))
    run_case(source)
    assert len(calls) == source.evaluation_count == 36
    assert source.run_progress_steps == 14
    assert source.run_progress_attempts == 15
    assert source.last_step_outcome["reason"] == "search_plan_completed"
    assert len(set(owners)) == 1 and len(returned_batches) == 2
    assert [len(batch) for batch in returned_batches] == [2, 2]
    assert_rounds(trace(source).records)
    saved = trace(source).records[saved_steps - 1]
    checkpoint, = (tmp_path / "checkpoints").glob(f"*_g{saved_steps - 1:06d}_*.pkl")

    restored = build(project, grant)
    restored_calls = observe_calls(monkeypatch, restored)
    initializer = restored.adapter.units[0].adapter.inner.get_bound_initializer()
    def no_new_population(*args, **kwargs):
        raise AssertionError("restoring a local activation must not initialize another GA population")
    monkeypatch.setattr(initializer, "initialize", no_new_population)
    reader = CheckpointResumePlugin(config=checkpoint_config)
    restored.add_plugin(reader)
    assert reader.resume(str(checkpoint))
    run_case(restored)
    assert restored.run_progress_steps == 14 and restored.evaluation_count == 36
    assert restored.adapter.cursor.completed
    assert len(restored_calls) == 36 - saved["evaluations"]
    np.testing.assert_array_equal(restored_calls, calls[saved["evaluations"]:])
    assert_rounds(trace(restored).records)
    assert trace(restored).records[:saved_steps] == trace(source).records[:saved_steps]
    np.testing.assert_array_equal(restored.adapter.units[0].adapter.inner.population, ga.population)
    np.testing.assert_array_equal(restored.adapter.units[0].adapter.inner.algorithm_unit.member_age,
                                  ga.algorithm_unit.member_age)
