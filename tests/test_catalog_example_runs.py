"""Catalog execution evidence must stay bound to fixed commands and real runs."""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("catalog_example_receipts", ROOT / "deployment/catalog/run_example_receipts.py")
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def _record(root, *, command="python examples/cases/catalog_codec_demo/run_project.py"):
    source = root / "examples/cases/catalog_codec_demo/project_config.py"
    return {
        "id": "ml-linear-point", "run_command": command, "working_directory": "mlblack",
        "publication_digest": "a" * 64, "source_digest": "b" * 64,
        "source_files": {"mlblack/examples/cases/catalog_codec_demo/project_config.py": hashlib.sha256(source.read_bytes()).hexdigest()},
    }


def test_catalog_commands_cannot_authorize_execution(tmp_path, monkeypatch):
    roots = {"mlblack": tmp_path}
    (tmp_path / "examples/cases/catalog_codec_demo").mkdir(parents=True)
    (tmp_path / "examples/cases/catalog_codec_demo/project_config.py").write_text("L0 = {}", encoding="utf-8")
    record = _record(tmp_path, command="python private.py")
    monkeypatch.setattr(RUNNER.subprocess, "run", lambda *a, **k: pytest.fail("untrusted command executed"))
    with pytest.raises(ValueError, match="allowlisted_command_missing_or_changed"):
        RUNNER.run_preset("ml-linear-point", roots, {"publication_digest": "a" * 64, "examples": {record["id"]: record}}, timeout=10)
    with pytest.raises(ValueError, match="example_not_allowlisted"):
        RUNNER.run_preset("new-ai-command", roots, {}, timeout=10)


def test_source_changed_since_index_is_rejected_before_run(tmp_path, monkeypatch):
    project = tmp_path / "examples/cases/catalog_codec_demo"
    project.mkdir(parents=True)
    source = project / "project_config.py"
    source.write_text("L0 = {}", encoding="utf-8")
    record = _record(tmp_path)
    source.write_text("L0 = {'changed': True}", encoding="utf-8")
    monkeypatch.setattr(RUNNER.subprocess, "run", lambda *a, **k: pytest.fail("changed source executed"))
    with pytest.raises(ValueError, match="source_changed_since_index"):
        RUNNER.run_preset("ml-linear-point", {"mlblack": tmp_path},
                          {"publication_digest": "a" * 64, "examples": {record["id"]: record}}, timeout=10)


def test_source_paths_and_old_results_cannot_escape_or_be_copied(tmp_path):
    root, target = tmp_path / "source", tmp_path / "copy"
    root.mkdir()
    (root / "run_project.py").write_text("pass", encoding="utf-8")
    (root / "results").mkdir()
    (root / "results/old.json").write_text("{}", encoding="utf-8")
    (root / ".blackbase").mkdir()
    (root / ".blackbase/old.json").write_text("{}", encoding="utf-8")
    RUNNER._copy_project(root, target)
    assert (target / "run_project.py").is_file()
    assert not (target / "results").exists()
    assert not (target / ".blackbase").exists()
    with pytest.raises(ValueError, match="source_path_invalid"):
        RUNNER._source_path({"mlblack": root}, "mlblack/../private.py")


def test_failed_or_unbound_case_cannot_yield_execution_observations(tmp_path):
    with pytest.raises(ValueError, match="case_did_not_succeed"):
        RUNNER._case_observations({"status": "failed", "exit_code": 1}, project=tmp_path,
                                  case_name="linear_point", preset="ml-linear-point")
    with pytest.raises(ValueError, match="case_resource_binding_not_current"):
        RUNNER._case_observations({"status": "succeeded", "exit_code": 0}, project=tmp_path,
                                  case_name="linear_point", preset="ml-linear-point")


def test_real_numpy_ml_project_runs_without_modifying_source():
    mlroot = ROOT.parent / "mlblack"
    project = mlroot / "examples/cases/catalog_codec_demo"
    if not project.is_dir():
        pytest.skip("sibling mlblack showcase not available")
    record = _record(mlroot)
    sources = list(project.rglob("*.py"))
    before = {str(p): p.read_bytes() for p in sources}
    receipts = RUNNER.run_preset("ml-linear-point", {"mlblack": mlroot, "nsgablack": ROOT},
                                 {"publication_digest": "a" * 64, "examples": {record["id"]: record}}, timeout=60)
    assert len(receipts) == 1 and receipts[0]["exit_code"] == 0
    assert any("Committed ML steps=3" in line for line in receipts[0]["observed_outputs"])
    assert any("linear_point" in line for line in receipts[0]["observed_outputs"])
    assert any("Artifact checksum=sha256:" in line for line in receipts[0]["observed_outputs"])
    assert before == {str(p): p.read_bytes() for p in sources}


def test_fixed_receipt_requires_actual_pool_feedback_and_case_result_to_agree(tmp_path):
    case = {"status": "succeeded", "exit_code": 0,
            "resource_usage": {"binding": {"current": True}},
            "metadata": {"runtime_state": {"adapter": "FixedCandidateAdapter"}},
            "output": {"report": {"steps": 1, "evaluation_count": 1}, "best_objectives": [0.625]}}
    actual = {"steps": 1, "evaluations": 1, "accepted_refs": 1, "candidates": [[0.25, 0.75]],
              "raw_objectives": [[0.625]], "raw_violations": [0.0]}
    lines = RUNNER._case_observations(case, project=tmp_path, case_name="fixed", preset="fixed-candidate",
                                      fixed_report=actual)
    assert any("raw objective=0.625" in line for line in lines)
    for field, value in (("raw_violations", [1.0]), ("accepted_refs", 0), ("candidates", [[0.0, 0.0]])):
        with pytest.raises(ValueError, match="fixed_candidate_result_mismatch"):
            RUNNER._case_observations(case, project=tmp_path, case_name="fixed", preset="fixed-candidate",
                                      fixed_report={**actual, field: value})
    with pytest.raises(ValueError, match="fixed_candidate_result_mismatch"):
        RUNNER._case_observations(case, project=tmp_path, case_name="fixed", preset="fixed-candidate")


def test_real_fixed_project_receipt_uses_fresh_standard_project_run():
    project = ROOT / "examples/cases/catalog_fixed_candidate"
    source = project / "project_config.py"
    record = {"id": "fixed-candidate-project", "working_directory": "nsgablack",
              "run_command": "python examples/cases/catalog_fixed_candidate/run_project.py",
              "publication_digest": "a" * 64, "source_digest": "b" * 64,
              "source_files": {"nsgablack/examples/cases/catalog_fixed_candidate/project_config.py":
                               hashlib.sha256(source.read_bytes()).hexdigest()}}
    receipts = RUNNER.run_preset("fixed-candidate", {"nsgablack": ROOT},
        {"publication_digest": "a" * 64, "examples": {record["id"]: record}}, timeout=60)
    assert len(receipts) == 1 and receipts[0]["exit_code"] == 0
    assert any("one committed step and one evaluation" in line for line in receipts[0]["observed_outputs"])
