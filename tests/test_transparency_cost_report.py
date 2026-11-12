import json

import pytest

from benchmarks import transparency_cost_report as module


def test_failed_project_is_not_a_cost_report(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"status":"failed"}),encoding="utf-8")
    with pytest.raises(ValueError,match="finish"):
        module.export(path,tmp_path/"out")


def test_unqualified_fixture_cannot_be_reported_as_passed(tmp_path,monkeypatch):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"status":"ok","cases":[{}]}),encoding="utf-8")
    monkeypatch.setattr(module,"read_report",lambda c:{"mode":"costs","validation":{"status":"passed"},
        "fixtures":[{"qualification":{s:{"status":"unsupported"} for s in ("semantics","quality","recovery")}}]})
    with pytest.raises(ValueError,match="unqualified"):
        module.export(path,tmp_path/"out")
