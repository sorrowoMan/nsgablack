"""Corpus integrity and production-protocol checks, not model quality scores."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil

import pytest

import nsgablack.catalog.assistant_dataset as dataset
from nsgablack.catalog.lab_assistant import assistant_messages, validate_draft


@pytest.fixture(scope="module")
def exported(tmp_path_factory):
    target = tmp_path_factory.mktemp("assistant_dataset")
    manifest = dataset.export_dataset(target)
    return target, manifest


def _copy_export(exported, tmp_path):
    target = tmp_path / "corpus"
    shutil.copytree(exported[0], target)
    return target


def _write_manifest(target, manifest):
    manifest = deepcopy(manifest)
    manifest.pop("dataset_digest", None)
    manifest["dataset_digest"] = dataset._digest(manifest)
    (target / "metadata.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")


def _case(identity):
    return next(case for case in dataset.load_cases() if case["id"] == identity)


def test_seed_is_explicit_small_authored_corpus_and_family_separated():
    cases = dataset.load_cases()
    assert len(cases) == 20
    assert Counter(case["split"] for case in cases) == {"train": 12, "validation": 3, "test": 5}
    assert len({case["family"] for case in cases}) == 20
    assert all(case["rubric"]["criteria"] and case["source_checks"] for case in cases)
    cases[0]["rubric"]["criteria"].append("mutated only this copy")
    assert "mutated only this copy" not in dataset.load_cases()[0]["rubric"]["criteria"]


@pytest.mark.parametrize("case_id", [case["id"] for case in dataset.load_cases()])
def test_every_record_uses_production_prompt_packet_and_valid_reference(case_id):
    case = _case(case_id)
    record = dataset.build_record(case)
    assert record["messages"][:2] == assistant_messages(record["packet"])
    assert json.loads(record["messages"][1]["content"]) == record["packet"]
    assert json.loads(record["messages"][2]["content"]) == record["reference_answer"]
    assert {"rubric", "reference_answer", "answer", "answer_action", "source_checks", "split"}.isdisjoint(record["packet"])
    assert record["reference_answer"]["explanation"] not in record["messages"][1]["content"]
    checked = validate_draft(record["reference_answer"], base_digest=record["packet"]["base_digest"],
        catalog=record["packet"]["assembly_catalog"], framework_context=record["packet"]["framework_context"])
    assert checked["verification_status"] == "not_run"
    assert record["provenance"]["review_status"] == "agent_source_checked"
    assert record["provenance"]["human_review"] == "not_done"
    assert record["provenance"]["runtime_validation"] == "not_run"
    for source in record["provenance"]["source_checks"]:
        content = dataset._read_source(source["path"])
        assert source["sha256"] == hashlib.sha256(content).hexdigest()
        lines = content.decode("utf-8-sig").splitlines()
        assert source["anchor"] in lines[source["line"] - 1]
        assert source["excerpt"] == "\n".join(lines[source["line"] - 1:source["end_line"]])


def test_export_is_hf_messages_only_and_metadata_is_out_of_model_packet(exported):
    target, manifest = exported
    assert {path.name for path in target.iterdir()} == {"train.jsonl", "validation.jsonl", "test.jsonl", "metadata.json"}
    assert manifest["validation"] == {"protocol": "passed", "semantic": "pending_independent_review",
                                      "model_execution": "not_run", "training": "not_run"}
    for split in dataset.SPLITS:
        rows = [json.loads(line) for line in (target / (split + ".jsonl")).read_text(encoding="utf-8").splitlines()]
        assert len(rows) == manifest["files"][split + ".jsonl"]["rows"]
        for row in rows:
            assert set(row) == {"messages"}
            assert [message["role"] for message in row["messages"]] == ["system", "user", "assistant"]
            packet = json.loads(row["messages"][1]["content"])
            assert {"rubric", "reference_answer", "expected_answer", "family", "split"}.isdisjoint(packet)
    assert all(row["token_count"] is None and row["tokenizer"] is None for row in manifest["cases"])
    assert all(row["message_characters"][1] > 30000 for row in manifest["cases"])


def test_loader_validates_full_corpus_but_returns_only_selected_split(exported):
    target, _ = exported
    held_out = dataset.load_exported_records(target)
    assert len(held_out) == 5 and all(row["split"] == "test" for row in held_out)
    train = dataset.load_exported_records(target, split="train")
    assert len(train) == 12
    assert {row["family"] for row in train}.isdisjoint(row["family"] for row in held_out)
    assert all("reference_answer" in row and "packet" in row for row in held_out)
    held_out[0]["packet"]["instruction"] = "mutated copy"
    assert dataset.load_exported_records(target)[0]["packet"]["instruction"] != "mutated copy"
    report = dataset.validate_dataset(target)
    assert report["protocol"] == "passed" and report["semantic"] == "pending_independent_review"
    assert report["records"] == 20


def test_no_model_invocation_or_request_manager_is_used(tmp_path, monkeypatch):
    import nsgablack.catalog.lab_assistant as assistant
    def forbidden(*args, **kwargs):
        raise AssertionError("dataset must stay offline")
    monkeypatch.setattr(assistant.DeepSeekAssemblyGenerator, "generate", forbidden)
    monkeypatch.setattr(assistant.AssistantManager, "submit", forbidden)
    dataset.export_dataset(tmp_path / "offline", cases=[_case("framework_roles_01")])
    assert dataset.validate_dataset(tmp_path / "offline")["records"] == 1


def test_seed_edit_changes_only_seed():
    record = dataset.build_record(_case("seed_edit_01"))
    expected = deepcopy(record["packet"]["assembly"])
    expected["seed"] = 19
    assert record["reference_answer"]["draft"] == expected


def test_expression_delivery_preserves_algorithm_plan_and_budget():
    record = dataset.build_record(_case("problem_formula_01"))
    before, after = record["packet"]["assembly"], record["reference_answer"]["draft"]
    changed = {key for key in before if before[key] != after[key]}
    assert changed <= {"dimension", "problem", "pipeline"}
    assert after["dimension"] == 1
    assert after["problem"]["parameters"]["constraints"] == []
    assert after["problem"]["parameters"]["objectives"][0]["direction"] == "min"


@pytest.mark.parametrize("change,error", [
    (lambda rows: rows.append(deepcopy(rows[0])), "dataset_duplicate_case"),
    (lambda rows: rows.append(dict(deepcopy(rows[0]), id="different_id")), "dataset_duplicate_input"),
    (lambda rows: rows.append(dict(deepcopy(rows[0]), id="different_id", instruction="another question", split="test")), "dataset_family_leakage"),
    (lambda rows: rows[0].update(split="other"), "dataset_split_invalid"),
    (lambda rows: rows[0].update(rubric={"delivery": "discussion", "criteria": [], "forbidden_inferences": []}), "dataset_rubric_invalid"),
    (lambda rows: rows[0].update(source_checks=[]), "dataset_source_checks_required"),
])
def test_invalid_seed_duplicate_and_declared_family_leakage_refused(tmp_path, change, error):
    rows = [deepcopy(dataset.load_cases()[0])]
    change(rows)
    with pytest.raises(dataset.DatasetError, match=error):
        dataset.export_dataset(tmp_path / "bad", cases=rows)
    assert not (tmp_path / "bad").exists()


def test_missing_or_ambiguous_source_anchor_refused():
    case = deepcopy(dataset.load_cases()[0])
    case["source_checks"][0]["anchor"] = "source anchor no longer present"
    with pytest.raises(dataset.DatasetError, match="dataset_source_anchor_changed"):
        dataset.build_record(case)
    case["source_checks"][0]["anchor"] = "Unit"
    with pytest.raises(dataset.DatasetError, match="dataset_source_anchor_changed"):
        dataset.build_record(case)


@pytest.mark.parametrize("relative", ["../key.pem", "C:/key.pem", "/tmp/other.py", "catalog\\lab_guide.py", "AGENTS.md/../key.pem"])
def test_source_paths_stay_within_declared_repo(relative):
    with pytest.raises(dataset.DatasetError, match="dataset_source_path_invalid"):
        dataset._source_path(relative)


def test_existing_export_never_overwritten(exported):
    target, manifest = exported
    before = (target / "metadata.json").read_bytes()
    with pytest.raises(dataset.DatasetError, match="dataset_output_not_empty"):
        dataset.export_dataset(target, cases=[dataset.load_cases()[0]])
    assert (target / "metadata.json").read_bytes() == before
    assert dataset.validate_dataset(target)["dataset_digest"] == manifest["dataset_digest"]


def test_jsonl_tampering_refused_before_loading(exported, tmp_path):
    target = _copy_export(exported, tmp_path)
    with (target / "train.jsonl").open("ab") as handle:
        handle.write(b"{}\n")
    with pytest.raises(dataset.DatasetError, match="dataset_file_digest_mismatch"):
        dataset.load_exported_records(target)


def test_metadata_tampering_refused(exported, tmp_path):
    target = _copy_export(exported, tmp_path)
    value = json.loads((target / "metadata.json").read_text(encoding="utf-8"))
    value["cases"][0]["rubric"]["criteria"].append("altered")
    (target / "metadata.json").write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(dataset.DatasetError, match="dataset_manifest_digest_mismatch"):
        dataset.validate_dataset(target)


def test_rehashed_packet_cannot_replace_current_production_capabilities(exported, tmp_path):
    target = _copy_export(exported, tmp_path)
    manifest = deepcopy(exported[1])
    name = "train.jsonl"
    rows = [json.loads(line) for line in (target / name).read_text(encoding="utf-8").splitlines()]
    packet = json.loads(rows[0]["messages"][1]["content"])
    packet["assembly_catalog"]["unsupported"] = []
    rows[0]["messages"][:2] = assistant_messages(packet)
    record = {key: deepcopy(manifest["cases"][0][key])
              for key in ("id", "family", "split", "profile", "rubric", "provenance")}
    record.update(messages=rows[0]["messages"], packet=packet,
                  reference_answer=json.loads(rows[0]["messages"][2]["content"]))
    manifest["cases"][0] = dataset._record_metadata(record, 1)
    data = "".join(dataset._canonical(row) + "\n" for row in rows).encode("utf-8")
    (target / name).write_bytes(data)
    manifest["files"][name] = {"rows": len(rows), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    _write_manifest(target, manifest)
    with pytest.raises(dataset.DatasetError, match="dataset_packet_drift"):
        dataset.validate_dataset(target)


def test_current_source_drift_refuses_old_export(exported, monkeypatch):
    original = dataset._file_evidence
    def changed(relative):
        evidence = original(relative)
        if relative == "catalog/lab_guide.py":
            evidence["sha256"] = "0" * 64
        return evidence
    monkeypatch.setattr(dataset, "_file_evidence", changed)
    with pytest.raises(dataset.DatasetError, match="dataset_source_drift"):
        dataset.load_exported_records(exported[0])


@pytest.mark.parametrize("mutation,error", [
    (lambda value: value["validation"].update(semantic="passed"), "dataset_validation_claim_invalid"),
    (lambda value: value["cases"][0]["provenance"].update(human_review="approved"), "dataset_provenance_invalid"),
    (lambda value: value["cases"][0].update(family=value["cases"][-1]["family"]), "dataset_family_leakage"),
    (lambda value: value.update(source_files=[row for row in value["source_files"]
        if row["path"] != "catalog/assistant_dataset.py"]), "dataset_source_manifest_incomplete"),
    (lambda value: value["cases"][0].update(line=999), "dataset_record_invalid"),
])
def test_pinned_metadata_cannot_claim_unperformed_review_or_leak_split(exported, tmp_path, mutation, error):
    target = _copy_export(exported, tmp_path)
    manifest = deepcopy(exported[1])
    mutation(manifest)
    _write_manifest(target, manifest)
    with pytest.raises(dataset.DatasetError, match=error):
        dataset.validate_dataset(target)


def test_missing_export_file_refused(exported, tmp_path):
    target = _copy_export(exported, tmp_path)
    (target / "validation.jsonl").unlink()
    with pytest.raises(dataset.DatasetError, match="dataset_export_missing"):
        dataset.load_exported_records(target, split="train")


def test_duplicate_json_keys_refused():
    with pytest.raises(dataset.DatasetError, match="dataset_duplicate_json_key"):
        dataset._json('{"messages":[],"messages":[]}')
    with pytest.raises(dataset.DatasetError, match="dataset_nonfinite"):
        dataset._json('{"x":NaN}')


def test_empty_or_invalid_export_split_refused(tmp_path):
    with pytest.raises(dataset.DatasetError, match="dataset_cases_invalid"):
        dataset.export_dataset(tmp_path / "empty", cases=[])
    with pytest.raises(dataset.DatasetError, match="dataset_split_invalid"):
        dataset.load_exported_records(tmp_path, split="both")


def test_cli_reports_protocol_only(exported, capsys):
    assert dataset.main(["validate", str(exported[0])]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["protocol"] == "passed"
    assert report["semantic"] == "pending_independent_review"
    assert report["training"] == "not_run"
