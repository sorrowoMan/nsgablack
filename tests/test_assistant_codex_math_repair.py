import json

import pytest

from nsgablack.catalog import assistant_codex_math_repair as repair
from nsgablack.catalog import assistant_codex_acceptance as acceptance


@pytest.mark.parametrize("idea", tuple(repair.FAULTS))
def test_declared_seed_changes_one_expression_and_fails_original_math(tmp_path, idea):
    directory = tmp_path / "seed"
    frozen = repair.freeze_oracle()
    manifest = repair.prepare_seed(idea, directory)
    source = (directory / "seed.py").read_text(encoding="utf-8")
    assert manifest["single_expression_mutation"]["new"] in source
    assert manifest["seed_sha256"] != manifest["reference_source_sha256"]
    result = repair.preflight_seed(idea, directory)
    assert result["validation"]["failed_stage"] == "behavior"
    assert result["validation"]["executed"] is True
    assert result["validation"]["error_type"] == "AssertionError"
    assert repair.freeze_oracle() == frozen


def test_preflight_failure_alone_does_not_count_as_model_error_repair(tmp_path, monkeypatch):
    from nsgablack.catalog.assistant_novel_acceptance import TARGET
    seed = tmp_path / "seed"
    seed.mkdir()
    run = tmp_path / "run"
    run.mkdir()
    frozen = {"fixed": "unchanged"}
    (seed / "seed-manifest.json").write_text(json.dumps({"seed_sha256": "bad", "oracle_before": frozen}))
    (run / "report.json").write_text(json.dumps({"idea": "fixture", "resume_thread": None}))
    monkeypatch.setattr(repair, "freeze_oracle", lambda *args: frozen)
    monkeypatch.setattr(acceptance, "review_acceptance", lambda path: {
        "status": "passed", "actual_file_sha256": "good", "thread_ids": ["same-thread"]})
    def event(digest, status):
        return {"type": "item.completed", "item": {"type": "mcp_tool_call", "server": "black-framework", "tool": "check_project_edit",
            "result": {"structured_content": {"path": TARGET, "code_sha256": digest,
                "check": {"status": "needs_runtime_validation"}, "validation": {"status": status,
                    "executed": True, "failed_stage": "behavior", "error_type": "AssertionError"}}}}}
    def save(events):
        (run / "events.jsonl").write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
    save([event("good", "passed")])
    assert repair.review_repair(run, seed)["status"] == "not_verified"
    save([event("bad", "failed"), event("good", "passed")])
    assert repair.review_repair(run, seed)["status"] == "passed"
    for key, value in (("executed", False), ("failed_stage", "import"), ("error_type", "TypeError")):
        not_math = event("bad", "failed")
        not_math["item"]["result"]["structured_content"]["validation"][key] = value
        save([not_math, event("good", "passed")])
        assert repair.review_repair(run, seed)["status"] == "not_verified"
    other_server = event("bad", "failed")
    other_server["item"]["server"] = "unrelated"
    save([other_server, event("good", "passed")])
    assert repair.review_repair(run, seed)["status"] == "not_verified"
    save([event("bad", "failed"), event("good", "passed")])
    manifest = {"seed_sha256": "bad", "oracle_before": frozen, "expected_thread_id": "same-thread"}
    (seed / "seed-manifest.json").write_text(json.dumps(manifest))
    (run / "report.json").write_text(json.dumps({"idea": "fixture", "resume_thread": "same-thread"}))
    assert repair.review_repair(run, seed)["status"] == "passed"
    (run / "report.json").write_text(json.dumps({"idea": "fixture", "resume_thread": "other-thread"}))
    assert repair.review_repair(run, seed)["status"] == "not_verified"
    (run / "report.json").write_text(json.dumps({"idea": "fixture", "resume_thread": "same-thread"}))
    monkeypatch.setattr(repair, "freeze_oracle", lambda *args: {"changed": True})
    assert repair.review_repair(run, seed)["status"] == "not_verified"
