"""Actual Project stages, Artifact handoff and the tutorial report agree."""
from pathlib import Path
import importlib.util
import json
import shutil

import pytest

from nsgablack.project.project_runner import execute_project


@pytest.fixture(scope="module")
def workbench(tmp_path_factory):
    source = Path(__file__).resolve().parents[1] / "examples/cases/assembly_workbench"
    target = tmp_path_factory.mktemp("assembly_workbench") / "project"
    shutil.copytree(source, target,
        ignore=shutil.ignore_patterns("results", "__pycache__", ".blackbase", "*.pyc"))
    return target


@pytest.fixture(scope="module")
def actual_run(workbench):
    result = execute_project(workbench)
    assert result.ok, result.as_dict()
    return result


def report_module(project):
    spec = importlib.util.spec_from_file_location("assembly_workbench_report", project / "run_and_report.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_project_build_check_includes_the_actual_three_root_cases(workbench):
    result = execute_project(workbench, check=True, build_check=True)
    assert result.ok, result.as_dict()
    observed = {case.request.case_name: case.metadata["runtime_state"] for case in result.case_results}
    assert set(observed) == {"hybrid_search", "directions", "outer_nested"}
    assert observed["hybrid_search"]["adapter"] == "SearchPlanAdapter"
    assert observed["directions"]["adapter"] == "SearchPlanAdapter"
    assert all(row["case_class"] for row in observed.values())


def test_parallel_roots_publish_before_outer_consumes_the_exact_bindings(actual_run):
    cases = {case.request.case_name: case for case in actual_run.case_results}
    upstream = [cases["hybrid_search"], cases["directions"]]
    outer = cases["outer_nested"]
    assert outer.started_at >= max(case.finished_at for case in upstream)
    assert len({case.resource_usage["effective_context"]["namespace"] for case in cases.values()}) == 3
    assert all(case.resource_usage["binding"]["current"] for case in cases.values())
    for alias, key in {"hybrid_summary": "hybrid_search.summary",
                       "directions_summary": "directions.summary"}.items():
        binding = actual_run.artifact_bindings[key]
        assert outer.request.input_artifact_bindings[alias] == binding
        assert outer.request.input_artifacts[alias] == binding.ref
    assert all("summary" in case.artifact_publications for case in cases.values())
    assert "nested_report" in outer.artifact_publications


def test_readonly_report_uses_this_run_and_rejects_a_stale_trace(workbench, actual_run):
    reporter = report_module(workbench)
    summary = reporter.summarize(actual_run.as_dict(), wall_seconds=0.)
    assert summary["project_run_id"] == actual_run.run_id
    assert summary["topology"]["upstream_artifacts_verified"]
    assert summary["topology"]["downstream_after_both"]
    trace_path = workbench / "results/hybrid_search/trace.json"
    previous = trace_path.read_text(encoding="utf-8")
    stale = json.loads(previous)
    stale["run_id"] = "older-case:solver-run:1"
    try:
        trace_path.write_text(json.dumps(stale), encoding="utf-8")
        with pytest.raises(ValueError, match="older/different run"):
            reporter.summarize(actual_run.as_dict(), wall_seconds=0.)
    finally:
        trace_path.write_text(previous, encoding="utf-8")


def test_dag_group_derives_the_same_case_dependencies(workbench):
    result = execute_project(workbench, group="dag")
    assert result.ok, result.as_dict()
    cases = {case.request.case_name: case for case in result.case_results}
    assert set(cases) == {"hybrid_search", "directions", "outer_nested"}
    outer = cases["outer_nested"]
    assert outer.started_at >= max(cases[name].finished_at for name in ("hybrid_search", "directions"))
    assert set(outer.request.input_artifact_bindings) == {"hybrid_summary", "directions_summary"}


@pytest.mark.parametrize("group,name,steps,evaluations", [
    ("provider", "hybrid_search", 14, 36),
    ("random_directions", "directions", 11, 18),
    ("parallel_refiners", "directions", 9, 27),
])
def test_named_variants_use_real_project_overrides_and_publish_results(
        workbench, group, name, steps, evaluations):
    result = execute_project(workbench, group=group)
    assert result.ok, result.as_dict()
    case, = result.case_results
    assert case.request.case_name == name
    assert case.output["report"]["steps"] == steps
    assert case.output["report"]["evaluation_count"] == evaluations
    assert f"{name}.summary" in result.artifact_bindings
    assert case.artifact_publications["summary"].metadata["case_finalization_sealed"] is True
    if group == "provider":
        state = case.metadata["runtime_state"]
        assert tuple(state["provider_names"]) == ("recipe_vectorized",)
        trace = json.loads((workbench / "results/hybrid_search/trace.json").read_text(encoding="utf-8"))
        assert trace["final"]["problem_calls"] == 0
