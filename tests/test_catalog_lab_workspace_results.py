"""Presentation cannot turn accepted history into final algorithm evidence."""
from copy import deepcopy
import json

import pytest

from nsgablack.catalog.lab_workspace_results import compare_experiments, describe_result


def experiment(**changes):
    value = {
        "workspace_id": "workspace-a", "job_id": "job-a", "revision_id": "revision-a",
        "case_name": "search", "source_digest": "a" * 64, "status": "succeeded",
        "proposal": {"seed": 42, "parameters": {"population": 10, "optional": None},
                     "budget": {"max_steps": 3, "timeout_seconds": 60}},
        "result": {"success": True, "status": "succeeded", "project_revision": "a" * 64,
                   "steps": 2, "evaluations": 4, "elapsed_seconds": 1.25,
                   "raw_results": {"scope": "last_16_accepted", "refs": [
                       {"token": "first", "version": 1}, {"token": "second", "version": 2}],
                       "candidates": [[.1, .2], [.1, .2]], "raw_objectives": [[2., 8.], [3., 6.]],
                       "raw_violations": [0., 1.]},
                   "metrics": [{"path": "results/plan.audit.json", "report": {
                       "production": 100, "violations": 0, "rate": .2,
                       "details": {"machines": 20}, "values": [1., 2.], "ok": True}}],
                   "effective_data": {"files": {"input_path": {
                       "path": "cases/search/input.csv", "sha256": "c" * 64, "size_bytes": 36}},
                       "unresolved_path_fields": []}}}
    value.update(changes)
    return value


def by_key(rows):
    return {row["key"]: row for row in rows}


def test_success_has_factual_measures_and_explicit_history_scope():
    view = describe_result(experiment())
    assert view["succeeded"] is True and view["status_label"] == "已完成"
    assert [row["value"] for row in view["measures"]] == [2, 4, 1.25]
    assert view["scope"] == "last_16_accepted"
    assert "接纳历史" in view["scope_label"] and "不是算法最终成员" in view["scope_label"]
    assert any("最终成员" in text and "返回接纳" in text for text in view["missing_evidence"])
    assert "best" not in view and "pareto" not in view


def test_equal_numeric_candidates_preserve_different_exact_refs_and_order():
    view = describe_result(experiment())
    assert [row["index"] for row in view["raw_rows"]] == [0, 1]
    assert [row["solution_ref"]["token"] for row in view["raw_rows"]] == ["first", "second"]
    assert [row["raw_objectives"] for row in view["raw_rows"]] == [[2., 8.], [3., 6.]]


def test_presentation_is_detached_and_never_mutates_report():
    job = experiment()
    original = deepcopy(job)
    view = describe_result(job)
    view["raw_rows"][0]["solution_ref"]["version"] = 100
    view["raw_rows"][0]["candidate"].append(5)
    assert job == original


@pytest.mark.parametrize("key,value", [("steps", -1), ("steps", 1.5), ("steps", True),
    ("evaluations", float("nan")), ("elapsed_seconds", float("inf")), ("elapsed_seconds", -1)])
def test_invalid_measures_remain_missing_not_zero(key, value):
    job = experiment()
    job["result"][key] = value
    view = describe_result(job)
    assert by_key(view["measures"])[key]["value"] is None
    assert any("缺失或无效" in text for text in view["warnings"])
    json.dumps(view, allow_nan=False)


def test_zero_measure_is_a_real_recorded_value_and_duration_fallback_is_supported():
    job = experiment()
    job["result"].update(steps=0, evaluations=0, elapsed_seconds=None, duration_seconds=0.)
    assert [row["value"] for row in describe_result(job)["measures"]] == [0, 0, 0.]


def test_raw_row_count_mismatch_is_not_silently_zipped():
    job = experiment()
    job["result"]["raw_results"]["raw_violations"] = [0.]
    view = describe_result(job)
    assert view["raw_rows"] == []
    assert any("行数不一致" in text for text in view["warnings"])


def test_missing_refs_do_not_invent_identity_from_equal_values():
    job = experiment()
    job["result"]["raw_results"]["refs"] = [{"token": "first", "version": 1}]
    view = describe_result(job)
    assert [row["solution_ref"] for row in view["raw_rows"]] == [None, None]
    assert any("未按数值相等推断身份" in text for text in view["warnings"])


@pytest.mark.parametrize("key,value", [("raw_violations", [float("nan"), 1.]),
    ("raw_objectives", [[float("inf"), 8.], [3., 6.]]),
    ("candidates", [[None, .2], [.1, .2]])])
