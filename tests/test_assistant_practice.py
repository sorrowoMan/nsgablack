"""Short-practice provenance and transport checks; no semantic auto-grader."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
import shutil

import pytest

import nsgablack.catalog.assistant_practice as practice
from nsgablack.catalog.assistant_dataset import DatasetError, _canonical, _digest, _json


@pytest.fixture(scope="module")
def exports(tmp_path_factory):
    root = tmp_path_factory.mktemp("practice")
    old_seed = practice._PATH.with_name("cases.json")
    before = old_seed.read_bytes()
    plain = root / "plain"
    grounded = root / "grounded"
    practice.export_practice_dataset(plain, include_grounding=False)
    practice.export_practice_dataset(grounded)
    assert old_seed.read_bytes() == before
    return plain, grounded


def _seed():
    return _json(practice._PATH.read_bytes())


def _copy(exported, tmp_path):
    target = tmp_path / "copy"
    shutil.copytree(exported, target)
    return target


def _rehash_manifest(target, manifest):
    value = deepcopy(manifest)
    value.pop("dataset_digest", None)
    value["dataset_digest"] = _digest(value)
    (target / "manifest.json").write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _rehash_file(target, name, data):
    (target / name).write_bytes(data)
    manifest = _json((target / "manifest.json").read_bytes())
    manifest["files"][name] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    _rehash_manifest(target, manifest)


def test_practice_has_varied_tasks_and_no_test_or_old_diagnostics_in_training():
    cases = practice.load_practice_cases()
    assert len(cases) == 56
    assert Counter(case["split"] for case in cases) == {"train": 48, "validation": 8}
    assert Counter(case["kind"] for case in cases) == {"counterexample": 17, "trace": 16, "direct": 13, "correction": 10}
    train = [case for case in cases if case["split"] == "train"]
    validation = [case for case in cases if case["split"] == "validation"]
    assert {case["family"] for case in train}.isdisjoint(case["family"] for case in validation)
    assert {case["id"] for case in cases}.isdisjoint(practice._OLD_DIAGNOSTICS)
    assert len({case["instruction"] for case in cases}) == 56


@pytest.mark.parametrize("identity", [case["id"] for case in practice.load_practice_cases()])
def test_each_short_record_is_source_checked_but_not_claimed_reviewed_or_run(identity):
    case = next(case for case in practice.load_practice_cases() if case["id"] == identity)
    record = practice.build_practice_record(case)
    assert [row["role"] for row in record["messages"]] == ["system", "user", "assistant"]
    assert record["messages"][1]["content"] == case["instruction"] == record["question"]
    assert record["messages"][2]["content"] == case["answer"] == record["reference_answer"]
    assert case["answer"] not in record["messages"][1]["content"]
    assert all(term not in record["messages"][1]["content"] for term in ("source_checks", "rubric", "reference_answer"))
    provenance = record["provenance"]
    assert provenance["review_status"] == "agent_source_checked"
    assert provenance["human_review"] == "not_done"
    assert provenance["independent_review"] == "pending"
    assert provenance["runtime_validation"] == "not_run"
    assert len(provenance["source_checks"]) >= 2
    for source in provenance["source_checks"]:
        data = practice._read_source(source["path"])
        assert source["sha256"] == hashlib.sha256(data).hexdigest()
        lines = data.decode("utf-8-sig").splitlines()
        assert source["anchor"] in lines[source["line"] - 1]
        assert source["excerpt"] == "\n".join(lines[source["line"] - 1:source["end_line"]])


def test_plain_and_grounded_packages_keep_identical_plain_inputs(exports):
    plain, grounded = exports
    for split in ("train", "validation"):
        assert (plain / (split + ".jsonl")).read_bytes() == (grounded / (split + ".jsonl")).read_bytes()
        rows = [_json(row) for row in (plain / (split + ".jsonl")).read_bytes().splitlines()]
        assert all(set(row) == {"id", "messages"} for row in rows)
    assert not (plain / "grounding.jsonl").exists()
    assert not (grounded / "test.jsonl").exists()
    manifest = _json((grounded / "manifest.json").read_bytes())
    assert manifest["old_test_status"]["status"] == "development_diagnostics"
    assert manifest["old_test_status"]["used_for_failure_analysis"] is True
    assert manifest["old_test_status"]["included_in_training"] is False
    assert manifest["validation"]["semantic"] == "pending_independent_review"


def test_grounding_sidecar_uses_explicit_ids_and_exact_current_source_evidence(exports):
    _, grounded = exports
    rows = [_json(row) for row in (grounded / "grounding.jsonl").read_bytes().splitlines()]
    cases = practice.load_practice_cases()
    assert len(rows) == 56
    assert [(row["sample_id"], row["split"]) for row in rows] == [(case["id"], case["split"]) for case in cases]
    assert all(set(row) == {"sample_id", "split", "context", "source_refs"} for row in rows)
    assert all(row["source_refs"] for row in rows)
    assert all(len(row["context"]) <= 2200 for row in rows)
    assert practice.validate_practice_dataset(grounded)["source_integrity"] == "passed"


def test_grounding_call_never_receives_reference_rubric_or_source_checks(monkeypatch):
    import nsgablack.catalog.lab_framework as framework
    calls = []
    def facts(instruction, **kwargs):
        calls.append((instruction, kwargs))
        return {"text": "current query facts", "evidence": [], "context_sha256": "a" * 64, "limitations": []}
    monkeypatch.setattr(framework, "build_framework_facts", facts)
    record = practice.build_practice_record(practice.load_practice_cases()[0])
    row, trace = practice._grounding(record, max_chars=2200)
    poisoned = deepcopy(record)
    poisoned["reference_answer"] = "private-gold-canary"
    poisoned["rubric"] = ["private-rubric-canary"]
    poisoned["provenance"]["source_checks"] = [{"path": "private-source-canary"}]
    second, other_trace = practice._grounding(poisoned, max_chars=2200)
    assert row == second and trace == other_trace
    assert calls == [(record["question"], {"max_chars": 2200})] * 2


def test_no_model_job_training_or_old_export_is_invoked(tmp_path, monkeypatch):
    import nsgablack.catalog.lab_assistant as assistant
    import nsgablack.catalog.assistant_dataset as original
    def forbidden(*args, **kwargs):
        raise AssertionError("practice must stay offline")
    monkeypatch.setattr(assistant.DeepSeekAssemblyGenerator, "generate", forbidden)
    monkeypatch.setattr(assistant.AssistantManager, "submit", forbidden)
    monkeypatch.setattr(original, "export_dataset", forbidden)
    target = tmp_path / "offline"
    practice.export_practice_dataset(target, include_grounding=False)
    report = practice.validate_practice_dataset(target)
    assert report["model_execution"] == report["training"] == "not_run"


@pytest.mark.parametrize("mutation,error", [
    (lambda value: value["cases"].append(deepcopy(value["cases"][0])), "practice_duplicate_id"),
    (lambda value: value["cases"].append(dict(deepcopy(value["cases"][0]), id="same_question")), "practice_duplicate_question"),
    (lambda value: value["cases"][0].update(split="validation"), "practice_family_leakage"),
    (lambda value: value["cases"][0].update(source_groups=["missing"]), "practice_source_group_unknown"),
    (lambda value: value["cases"][0].update(split="test"), "practice_classification_invalid"),
    (lambda value: value["cases"][0].update(kind="wrong_answer_as_target"), "practice_classification_invalid"),
    (lambda value: value["cases"][0].update(rubric=[]), "practice_rubric_invalid"),
])
def test_seed_rejects_duplicates_leakage_and_unreviewable_rows(mutation, error):
    value = _seed()
    mutation(value)
    with pytest.raises(DatasetError, match=error):
        practice._validate_seed(value)


def test_changed_source_anchor_is_rejected():
    case = deepcopy(practice.load_practice_cases()[0])
    case["source_checks"][0]["anchor"] = "anchor no longer present"
    with pytest.raises(DatasetError, match="dataset_source_anchor_changed"):
        practice.build_practice_record(case)


def test_export_never_overwrites_existing_experiment(exports):
    path = exports[0]
    before = (path / "manifest.json").read_bytes()
    with pytest.raises(DatasetError, match="practice_output_already_exists"):
        practice.export_practice_dataset(path)
    assert before == (path / "manifest.json").read_bytes()


def test_modified_jsonl_is_rejected(exports, tmp_path):
    target = _copy(exports[0], tmp_path)
    with (target / "train.jsonl").open("ab") as handle:
        handle.write(b"{}\n")
    with pytest.raises(DatasetError, match="practice_file_digest_mismatch"):
        practice.validate_practice_dataset(target)


def test_rehashed_jsonl_cannot_inject_gold_into_user_input(exports, tmp_path):
    target = _copy(exports[0], tmp_path)
    rows = [_json(row) for row in (target / "train.jsonl").read_bytes().splitlines()]
    rows[0]["messages"][1]["content"] += "\n" + rows[0]["messages"][2]["content"]
    _rehash_file(target, "train.jsonl", "".join(_canonical(row) + "\n" for row in rows).encode("utf-8"))
    with pytest.raises(DatasetError, match="practice_messages_mismatch"):
        practice.validate_practice_dataset(target)


def test_rehashed_grounding_cannot_silently_bind_wrong_id(exports, tmp_path):
    target = _copy(exports[1], tmp_path)
    rows = [_json(row) for row in (target / "grounding.jsonl").read_bytes().splitlines()]
    rows[0]["sample_id"] = "other-task"
    _rehash_file(target, "grounding.jsonl", "".join(_canonical(row) + "\n" for row in rows).encode("utf-8"))
    with pytest.raises(DatasetError, match="practice_grounding_identity_mismatch"):
        practice.validate_practice_dataset(target)


def test_rehashed_grounding_context_must_be_actual_query_retrieval(exports, tmp_path):
    target = _copy(exports[1], tmp_path)
    rows = [_json(row) for row in (target / "grounding.jsonl").read_bytes().splitlines()]
    rows[0]["context"] = "forged facts selected from gold"
    metadata = _json((target / "metadata.json").read_bytes())
    metadata["retrieval_traces"][rows[0]["sample_id"]]["context_sha256"] = hashlib.sha256(rows[0]["context"].encode()).hexdigest()
    _rehash_file(target, "metadata.json", json.dumps(metadata, ensure_ascii=False).encode("utf-8"))
    _rehash_file(target, "grounding.jsonl", "".join(_canonical(row) + "\n" for row in rows).encode("utf-8"))
    with pytest.raises(DatasetError, match="practice_grounding_retrieval_mismatch"):
        practice.validate_practice_dataset(target)


@pytest.mark.parametrize("mutation,error", [
    (lambda manifest: manifest["validation"].update(semantic="passed"), "practice_validation_claim_invalid"),
    (lambda manifest: manifest["old_test_status"].update(status="new_held_out"), "practice_diagnostic_status_invalid"),
    (lambda manifest: manifest.update(counts={"train": 56, "validation": 0}), "practice_counts_mismatch"),
])
def test_unperformed_validation_claims_and_legacy_status_are_refused(exports, tmp_path, mutation, error):
    target = _copy(exports[0], tmp_path)
    manifest = _json((target / "manifest.json").read_bytes())
    mutation(manifest)
    _rehash_manifest(target, manifest)
    with pytest.raises(DatasetError, match=error):
        practice.validate_practice_dataset(target)


def test_source_drift_refuses_stale_package(exports, monkeypatch):
    original = practice._file_evidence
    def changed(path):
        result = original(path)
        if path == "catalog/assistant_practice.py":
            result["sha256"] = "0" * 64
        return result
    monkeypatch.setattr(practice, "_file_evidence", changed)
    with pytest.raises(DatasetError, match="practice_source_drift"):
        practice.validate_practice_dataset(exports[0])


def test_cli_reports_structure_not_model_quality(exports, capsys):
    assert practice.main(["validate", str(exports[0])]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["structure"] == "passed"
    assert report["semantic"] == "pending_independent_review"
    assert report["old_test_status"] == "development_diagnostics"
