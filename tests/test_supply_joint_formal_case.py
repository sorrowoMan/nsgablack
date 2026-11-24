"""供应候选 -> 正式生产 Case -> sealed summary -> 原始三目标。"""

import importlib
import json
from pathlib import Path
import shutil

import numpy as np
import pandas as pd

from blackbase.project import execute_project
from blackbase.resources import ArtifactBinding, ArtifactPublisher
from blackbase.wire import thaw_wire_mapping


REPO = Path(__file__).resolve().parents[1]
PROJECT = REPO / "examples/cases/supply_adjustment_nested"
PRODUCTION = REPO / "examples/cases/production_scheduling/cases/production_scheduling"


def make_project(tmp_path, *, evaluation_only=True):
    root = tmp_path / "joint"
    (root / "cases").mkdir(parents=True)
    (root / "cases/__init__.py").write_text("", encoding="utf-8")
    for name in ("production_inner", "supply_adjustment_nested"):
        shutil.copytree(PROJECT / "cases" / name, root / "cases" / name,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "_artifacts"))
    bom, supply = root / "bom.csv", root / "supply.csv"
    pd.DataFrame([(m, 1 + m % 3, 1) for m in range(8)],
                 columns=["machine", "material", "required"]).to_csv(bom, index=False)
    supplies = np.zeros((3, 31))
    supplies[:, 0] = 60000
    supplies[0, 5], supplies[1, 9] = 3000, 4000
    pd.DataFrame({"material": [1, 2, 3], **{str(d): supplies[:, d] for d in range(31)}}).to_csv(supply, index=False)
    argv = ["--bom", str(bom), "--supply", str(supply), "--production-case-dir", str(PRODUCTION),
            "--machines", "8", "--materials", "3", "--pop-size", "2", "--generations", "1",
            "--max-evaluations", "4", "--inner-pop-size", "8", "--inner-generations", "1",
            "--inner-max-evaluations", "32", "--inner-memory-mb", "384",
            "--no-decision-trace", "--no-profiler"]
    if evaluation_only:
        argv.append("--evaluation-only")
    overrides = {"argv": argv}
    if evaluation_only:
        overrides["candidate"] = [1, 2]
    (root / "project_config.py").write_text(f'''
PROJECT_NAME = "joint"
L0 = {{"namespace": "joint", "offer": {{"threads": 1, "memory_mb": 1024}},
      "policy": {{"mode": "strict", "max_workers": 1, "max_threads": 1}},
      "default_request": {{"workers": 1, "threads": 1, "memory_mb": 512,
                            "capabilities": ["production_inner", "nested_eval"]}},
      "lease_backend": "sqlite", "lease_path": ".blackbase/leases.sqlite",
      "lease_ttl_seconds": 30, "lease_heartbeat_seconds": 5,
      "budgets": {{"evaluations": 132, "audit_evaluations": 4}}}}
STAGES = [{{"name": "joint", "cases": ["supply_adjustment_nested"], "timeout_seconds": 120,
           "component_overrides": {{"supply_adjustment_nested": {overrides!r}}}}}]
GROUPS = {{"default": {{"stages": ["joint"]}}}}
'''.lstrip(), encoding="utf-8")
    return root, supplies


def test_supply_candidate_gets_its_actual_sealed_child_schedule(tmp_path):
    root, original = make_project(tmp_path)
    result = execute_project(root, run_id="actual-joint-proof", record=False)
    assert result.ok, result.as_dict()
    outer = result.case_results[0]
    binding = ArtifactBinding.from_dict({"ref": outer.artifact_refs["joint_summary"].as_dict(),
                                        "publication": outer.artifact_publications["joint_summary"].as_dict()})
    reader = ArtifactPublisher.from_resource_context(outer.request.resource_context,
        project_run_id=outer.identity.project_run_id, case_run_id=outer.identity.case_run_id)
    summary = json.loads(reader.read_verified(binding))
    assert summary["shifts"] == [1, 2]
    assert summary["day0_max_abs_delta"] == 0
    np.testing.assert_array_equal(np.asarray(summary["adjusted_supply"])[:, 0], original[:, 0])
    assert len(summary["raw_objectives"]) == 3
    assert summary["raw_objectives"][1:] == [2, 3]
    assert summary["raw_objectives"][0] == -np.asarray(summary["schedule"]).sum()
    assert summary["candidate_token"]
    assert summary["inner_case_identity"]["parent_case_run_id"] == outer.identity.case_run_id
    assert summary["inner_budget_usage"]["audit_evaluations"]["committed"] == 1


def test_search_batch_keeps_a_child_receipt_for_the_selected_incumbent(tmp_path):
    root, original = make_project(tmp_path, evaluation_only=False)
    result = execute_project(root, run_id="actual-joint-batch-proof", record=False)
    assert result.ok, result.as_dict()
    outer = result.case_results[0]
    assert "joint_summary" in outer.artifact_refs
    assert 1 <= outer.output["metadata"]["joint_summary"]["outer_evaluations"] <= 4


def test_sealed_supply_plan_can_be_reevaluated_by_another_case_stage(tmp_path):
    root, _ = make_project(tmp_path)
    with (root / "project_config.py").open("a", encoding="utf-8") as stream:
        stream.write('''
from copy import deepcopy
second = deepcopy(STAGES[0])
second["name"] = "recheck"
second["component_overrides"]["supply_adjustment_nested"].pop("candidate")
second["component_overrides"]["supply_adjustment_nested"]["argv"] += ["--inner-seed", "43"]
second["input_artifacts"] = {"supply_adjustment_nested": {"candidate_plan": "joint.supply_adjustment_nested.joint_summary"}}
STAGES.append(second)
GROUPS["default"]["stages"].append("recheck")
''')
    result = execute_project(root, run_id="joint-recheck-proof", record=False)
    assert result.ok, result.as_dict()
    assert len(result.case_results) == 2
    summaries = []
    for case in result.case_results:
        reader = ArtifactPublisher.from_resource_context(case.request.resource_context,
            project_run_id=case.identity.project_run_id, case_run_id=case.identity.case_run_id)
        binding = ArtifactBinding(case.artifact_refs["joint_summary"], case.artifact_publications["joint_summary"])
        summaries.append(json.loads(reader.read_verified(binding)))
    assert summaries[0]["shifts"] == summaries[1]["shifts"] == [1, 2]
    assert summaries[0]["scenario_digest"] == summaries[1]["scenario_digest"]
    assert summaries[0]["inner_config"]["seed"] == 42
    assert summaries[1]["inner_config"]["seed"] == 43
    assert summaries[1]["candidate_plan_binding"]["ref"] == result.case_results[0].artifact_refs["joint_summary"].as_dict()