def test_nonfinite_or_missing_raw_row_does_not_shift_identity(key, value):
    job = experiment()
    job["result"]["raw_results"][key] = value
    view = describe_result(job)
    assert len(view["raw_rows"]) == 1
    assert view["raw_rows"][0]["index"] == 1
    assert view["raw_rows"][0]["solution_ref"]["token"] == "second"
    assert any("第 1 行" in text for text in view["warnings"])
    json.dumps(view, allow_nan=False)


def test_unknown_scope_is_not_trusted_as_final_population():
    job = experiment()
    job["result"]["raw_results"]["scope"] = "final_population"
    view = describe_result(job)
    assert "未核验" in view["scope_label"]
    assert any("最终成员" in text for text in view["missing_evidence"])


def test_failed_and_pending_jobs_keep_actual_status_without_success_claim():
    for status in ("failed", "queued", "running", "interrupted"):
        job = experiment(status=status, result=None)
        view = describe_result(job)
        assert view["succeeded"] is False
        assert view["raw_rows"] == []
        assert [row["value"] for row in view["measures"]] == [None, None, None]
        assert any("不构成算法效果验证" in text for text in view["missing_evidence"])


def test_contradictory_job_and_result_status_are_called_out():
    job = experiment()
    job["result"]["success"] = False
    job["result"]["status"] = "failed"
    view = describe_result(job)
    assert not view["succeeded"]
    assert any("状态不一致" in text for text in view["warnings"])


def test_success_label_without_report_does_not_claim_verified_completion():
    view = describe_result(experiment(result=None))
    assert not view["succeeded"]
    assert "尚无运行报告。" in view["missing_evidence"]
    assert any("状态不一致" in text for text in view["warnings"])


def test_only_finite_scalar_metrics_are_flattened_without_objective_sums():
    job = experiment()
    job["result"]["metrics"][0]["report"].update(missing=float("nan"), infinite=float("inf"))
    rows = describe_result(job)["metric_rows"]
    assert [row["value"] for row in rows] == [100, 0, .2, 20]
    assert all("values" not in row["key"] and "ok" not in row["key"] for row in rows)
    assert any("未声明优化方向" in text for text in describe_result(job)["warnings"])


def test_metric_json_pointers_distinguish_slashes_and_nested_keys():
    job = experiment()
    job["result"]["metrics"] = {"a/b": 1, "a": {"b": 2}, "a~b": 3}
    assert [row["key"] for row in describe_result(job)["metric_rows"]] == ["#/a~1b", "#/a/b", "#/a~0b"]


def test_matching_workspace_and_case_enable_factual_deltas_only():
    baseline = experiment()
    current = experiment(job_id="job-b", revision_id="revision-b")
    current["result"].update(steps=3, evaluations=7, elapsed_seconds=2.)
    comparison = compare_experiments(current, baseline)
    assert comparison["can_compare"] is True and comparison["reasons"] == []
    assert comparison["same_snapshot"] is True
    assert [row["delta"] for row in comparison["measure_rows"]] == [1, 3, .75]
    assert comparison["quality_conclusion"] is None
    assert any("不据此判定算法优劣" in text for text in comparison["notices"])


@pytest.mark.parametrize("field,value", [("workspace_id", "elsewhere"), ("case_name", "training"),
    ("workspace_id", None), ("case_name", "")])
def test_mismatched_or_missing_identity_blocks_delta_view(field, value):
    current = experiment(**{field: value})
    comparison = compare_experiments(current, experiment())
    assert comparison["can_compare"] is False and comparison["reasons"]
    assert comparison["configuration_rows"] == comparison["measure_rows"] == comparison["metric_rows"] == []


def test_same_source_does_not_implicitly_mean_same_data():
    left, right = experiment(), experiment()
    left["result"].pop("effective_data")
    right["result"].pop("effective_data")
    comparison = compare_experiments(left, right)
    assert comparison["same_snapshot"] is True
    assert comparison["data_status"] == "unverified"


@pytest.mark.parametrize("data", [{}, {"files": {}}, {"files": {}, "arrays": {"x": {"shape": [2]}}},
    {"files": {"input_path": {"path": "input.csv", "sha256": "missing-size"}}},
    {"files": {"input_path": {"path": "input.csv", "sha256": "c" * 64, "size_bytes": 36}},
     "unresolved_path_fields": ["other_path"]}])
def test_empty_or_incomplete_data_observation_is_unverified(data):
    current = experiment()
    current["result"]["effective_data"] = data
    comparison = compare_experiments(current, experiment())
    assert comparison["data_status"] == "unverified"


