from pathlib import Path

from nsgablack.utils.engineering.schema_version import schema_check, stamp_schema
from tools.schema_tool import check_files


def test_stamp_schema_and_check_ok():
    payload = stamp_schema({"run_id": "demo"}, "run_inspector_snapshot")
    ok, msg = schema_check(payload, "run_inspector_snapshot")
    assert ok, msg
    assert payload["schema_version"] == 1
    assert payload["schema_name"] == "run_inspector_snapshot"


def test_schema_check_reports_version_mismatch():
    payload = {"schema_name": "module_report", "schema_version": 99}
    ok, msg = schema_check(payload, "module_report")
    assert not ok
    assert "schema_version mismatch" in msg


def test_schema_tool_checks_known_json_patterns(tmp_path: Path):
    p = tmp_path / "a.modules.json"
    p.write_text('{"schema_name":"module_report","schema_version":1}', encoding="utf-8")
    checked, issues = check_files([tmp_path])
    assert checked == 1
    assert not issues


def test_schema_tool_checks_repro_bundle_pattern(tmp_path: Path):
    p = tmp_path / "demo.repro_bundle.json"
    p.write_text('{"schema_name":"repro_bundle","schema_version":1}', encoding="utf-8")
    checked, issues = check_files([tmp_path])
    assert checked == 1
    assert not issues


def test_schema_tool_skips_runs_by_default(tmp_path: Path):
    runs = tmp_path / "runs"
    runs.mkdir(parents=True)
    bad = runs / "demo.summary.json"
    bad.write_text('{"schema_name":"benchmark_summary","schema_version":0}', encoding="utf-8")
    checked, issues = check_files([tmp_path])
    assert checked == 0
    assert not issues


def test_schema_tool_can_include_runs_explicitly(tmp_path: Path):
    runs = tmp_path / "runs"
    runs.mkdir(parents=True)
    bad = runs / "demo.summary.json"
    bad.write_text('{"schema_name":"benchmark_summary","schema_version":0}', encoding="utf-8")
    checked, issues = check_files([tmp_path], include_runs=True)
    assert checked == 1
    assert issues


def test_schema_tool_scans_explicit_historical_root(tmp_path: Path):
    runs = tmp_path / "runs"
    runs.mkdir(parents=True)
    bad = runs / "demo.summary.json"
    bad.write_text('{"schema_name":"benchmark_summary","schema_version":0}', encoding="utf-8")
    checked, issues = check_files([runs])
    assert checked == 1
    assert issues
