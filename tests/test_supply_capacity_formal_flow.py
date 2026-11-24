"""部分外层初始化仍通过并行内层的正式计数、发布和结算闭包。"""
import json
import runpy

from blackbase.project import execute_project
from blackbase.resources import ArtifactBinding, ArtifactPublisher

from tests.test_supply_joint_formal_case import make_project


def test_large_outer_initialization_budget_two_keeps_threaded_child_evidence(tmp_path):
    root, _ = make_project(tmp_path, evaluation_only=False)
    module = runpy.run_path(str(root / "project_config.py"))
    l0, stages = module["L0"], module["STAGES"]
    l0["offer"]["threads"] = l0["policy"]["max_threads"] = 4
    l0["default_request"]["threads"] = 4
    argv = stages[0]["component_overrides"]["supply_adjustment_nested"]["argv"]
    argv += ["--pop-size", "200", "--generations", "100", "--max-evaluations", "2",
             "--inner-pop-size", "32", "--inner-generations", "2",
             "--inner-max-evaluations", "64", "--parallel", "--inner-parallel-workers", "4"]
    (root / "project_config.py").write_text(
        "PROJECT_NAME = 'joint'\nL0 = " + repr(l0) + "\nSTAGES = " + repr(stages)
        + "\nGROUPS = " + repr(module["GROUPS"]) + "\n", encoding="utf-8")
    result = execute_project(root, run_id="capacity-partial-initialization", record=False)
    assert result.ok, result.as_dict()
    case = result.case_results[0]
    reader = ArtifactPublisher.from_resource_context(case.request.resource_context,
        project_run_id=case.identity.project_run_id, case_run_id=case.identity.case_run_id)
    binding = ArtifactBinding(ref=case.artifact_refs["candidate_search_audit"],
                              publication=case.artifact_publications["candidate_search_audit"])
    audit = json.loads(reader.read_verified(binding))
    assert audit["accepted_candidate_count"] == audit["outer_evaluations"] == 2
    for row in audit["rows"]:
        inner = json.loads(reader.read_verified(ArtifactBinding.from_dict(row["production_summary_binding"])))
        assert 0 < inner["algorithm_evaluations"] <= 64
        assert inner["resource_grant"]["threads"] == 4
        assert inner["inner_config"]["parallel_workers"] == 4
        assert inner["inner_config"]["parallel"] is True
        dispatch = inner["parallel_raw_dispatch"]
        assert dispatch["thread_batches"] >= 1
        assert dispatch["thread_completed_count"] >= 5
        assert dispatch["started_count"] == dispatch["completed_count"] == inner["algorithm_evaluations"]
        assert dispatch["process_ids"] == [inner["pid"]]
        assert dispatch["max_distinct_threads"] >= 1
        assert inner["resource_binding_current"] is True
        assert inner["day0_max_abs_delta"] == 0
        assert inner["candidate_token"] == row["candidate_token"]
        for name, count in (("evaluations", inner["algorithm_evaluations"]), ("audit_evaluations", 1)):
            usage = row["inner_budget_usage"][name]
            assert usage["committed"] == usage["charged_to_parent"] == count
            assert usage["outstanding_reserved"] == 0
            assert usage["settlement_status"] == "settled"
