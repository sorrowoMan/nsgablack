"""Portable production sources use declared receipts, never sender paths."""
from copy import deepcopy
import importlib
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

import numpy as np
import pytest

from blackbase.project import build_case, case_import_context, execute_project, load_case_builder
from blackbase.resources import ArtifactBinding, ArtifactPublisher
from tests.test_production_inner_case import small_task, SUPPLY_PROJECT, PRODUCTION_CASE


@pytest.fixture
def portable_sources(tmp_path, small_task, monkeypatch):
    import tempfile
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    monkeypatch.setenv("TEMP", str(scratch))
    monkeypatch.setenv("TMP", str(scratch))
    monkeypatch.setattr(tempfile, "tempdir", str(scratch))
    monkeypatch.setenv("NSGABLACK_PRODUCTION_CASE_DIR", str(PRODUCTION_CASE))
    task, bom, adjusted = small_task
    root = tmp_path / "portable"
    (root / "cases").mkdir(parents=True)
    (root / "cases/__init__.py").write_text("", encoding="utf-8")
    for name in ("production_sources", "production_inner", "supply_adjustment_nested"):
        shutil.copytree(SUPPLY_PROJECT / "cases" / name, root / "cases" / name,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    options = {"bom": task["source"]["bom"]["path"], "supply": task["source"]["supply"]["path"],
               "machines": 8, "materials": 3, "production_case_dir": str(PRODUCTION_CASE)}
    config = '''
PROJECT_NAME = "portable"
L0 = {"namespace": "portable", "offer": {"threads": 1},
      "policy": {"mode": "strict", "max_workers": 1, "max_threads": 1},
      "default_request": {"workers": 1, "threads": 1, "memory_mb": 512,
                          "capabilities": ["production_inner", "nested_eval"]},
      "lease_backend": "sqlite", "lease_path": ".blackbase/leases.sqlite",
      "budgets": {"evaluations": 33, "audit_evaluations": 1}}
STAGES = [{"name": "sources", "cases": ["production_sources"], "component_overrides": {
    "production_sources": OPTIONS}}]
GROUPS = {"default": {"stages": ["sources"]}}
'''.replace("OPTIONS", repr(options))
    (root / "project_config.py").write_text(config, encoding="utf-8")
    result = execute_project(root, record=False)
    assert result.ok, result.as_dict()
    producer = result.case_results[0]
    bindings = {name: ArtifactBinding(producer.artifact_refs[name], producer.artifact_publications[name])
                for name in ("bom", "supply")}
    reader = ArtifactPublisher.from_resource_context(producer.request.resource_context,
        project_run_id=producer.identity.project_run_id, case_run_id=producer.identity.case_run_id)
    with case_import_context(root, "production_inner"):
        contract = importlib.import_module("cases.production_inner.runtime.task_contract")
        portable = {**deepcopy(task), "schema": contract.PORTABLE_TASK_SCHEMA,
                    "code_manifest": contract.production_code_manifest(PRODUCTION_CASE)}
    portable.pop("production_case_dir")
    portable["inner_config"]["max_evaluations"] = 32
    portable["source"] = {name: {"sha256": task["source"][name]["sha256"],
                               "suffix": ".csv", "binding": bindings[name].as_dict()}
                          for name in ("bom", "supply")}
    return SimpleNamespace(root=root, task=portable, old=task, reader=reader, bindings=bindings,
                           bom=bom, adjusted=adjusted, config=config)


def test_portable_task_materializes_original_data_and_deletes_temporary_files(portable_sources):
    fixture = portable_sources
    for value in fixture.old["source"].values():
        Path(value["path"]).unlink()
    with case_import_context(fixture.root, "production_inner"):
        contract = importlib.import_module("cases.production_inner.runtime.task_contract")
        prepared = contract.prepare_task(fixture.task, publisher=fixture.reader)
    np.testing.assert_array_equal(prepared.outer_problem.bom_matrix, fixture.bom)
    np.testing.assert_array_equal(prepared.adjusted_supply, fixture.adjusted)
    assert prepared.task["source"] == fixture.task["source"]
    assert not list((fixture.root.parent / "scratch").glob("production-inputs-*"))
    assert "production_case_dir" not in prepared.task


@pytest.mark.parametrize("damage", ["source_sha", "receipt_scope", "manifest", "sender_path", "format"])
def test_portable_task_rejects_wrong_identity_before_solver_run(portable_sources, damage):
    fixture = portable_sources
    task = deepcopy(fixture.task)
    if damage == "source_sha":
        task["source"]["bom"]["sha256"] = "0" * 64
    elif damage == "receipt_scope":
        task["source"]["bom"]["binding"]["publication"]["authority_namespace"] = "other"
    elif damage == "manifest":
        task["code_manifest"]["files"]["problem/production_problem.py"] = "0" * 64
    elif damage == "format":
        task["source"]["bom"]["suffix"] = ".xlsx"
    else:
        task["production_case_dir"] = str(PRODUCTION_CASE)
    with case_import_context(fixture.root, "production_inner"):
        contract = importlib.import_module("cases.production_inner.runtime.task_contract")
        with pytest.raises((ValueError, RuntimeError)):
            contract.prepare_task(task, publisher=fixture.reader)


def test_build_and_observation_do_not_download_or_construct_unit(portable_sources):
    fixture = portable_sources
    case = build_case(load_case_builder(fixture.root, "production_inner"),
        resource_context={"threads": 1}, component_overrides={"task": fixture.task})
    class Reader:
        def read_verified(self, binding):
            raise AssertionError("build and observation must not download")
    runtime = SimpleNamespace(request=SimpleNamespace(input_artifact_bindings=fixture.bindings), artifact_publisher=Reader())
    case.set_input_artifacts({name: binding.ref for name, binding in fixture.bindings.items()})
    case.set_case_inputs({"candidate": [1, 2], "candidate_provenance": {"candidate_token": fixture.task["candidate_token"]}})
    case.set_case_runtime(runtime)
    assert case._case is None and getattr(case, "adapter", None) is None
    case.close()


def test_task_binding_must_match_the_formal_input_before_any_read(portable_sources):
    fixture = portable_sources
    case = build_case(load_case_builder(fixture.root, "production_inner"),
        resource_context={"threads": 1}, component_overrides={"task": fixture.task})
    class Reader:
        def read_verified(self, binding):
            raise AssertionError("undeclared input must not be read")
    case.set_case_runtime(SimpleNamespace(request=SimpleNamespace(input_artifact_bindings={}), artifact_publisher=Reader()))
    case.set_case_inputs({"candidate": [1, 2]})
    with pytest.raises(ValueError, match="declared"):
        case.run()


def test_external_legacy_task_is_rejected_before_local_file_access(small_task):
    task = deepcopy(small_task[0])
    task["source"]["bom"]["path"] = "missing-sender-file.csv"
    with pytest.raises(ValueError, match="portable"):
        build_case(load_case_builder(SUPPLY_PROJECT, "production_inner"),
                   resource_context={"threads": 1, "metadata": {"external_target": "other-host"}},
                   component_overrides={"task": task})


def test_full_supply_case_passes_sources_and_receipts_after_original_files_disappear(portable_sources):
    fixture = portable_sources
    # Delete coordinator-local inputs after the outer Problem has been built.
    # The actual isolated child and final audits must rely on Artifact bytes.
    wrapper = fixture.root / "cases/supply_adjustment_nested/solver/joint_case.py"
    text = wrapper.read_text(encoding="utf-8")
    text = text.replace("self.solver.set_case_runtime(runtime)",
        "self.solver.set_case_runtime(runtime)\n"
        "        from pathlib import Path\n"
        "        for source in self.solver.supply_source.values():\n"
        "            Path(source['path']).unlink(missing_ok=True)")
    wrapper.write_text(text, encoding="utf-8")
    argv = ["--bom", fixture.old["source"]["bom"]["path"], "--supply", fixture.old["source"]["supply"]["path"],
        "--production-case-dir", str(PRODUCTION_CASE), "--machines", "8", "--materials", "3",
        "--evaluation-only", "--portable-inputs", "--inner-pop-size", "8", "--inner-generations", "1",
        "--inner-max-evaluations", "32", "--inner-memory-mb", "384", "--no-decision-trace", "--no-profiler"]
    config = fixture.config + "\nSTAGES.append(" + repr({"name": "outer", "cases": ["supply_adjustment_nested"],
        "timeout_seconds": 120, "component_overrides": {"supply_adjustment_nested": {"argv": argv, "candidate": [1, 2]}},
        "input_artifacts": {"supply_adjustment_nested": {"bom": "sources.production_sources.bom",
                                                         "supply": "sources.production_sources.supply"}}}) + ")\nGROUPS['default']['stages'].append('outer')\n"
    (fixture.root / "project_config.py").write_text(config, encoding="utf-8")
    result = execute_project(fixture.root, record=False)
    assert result.ok, result.as_dict()
    outer = result.case_results[-1]
    reader = ArtifactPublisher.from_resource_context(outer.request.resource_context,
        project_run_id=outer.identity.project_run_id, case_run_id=outer.identity.case_run_id)
    binding = ArtifactBinding(outer.artifact_refs["joint_summary"], outer.artifact_publications["joint_summary"])
    summary = json.loads(reader.read_verified(binding))
    assert summary["schema"] == "supply_adjustment_nested.joint_summary/v2"
    assert summary["production_summary"]["schema"] == "supply_adjustment_nested.production_summary/v2"
    assert summary["shifts"] == [1, 2] and summary["day0_max_abs_delta"] == 0
    assert len(summary["production_raw_objectives"]) == 5
    assert summary["inner_budget_usage"]["evaluations"]["committed"] <= 32
    assert all("path" not in summary["source"][name] for name in ("bom", "supply"))
