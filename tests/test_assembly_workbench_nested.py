"""Real standard Case invocations keep response candidates and budgets separate."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from blackbase.project import execute_project
from blackbase.resources import ArtifactPublisher
from blackbase.types import SolverResult


SOURCE = Path(__file__).resolve().parents[1] / "examples/cases/assembly_workbench"


@pytest.fixture(scope="module")
def nested_project(tmp_path_factory):
    root = tmp_path_factory.mktemp("assembly_nested") / "assembly_workbench"
    (root / "cases").mkdir(parents=True)
    (root / "cases/__init__.py").write_text("", encoding="utf-8")
    shutil.copy2(SOURCE / "project_config.py", root / "project_config.py")
    for name in ("outer_nested", "inner_response"):
        shutil.copytree(SOURCE / "cases" / name, root / "cases" / name,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    result = execute_project(root, group="nested", run_id="nested-case-proof", record=False)
    return root, result


def read_artifact(case_result, name):
    from blackbase.resources import ArtifactBinding
    receipt = case_result.artifact_publications[name]
    reader = ArtifactPublisher.from_resource_context(case_result.request.resource_context,
        project_run_id=receipt.project_run_id, case_run_id=receipt.case_run_id)
    return json.loads(reader.read_verified(ArtifactBinding(
        ref=case_result.artifact_refs[name], publication=receipt)))


def test_real_nested_case_returns_evaluated_response_not_outer_candidate(nested_project):
    root, project = nested_project
    assert project.ok, project.as_dict()
    assert len(project.case_results) == 1
    outer = project.case_results[0]
    report = read_artifact(outer, "nested_report")
    assert report["summary"]["evaluation_count"] == 4
    assert report["summary"]["committed_steps"] == 2
    assert report["baseline_inputs"]["source"] == "builtin"
    assert report["baseline_inputs"]["bindings"] == {}
    assert len(report["calls"]) == 4
    for call in report["calls"]:
        x, y = call["outer_candidate"][0], call["best_response"]
        assert y == pytest.approx(x + .25)
        assert call["inner_loss"] == pytest.approx((y - x) ** 2)
        assert call["outer_objective"] == pytest.approx(call["inner_loss"] + .05 * x*x)
        assert call["inner_summary"]["evaluation_count"] == 2
        assert call["inner_summary"]["committed_steps"] == 2
    assert (root / "results/outer_nested/nested_report.json").is_file()


def test_nested_identity_resource_grants_budgets_and_artifacts_are_authoritative(nested_project):
    _, project = nested_project
    assert project.ok, project.as_dict()
    outer = project.case_results[0]
    report = read_artifact(outer, "nested_report")
    pools = {report["summary"]["pool_id"]}
    child_ids = set()
    for call in report["calls"]:
        identity = call["identity"]
        assert identity["parent_case_run_id"] == outer.identity.case_run_id
        assert identity["root_run_id"] == outer.identity.root_run_id
        assert identity["depth"] == outer.identity.depth + 1
        child_ids.add(identity["case_run_id"])
        assert call["resource_grant"]["threads"] <= call["parent_resource_grant"]["threads"]
        assert call["resource_grant"]["workers"] <= call["parent_resource_grant"]["workers"]
        assert call["resource_binding_current"] is True
        usage = call["budget_usage"]["evaluations"]
        assert usage["settlement_status"] == "settled"
        assert usage["committed"] == usage["charged_to_parent"] == 2
        assert usage["returned_to_parent"] == 0
        assert call["artifact_publication"]["metadata"]["case_finalization_sealed"] is True
        assert call["artifact_publication"]["case_run_id"] == identity["case_run_id"]
        pools.add(call["inner_summary"]["pool_id"])
    assert len(child_ids) == 4 and len(pools) == 5
    assert outer.artifact_publications["nested_report"].metadata["case_finalization_sealed"] is True
    assert "outer_nested.summary" in project.artifact_registry


def test_local_trace_uses_formal_solver_run_identity(nested_project):
    root, project = nested_project
    assert project.ok, project.as_dict()
    outer = project.case_results[0]
    trace = json.loads((root / "results/outer_nested/trace.json").read_text(encoding="utf-8"))
    assert trace["run_id"].startswith(outer.identity.case_run_id + ":solver-run:")
    assert len(trace["records"]) == 2
    report = read_artifact(outer, "nested_report")
    for index, call in enumerate(report["calls"]):
        inner_trace = json.loads((root / f"results/outer_nested/inner_calls/call_{index:03d}/trace.json")
                                 .read_text(encoding="utf-8"))
        assert inner_trace["run_id"].startswith(call["identity"]["case_run_id"] + ":solver-run:")
        assert len(inner_trace["records"]) == 2


def test_inner_case_runs_independently_and_payload_is_required_at_the_input_boundary(tmp_path):
    from examples.cases.assembly_workbench.cases.inner_response.build_solver import build_solver
    case = build_solver(component_overrides={"output_dir": str(tmp_path)})
    case.set_case_inputs({"inner_task_payload": {"target": -.75, "source": "test"}})
    output = case.export_case_result(case.run())
    result = SolverResult.from_dict(output.as_dict())
    assert result.metadata["summary"]["best_response"] == pytest.approx(-.5)
    assert result.metadata["summary"]["artifact_source"] == "standalone"
    with pytest.raises(ValueError, match="inner_task_payload"):
        case.set_case_inputs({"candidate": [0.]})


def test_case_clis_build_and_run_independently_with_the_formal_project_runtime(tmp_path):
    root = tmp_path / "standalone_cli"
    (root / "cases").mkdir(parents=True)
    (root / "cases/__init__.py").write_text("", encoding="utf-8")
    shutil.copy2(SOURCE / "project_config.py", root / "project_config.py")
    for name in ("outer_nested", "inner_response"):
        shutil.copytree(SOURCE / "cases" / name, root / "cases" / name,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1]) + os.pathsep + env.get("PYTHONPATH", "")
    for name in ("inner_response", "outer_nested"):
        for args in (["--check"], []):
            completed = subprocess.run([sys.executable, str(root / "cases" / name / "run_solver.py"), *args],
                cwd=root, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
            assert completed.returncode == 0, completed.stdout + completed.stderr
    outer = json.loads((root / "results/outer_nested/nested_report.json").read_text(encoding="utf-8"))
    assert outer["summary"]["baseline_source"] == "builtin"
    assert outer["summary"]["resource_binding_current"] is True
    assert len(outer["calls"]) == 4