def test_matching_hashes_only_claim_registered_files_match():
    comparison = compare_experiments(experiment(), experiment())
    assert comparison["data_status"] == "matched"
    assert "已登记数据文件一致" in comparison["data_label"]
    assert "未声明的输入尚未核验" in comparison["data_label"]


def test_different_data_hashes_are_explicit_even_if_source_digest_matches():
    current = experiment()
    current["result"]["effective_data"]["files"]["input_path"]["sha256"] = "d" * 64
    comparison = compare_experiments(current, experiment())
    assert comparison["same_snapshot"] is True
    assert comparison["data_status"] == "different"
    assert "数据文件不同" in comparison["data_label"]


def test_changed_or_unbound_source_is_reported_without_blocking_factual_comparison():
    current = experiment(source_digest="b" * 64)
    current["result"]["project_revision"] = "b" * 64
    comparison = compare_experiments(current, experiment())
    assert comparison["can_compare"] and comparison["same_snapshot"] is False
    assert any("不同工程快照" in text for text in comparison["notices"])
    current["result"]["project_revision"] = "e" * 64
    comparison = compare_experiments(current, experiment())
    assert comparison["same_snapshot"] is None
    assert any("摘要缺失或不一致" in text for text in comparison["notices"])


def test_parameters_budget_and_seed_show_submitted_values_and_absence():
    current = experiment()
    current["proposal"]["parameters"] = {"population": 20, "new": None}
    current["proposal"]["seed"] = 43
    current["proposal"]["budget"]["max_steps"] = 8
    rows = by_key(compare_experiments(current, experiment())["configuration_rows"])
    assert rows["parameters.population"]["baseline"] == 10
    assert rows["parameters.population"]["current"] == 20
    assert rows["seed"]["changed"] and rows["budget.max_steps"]["changed"]
    assert rows["parameters.new"]["baseline_present"] is False
    assert rows["parameters.new"]["current_present"] is True
    assert rows["parameters.new"]["changed"] is True
    assert rows["parameters.optional"]["current_present"] is False
    assert rows["parameters.optional"]["baseline_present"] is True


def test_metric_deltas_are_arithmetic_and_missing_side_remains_unknown():
    current = experiment()
    report = current["result"]["metrics"][0]["report"]
    report["production"] = 90
    report["new"] = 17
    report.pop("rate")
    comparison = compare_experiments(current, experiment())
    rows = by_key(comparison["metric_rows"])
    assert rows["results/plan.audit.json#/production"]["delta"] == -10
    assert rows["results/plan.audit.json#/new"]["delta"] is None
    assert rows["results/plan.audit.json#/rate"]["delta"] is None
    assert comparison["quality_conclusion"] is None


def test_failed_experiment_can_compare_recorded_cost_but_never_quality():
    current = experiment(status="failed")
    current["result"].update(success=False, status="failed", elapsed_seconds=5.)
    comparison = compare_experiments(current, experiment())
    assert comparison["can_compare"] is True
    assert comparison["measure_rows"][-1]["delta"] == 3.75
    assert comparison["quality_conclusion"] is None
    assert any("没有成功结果" in text for text in comparison["notices"])


def test_missing_metrics_do_not_turn_into_zero_or_nonfinite_deltas():
    current = experiment()
    current["result"]["elapsed_seconds"] = float("nan")
    current["result"]["metrics"] = {"number": float("inf")}
    comparison = compare_experiments(current, experiment())
    assert comparison["measure_rows"][-1]["delta"] is None
    assert all(row["delta"] is None for row in comparison["metric_rows"])
    json.dumps(comparison, allow_nan=False)


def test_arithmetic_overflow_does_not_crash_comparison_or_create_infinity():
    current, baseline = experiment(), experiment()
    current["result"]["elapsed_seconds"] = 10 ** 400
    comparison = compare_experiments(current, baseline)
    assert comparison["measure_rows"][-1]["delta"] is None
    current["result"]["elapsed_seconds"] = 1.7e308
    baseline["result"]["elapsed_seconds"] = .1
    baseline["result"]["metrics"] = {"large": -1.7e308}
    current["result"]["metrics"] = {"large": 1.7e308}
    assert compare_experiments(current, baseline)["metric_rows"][0]["delta"] is None


def test_inputs_must_be_mappings():
    with pytest.raises(TypeError):
        describe_result([])
    with pytest.raises(TypeError):
        compare_experiments({}, [])
