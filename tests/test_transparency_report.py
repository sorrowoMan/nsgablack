"""离线汇总不能用被改写的Artifact或未完成Project出具成功证据。"""
import hashlib
import json

import pytest

from benchmarks.transparency_report import _validate_report, collect, read_report


def published_case(tmp_path):
    from blackbase.resources import DataRef
    from blackbase.resources.artifacts import ArtifactPublicationReceipt

    data = b'{"mode":"matrix","rows":[]}'
    path = tmp_path / "report.json"
    path.write_bytes(data)
    ref = DataRef(uri=str(path), backend="filesystem", checksum="sha256:" + hashlib.sha256(data).hexdigest(),
                  size_bytes=len(data), media_type="application/json")
    receipt = ArtifactPublicationReceipt(publication_id="publication-test", artifact_name="report", ref=ref,
        project_run_id="project-test", case_run_id="case-test", transaction_id="transaction-test",
        authority_namespace="test", committed_at=1.0, metadata={"case_finalization_sealed": True})
    return {"artifact_refs": {"report": ref.as_dict()}, "artifact_publications": {"report": receipt.as_dict()}}


def test_report_bytes_must_match_publication_checksum(tmp_path):
    case = published_case(tmp_path)
    assert read_report(case)["rows"] == []
    path = tmp_path / "report.json"
    path.write_bytes(path.read_bytes().replace(b"matrix", b"fake!!"))
    with pytest.raises(ValueError, match="checksum"):
        read_report(case)


def test_receipt_integrity_is_checked_before_reading_data(tmp_path):
    case = published_case(tmp_path)
    case["artifact_publications"]["report"]["case_run_id"] = "other-case"
    with pytest.raises(ValueError, match="digest"):
        read_report(case)


def test_failed_project_cannot_enter_success_summary(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"status": "failed", "exit_code": 2}), encoding="utf-8")
    with pytest.raises(ValueError, match="not completed successfully"):
        collect([path])


def test_old_published_success_with_failed_inner_comparison_is_rejected():
    with pytest.raises(ValueError, match="comparison"):
        _validate_report({"mode": "nested", "comparison": {"status": "failed"}})


def test_empty_matrix_cannot_be_accepted_as_benchmark_evidence():
    with pytest.raises(ValueError, match="empty"):
        _validate_report({"mode": "matrix", "rows": []})


@pytest.mark.parametrize("section", ["semantics", "quality", "recovery", "overhead"])
def test_each_failed_section_prevents_a_success_summary(section):
    row = {"name": "broken", "semantics": {"status": "passed"}, "quality": {"status": "passed"},
           "recovery": {"status": "passed"}, "overhead": {"status": "measured"}}
    row[section]["status"] = "failed"
    with pytest.raises(ValueError, match=section):
        _validate_report({"mode": "matrix", "rows": [row]})
