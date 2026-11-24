"""失败诊断保留本地证据，并让正式 Case 边界接收到失败。"""
import json
from types import SimpleNamespace

import pytest

from blackbase.project import CaseRunIdentity
from benchmarks import transparency_case as case_module


def assemble(tmp_path, monkeypatch, *, quality="passed", allow_unsupported=()):
    monkeypatch.setattr(case_module, "_registry", lambda **kwargs: {"fixture": object()})
    monkeypatch.setattr(case_module, "run_pair", lambda *args, **kwargs: {
        "name": "fixture", "seed": 11, "semantics": {"status": "passed"},
        "quality": {"status": quality}, "overhead": {"status": "measured"},
        "recovery": {"status": "unsupported", "reason": "not requested"}})
    published = []
    runtime = SimpleNamespace(identity=CaseRunIdentity(case_run_id="failed-case"),
        checkpoint=lambda: None,
        publish_artifact=lambda *args, **kwargs: (published.append(args[0]) or
            SimpleNamespace(as_dict=lambda: {"uri": "artifact:report"})))
    case = case_module.make_benchmark_case("matrix", resource_context={"threads": 1}, config={
        "names": ["fixture"], "recovery": False, "output_dir": str(tmp_path),
        "allow_unsupported": allow_unsupported})
    case.set_case_runtime(runtime)
    return case, published


@pytest.mark.parametrize("status", ["failed", "unsupported"])
def test_required_failed_or_unsupported_quality_preserves_evidence_without_success_artifact(tmp_path, monkeypatch, status):
    case, published = assemble(tmp_path, monkeypatch, quality=status)
    with pytest.raises(RuntimeError, match="local evidence"):
        case.run()
    evidence = json.loads((tmp_path / "failed-case" / "failed_report.json").read_text(encoding="utf-8"))
    assert evidence["validation"]["status"] == "failed"
    assert evidence["validation"]["failures"][0]["section"] == "quality"
    assert published == []


def test_profile_must_explicitly_make_unsupported_quality_optional(tmp_path, monkeypatch):
    case, published = assemble(tmp_path, monkeypatch, quality="unsupported", allow_unsupported=["quality"])
    output = case.run()
    assert output["validation"]["status"] == "passed"
    assert published == ["report"]


@pytest.mark.parametrize("field", ["names", "seeds"])
def test_empty_request_is_rejected_before_any_pair_or_success_publication(tmp_path, monkeypatch, field):
    case, published = assemble(tmp_path, monkeypatch)
    case.options[field] = []
    monkeypatch.setattr(case_module, "run_pair", lambda *a, **k: pytest.fail("empty requests must not run pairs"))
    with pytest.raises(RuntimeError, match="local evidence"):
        case.run()
    evidence = json.loads((tmp_path / "failed-case" / "failed_report.json").read_text(encoding="utf-8"))
    assert evidence["rows"] == []
    assert evidence["validation"]["status"] == "failed"
    assert evidence["validation"]["failures"][0]["section"] == "request"
    assert published == []
