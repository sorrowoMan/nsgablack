from copy import deepcopy

import pytest

from nsgablack.catalog.assistant_evaluation import content_digest, evaluate_records
from nsgablack.catalog.lab_assistant import assistant_messages, build_assistant_packet
from nsgablack.catalog.lab_assembly import assembly_from_recipe


def fixture_record():
    packet = build_assistant_packet(assembly_from_recipe("ga"), instruction="Pool 和 ctx 的职责如何区分？")
    return {"id": "fixture", "family": "pool-context", "split": "test", "packet": packet,
            "reference_answer": {"base_digest": packet["base_digest"], "draft": None,
                                 "explanation": "Pool 保存精确候选引用，ctx 保存轻量调用信息。",
                                 "changes": [], "questions": [], "evidence_keys": []},
            "rubric": ["区分候选身份与主流程调用信息。"]}


def test_shared_request_preparation_preserves_inputs_and_has_no_model_side_effect():
    spec = assembly_from_recipe("ga")
    previous = deepcopy(spec)
    packet = build_assistant_packet(spec, instruction="讨论已有结构")
    messages = assistant_messages(packet)
    assert spec == previous
    assert [m["role"] for m in messages] == ["system", "user"]
    import json
    assert json.loads(messages[1]["content"]) == packet
    assert "reference_answer" not in packet and "rubric" not in packet


def test_model_never_receives_reference_answer_or_rubric_and_format_does_not_pass_semantics():
    record = fixture_record()
    calls = []
    class Generator:
        def generate(self, packet):
            calls.append(packet)
            assert "rubric" not in packet and "reference_answer" not in packet
            return record["reference_answer"]
    report = evaluate_records([record], generator=Generator(), model_identity="local-test")
    assert len(calls) == 1
    assert report["summary"]["protocol_passed"] == 1
    assert report["summary"]["semantic_passed"] == 0
    assert report["summary"]["semantic_pending"] == 1


def test_reference_replay_is_labelled_as_harness_not_model_quality():
    report = evaluate_records([fixture_record()], reference_replay=True, model_identity="fixture")
    assert report["kind"] == "harness_reference_replay"
    assert report["summary"]["semantic_pending"] == 1


def test_human_review_is_bound_to_exact_response_and_rejects_later_response_changes():
    record = fixture_record()
    answer = record["reference_answer"]
    review = {"fixture": {"response_sha256": content_digest(answer), "decision": "pass"}}
    assert evaluate_records([record], responses={"fixture": answer}, reviews=review,
                            model_identity="test")["summary"]["semantic_passed"] == 1
    changed = {**answer, "explanation": "不同的回答。"}
    with pytest.raises(ValueError, match="review_response_mismatch"):
        evaluate_records([record], responses={"fixture": changed}, reviews=review, model_identity="test")


def test_provider_failure_never_echoes_exception_or_retries():
    calls = []
    class Broken:
        def generate(self, packet):
            calls.append(1)
            raise RuntimeError("Bearer private-canary http://private.invalid")
    report = evaluate_records([fixture_record()], generator=Broken(), model_identity="test")
    assert calls == [1]
    assert "private-canary" not in str(report) and "private.invalid" not in str(report)
    assert report["summary"]["protocol_passed"] == 0


def test_missing_and_unknown_answers_cannot_disappear_from_denominator():
    record = fixture_record()
    report = evaluate_records([record], responses={}, model_identity="test")
    assert report["summary"]["total"] == 1 and report["summary"]["protocol_passed"] == 0
    with pytest.raises(ValueError, match="unknown_response"):
        evaluate_records([record], responses={"other": {}}, model_identity="test")


def test_clarification_cannot_be_counted_as_requested_draft_delivery():
    record = fixture_record()
    record["reference_answer"]["draft"] = record["packet"]["assembly"]
    response = {**record["reference_answer"], "draft": None, "questions": ["缺少哪项定义？"]}
    report = evaluate_records([record], responses={"fixture": response}, model_identity="test")
    assert report["summary"]["protocol_passed"] == 1
    assert report["summary"]["delivery_matches_reference"] == 0
    assert report["summary"]["draft_matches_reference"] == 0


def test_cognition_profile_keeps_gold_and_rubric_out_of_user_context():
    from nsgablack.catalog.assistant_cognition import cognition_messages
    record = fixture_record()
    record["reference_answer"]["explanation"] = "reference-answer-canary"
    record["rubric"] = {"criteria": ["secret-rubric-canary"]}
    messages = cognition_messages(record)
    assert messages[-1]["content"] == "reference-answer-canary"
    assert "reference-answer-canary" not in str(messages[:-1])
    assert "secret-rubric-canary" not in str(messages)
    assert "assembly_catalog" not in str(messages)
    assert "adapter.bayesian_optimization" in messages[1]["content"]


def test_cognition_export_keeps_splits_and_does_not_overwrite_dataset(monkeypatch, tmp_path):
    import hashlib
    import json
    import nsgablack.catalog.assistant_cognition as module
    record = fixture_record()
    def records(path, *, split):
        return ({**record, "id": split, "family": split, "split": split},)
    monkeypatch.setattr(module, "load_exported_records", records)
    parent = tmp_path / "parent"
    parent.mkdir()
    (parent / "metadata.json").write_text("{}")
    target = tmp_path / "short"
    manifest = module.export_cognition_dataset(parent, target)
    assert manifest["counts"] == {"train": 1, "validation": 1, "test": 1}
    assert manifest["profile"] == "framework_cognition_only/v1"
    for path, digest in manifest["files"].items():
        assert hashlib.sha256((target / path).read_bytes()).hexdigest() == digest
    assert len(json.loads((target / "train.jsonl").read_text(encoding="utf-8"))["messages"]) == 3
    with pytest.raises(ValueError, match="already_exists"):
        module.export_cognition_dataset(parent, target)


def test_actual_export_drives_cognition_and_evaluation_cli_without_model(tmp_path, capsys):
    import json
    from nsgablack.catalog.assistant_dataset import export_dataset
    from nsgablack.catalog.assistant_cognition import export_cognition_dataset
    from nsgablack.catalog.assistant_evaluation import main
    parent = tmp_path / "workbench"
    manifest = export_dataset(parent)
    short = export_cognition_dataset(parent, tmp_path / "cognition")
    assert sum(short["counts"].values()) == len(manifest["cases"])
    report_path = tmp_path / "report.json"
    assert main([str(parent), "--reference-replay", "--out", str(report_path)]) == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["kind"] == "harness_reference_replay"
    assert report["summary"]["protocol_passed"] == short["counts"]["test"]
    assert report["summary"]["semantic_passed"] == 0
    assert report["summary"]["semantic_pending"] == short["counts"]["test"]


def test_actual_model_settings_are_fingerprinted_without_keys_or_private_urls():
    from nsgablack.catalog.assistant_evaluation import model_configuration_metadata
    from nsgablack.catalog.lab_model_provider import CompatibleAssistantConfig
    first = CompatibleAssistantConfig("https://private-model.invalid/v1", "base-model", "credential-canary")
    second = CompatibleAssistantConfig("https://private-model.invalid/v1", "tuned-model", "other-key")
    value = model_configuration_metadata(first)
    assert value["backend"] == "compatible" and value["model"] == "base-model"
    assert value["configuration_sha256"] != model_configuration_metadata(second)["configuration_sha256"]
    assert value == model_configuration_metadata(
        CompatibleAssistantConfig("https://private-model.invalid/v1", "base-model", "changed-key"))
    assert "credential-canary" not in str(value) and "private-model.invalid" not in str(value)
