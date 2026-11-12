"""Short source-checked practice data, with separate query-only grounding.

Old seed exports and experiment artifacts are never rewritten. Negative
examples are wrong user proposals followed by correct assistant targets; no
incorrect answer is labelled as a positive training target.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

from .assistant_cognition import SYSTEM
from .assistant_dataset import (
    DatasetError, _canonical, _digest, _file_evidence, _json, _read_export_file,
    _read_source, _source_check,
)

SCHEMA = "nsgablack.assistant_practice_dataset/v1"
PROFILE = "framework_cognition_practice/v1"
_PATH = Path(__file__).with_name("assistant_training") / "cognition_practice.json"
_SPLITS = ("train", "validation")
_KINDS = {"direct", "counterexample", "correction", "trace"}
_ID = re.compile(r"[a-z][a-z0-9_]{0,79}\Z")
_MODULES = ("catalog/assistant_practice.py", "catalog/assistant_training/cognition_practice.json",
            "catalog/assistant_dataset.py", "catalog/assistant_cognition.py")
_GROUNDING_MODULES = ("catalog/lab_framework.py", "catalog/lab_assembly.py")
_OLD_DIAGNOSTICS = ("bo_roles_01", "member_sigma_01", "nested_view_01", "cross_case_01", "evidence_recovery_01")


def _validate_seed(value: dict) -> tuple[dict, ...]:
    if (not isinstance(value, dict) or set(value) != {"schema", "version", "source_groups", "cases"}
            or value["schema"] != "nsgablack.assistant_practice_cases/v1"
            or not isinstance(value["version"], str) or not value["version"]
            or not isinstance(value["source_groups"], dict) or not value["source_groups"]
            or not isinstance(value["cases"], list) or not value["cases"]):
        raise DatasetError("practice_seed_invalid")
    sources = value["source_groups"]
    for name, checks in sources.items():
        if not isinstance(name, str) or not _ID.fullmatch(name) or not isinstance(checks, list) or not checks:
            raise DatasetError("practice_source_group_invalid")
        for check in checks:
            if (not isinstance(check, dict) or set(check) != {"path", "anchor"}
                    or any(not isinstance(check[key], str) or not check[key] for key in check)):
                raise DatasetError("practice_source_group_invalid")
    seen, inputs, families, result = set(), set(), {}, []
    required = {"id", "family", "split", "kind", "source_groups", "instruction", "answer", "rubric"}
    for case in value["cases"]:
        if not isinstance(case, dict) or set(case) != required:
            raise DatasetError("practice_case_invalid")
        for key in ("id", "family"):
            if not isinstance(case[key], str) or not _ID.fullmatch(case[key]):
                raise DatasetError("practice_identity_invalid")
        if case["id"] in seen:
            raise DatasetError("practice_duplicate_id")
        seen.add(case["id"])
        if (not isinstance(case["split"], str) or case["split"] not in _SPLITS
                or not isinstance(case["kind"], str) or case["kind"] not in _KINDS):
            raise DatasetError("practice_classification_invalid")
        if families.setdefault(case["family"], case["split"]) != case["split"]:
            raise DatasetError("practice_family_leakage")
        for field, maximum in (("instruction", 1600), ("answer", 900)):
            if not isinstance(case[field], str) or not 1 <= len(case[field]) <= maximum:
                raise DatasetError("practice_text_invalid")
        if case["instruction"] in inputs:
            raise DatasetError("practice_duplicate_question")
        inputs.add(case["instruction"])
        if (not isinstance(case["rubric"], list) or not case["rubric"]
                or any(not isinstance(item, str) or not item for item in case["rubric"])):
            raise DatasetError("practice_rubric_invalid")
        groups = case["source_groups"]
        if (not isinstance(groups, list) or not groups or any(not isinstance(group, str) for group in groups)
                or len(set(groups)) != len(groups)
                or any(group not in sources for group in groups)):
            raise DatasetError("practice_source_group_unknown")
        expanded = deepcopy(case)
        checks = {(_canonical(check)): check for group in groups for check in sources[group]}
        expanded["source_checks"] = deepcopy(list(checks.values()))
        result.append(expanded)
    return tuple(result)


def load_practice_cases() -> tuple[dict, ...]:
    """Load authored short tasks; no request to a model or source retrieval."""
    return _validate_seed(_json(_PATH.read_bytes()))


def build_practice_record(case: dict) -> dict:
    """Keep question, target and rubric separate; source checking is read-only."""
    # Only the fixed dataset schema is accepted; arbitrary source roots and
    # arbitrary prompt additions are not a public export configuration surface.
    required = {"id", "family", "split", "kind", "source_groups", "instruction", "answer", "rubric", "source_checks"}
    if not isinstance(case, dict) or set(case) != required:
        raise DatasetError("practice_case_invalid")
    checks = [_source_check(check) for check in case["source_checks"]]
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": case["instruction"]},
                {"role": "assistant", "content": case["answer"]}]
    return {"id": case["id"], "family": case["family"], "split": case["split"], "kind": case["kind"],
            "profile": PROFILE, "question": case["instruction"], "messages": messages,
            "reference_answer": case["answer"], "rubric": deepcopy(case["rubric"]),
            "provenance": {"review_status": "agent_source_checked", "independent_review": "pending",
                           "human_review": "not_done", "runtime_validation": "not_run",
                           "scenario": "authored_fixture", "source_checks": checks}}


def _grounding(record: dict, *, max_chars: int) -> tuple[dict, dict]:
    from .lab_framework import build_framework_facts
    # The retrieval call receives only the original user question. In
    # particular it cannot inspect source_checks, rubric or reference_answer.
    facts = build_framework_facts(record["question"], max_chars=max_chars)
    row = {"sample_id": record["id"], "split": record["split"],
           "context": facts["text"], "source_refs": deepcopy(facts["evidence"])}
    trace = {"query_sha256": hashlib.sha256(record["question"].encode("utf-8")).hexdigest(),
             "context_sha256": hashlib.sha256(row["context"].encode("utf-8")).hexdigest(),
             "retrieval_context_sha256": facts["context_sha256"], "limitations": deepcopy(facts["limitations"])}
    return row, trace


def _metadata(record: dict, line: int) -> dict:
    return {key: deepcopy(record[key]) for key in ("id", "family", "split", "kind", "profile", "question", "rubric", "provenance")} | {
        "line": line, "messages_sha256": _digest(record["messages"]),
        "reference_sha256": hashlib.sha256(record["reference_answer"].encode("utf-8")).hexdigest(),
        "message_characters": [len(message["content"]) for message in record["messages"]],
        "token_count": None, "tokenizer": None}


def export_practice_dataset(output_dir: str | Path, *, include_grounding: bool = True, max_chars: int = 2200) -> dict:
    """Export plain messages and optional query-grounding sidecar, never train.

    The ML consumer explicitly joins grounding by (split, id), producing its own
    prepared training input. Plain data and the original question stay intact.
    """
    if type(include_grounding) is not bool or type(max_chars) is not int or not 500 <= max_chars <= 4000:
        raise DatasetError("practice_export_options_invalid")
    output = Path(output_dir)
    if output.exists():
        raise DatasetError("practice_output_already_exists")
    records = [build_practice_record(case) for case in load_practice_cases()]
    payloads, metadata, traces, source_paths = {}, [], {}, set(_MODULES)
    for record in records:
        source_paths.update(source["path"] for source in record["provenance"]["source_checks"])
    for split in _SPLITS:
        selected = [record for record in records if record["split"] == split]
        rows = [{"id": record["id"], "messages": record["messages"]} for record in selected]
        payloads[split + ".jsonl"] = ("".join(_canonical(row) + "\n" for row in rows)).encode("utf-8")
        metadata.extend(_metadata(record, line) for line, record in enumerate(selected, 1))
    if include_grounding:
        source_paths.update(_GROUNDING_MODULES)
        rows = []
        for record in records:
            row, trace = _grounding(record, max_chars=max_chars)
            rows.append(row)
            traces[record["id"]] = trace
            source_paths.update(evidence["source"]["path"] for evidence in row["source_refs"])
        payloads["grounding.jsonl"] = "".join(_canonical(row) + "\n" for row in rows).encode("utf-8")
    payloads["metadata.json"] = json.dumps({"records": metadata, "retrieval_traces": traces}, ensure_ascii=False, indent=2).encode("utf-8")
    manifest = {"schema": SCHEMA, "profile": PROFILE, "version": _json(_PATH.read_bytes())["version"],
        "counts": dict(Counter(record["split"] for record in records)),
        "include_grounding": include_grounding, "facts_max_chars": max_chars if include_grounding else None,
        "files": {name: {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)} for name, data in payloads.items()},
        "source_files": [_file_evidence(path) for path in sorted(source_paths)],
        "old_test_status": {"status": "development_diagnostics", "ids": list(_OLD_DIAGNOSTICS),
                            "used_for_failure_analysis": True, "included_in_training": False},
        "validation": {"structure": "passed", "semantic": "pending_independent_review", "model_execution": "not_run", "training": "not_run"},
        "limitations": ["48条训练与8条验证为源码核对样本，并非独立人审或模型效果证据。",
                        "本包没有test；旧五题已用于开发诊断，不能再称未见验收。",
                        "grounding只按原始问题真实检索，不使用rubric、参考答案或source_checks选择材料。",
                        "不截断消息；真实分词长度与上下文拼接由ML入口检查。"]}
    manifest["dataset_digest"] = _digest(manifest)
    output.mkdir(parents=True)
    for name, data in payloads.items():
        with (output / name).open("xb") as handle:
            handle.write(data)
    with (output / "manifest.json").open("x", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
    validate_practice_dataset(output)
    return manifest


def validate_practice_dataset(output_dir: str | Path) -> dict:
    """Check shapes, identities and pinned sources; do not grade semantics."""
    root = Path(output_dir)
    manifest = _json(_read_export_file(root, "manifest.json"))
    if (not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA or manifest.get("profile") != PROFILE
            or type(manifest.get("include_grounding")) is not bool):
        raise DatasetError("practice_manifest_invalid")
    unsigned = {key: value for key, value in manifest.items() if key != "dataset_digest"}
    if manifest.get("dataset_digest") != _digest(unsigned):
        raise DatasetError("practice_manifest_digest_mismatch")
    expected_files = {"train.jsonl", "validation.jsonl", "metadata.json"}
    if manifest["include_grounding"]:
        if type(manifest.get("facts_max_chars")) is not int or not 500 <= manifest["facts_max_chars"] <= 4000:
            raise DatasetError("practice_export_options_invalid")
        expected_files.add("grounding.jsonl")
    if set(manifest.get("files", {})) != expected_files:
        raise DatasetError("practice_export_files_invalid")
    source_files = manifest.get("source_files")
    if not isinstance(source_files, list) or not source_files:
        raise DatasetError("practice_sources_invalid")
    sources = {}
    for source in source_files:
        if not isinstance(source, dict) or set(source) != {"repository", "path", "sha256"}:
            raise DatasetError("practice_sources_invalid")
        if source["path"] in sources or _file_evidence(source["path"]) != source:
            raise DatasetError("practice_source_drift")
        sources[source["path"]] = source
    modules = set(_MODULES) | (set(_GROUNDING_MODULES) if manifest["include_grounding"] else set())
    if not modules <= set(sources):
        raise DatasetError("practice_sources_incomplete")
    prepared = {}
    for name in expected_files:
        data = _read_export_file(root, name)
        if manifest["files"][name] != {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}:
            raise DatasetError("practice_file_digest_mismatch")
        prepared[name] = data
    meta = _json(prepared["metadata.json"])
    if not isinstance(meta, dict) or set(meta) != {"records", "retrieval_traces"}:
        raise DatasetError("practice_metadata_invalid")
    records = [build_practice_record(case) for case in load_practice_cases()]
    expected_metadata = []
    for split in _SPLITS:
        selected = [record for record in records if record["split"] == split]
        actual = [_json(row) for row in prepared[split + ".jsonl"].splitlines()]
        expected = [{"id": record["id"], "messages": record["messages"]} for record in selected]
        if actual != expected:
            raise DatasetError("practice_messages_mismatch")
        expected_metadata.extend(_metadata(record, line) for line, record in enumerate(selected, 1))
    if meta["records"] != expected_metadata:
        raise DatasetError("practice_metadata_mismatch")
    for record in records:
        if any(source["path"] not in sources for source in record["provenance"]["source_checks"]):
            raise DatasetError("practice_sources_incomplete")
    if manifest["include_grounding"]:
        rows = [_json(row) for row in prepared["grounding.jsonl"].splitlines()]
        if len(rows) != len(records) or set(meta["retrieval_traces"]) != {record["id"] for record in records}:
            raise DatasetError("practice_grounding_count_mismatch")
        for record, row in zip(records, rows):
            if (not isinstance(row, dict) or set(row) != {"sample_id", "split", "context", "source_refs"}
                    or row["sample_id"] != record["id"] or row["split"] != record["split"]
                    or not isinstance(row["context"], str) or not row["context"]
                    or not isinstance(row["source_refs"], list)):
                raise DatasetError("practice_grounding_identity_mismatch")
            trace = meta["retrieval_traces"][record["id"]]
            if (trace.get("query_sha256") != hashlib.sha256(record["question"].encode("utf-8")).hexdigest()
                    or trace.get("context_sha256") != hashlib.sha256(row["context"].encode("utf-8")).hexdigest()):
                raise DatasetError("practice_grounding_digest_mismatch")
            expected_row, expected_trace = _grounding(record, max_chars=manifest["facts_max_chars"])
            if row != expected_row or trace != expected_trace:
                raise DatasetError("practice_grounding_retrieval_mismatch")
            for evidence in row["source_refs"]:
                source = evidence.get("source", {})
                if source.get("path") not in sources or sources[source["path"]]["sha256"] != source.get("sha256"):
                    raise DatasetError("practice_grounding_source_drift")
                lines = _read_source(source["path"]).decode("utf-8-sig").splitlines()
                start, end = source.get("line"), source.get("end_line")
                if (type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(lines)
                        or "\n".join(lines[start - 1:end]) != evidence.get("excerpt")):
                    raise DatasetError("practice_grounding_excerpt_mismatch")
    elif meta["retrieval_traces"]:
        raise DatasetError("practice_unexpected_grounding")
    expected_old = {"status": "development_diagnostics", "ids": list(_OLD_DIAGNOSTICS),
                    "used_for_failure_analysis": True, "included_in_training": False}
    if manifest.get("old_test_status") != expected_old:
        raise DatasetError("practice_diagnostic_status_invalid")
    if manifest.get("validation") != {"structure": "passed", "semantic": "pending_independent_review",
                                      "model_execution": "not_run", "training": "not_run"}:
        raise DatasetError("practice_validation_claim_invalid")
    counts = dict(Counter(record["split"] for record in records))
    if manifest.get("counts") != counts:
        raise DatasetError("practice_counts_mismatch")
    return {"schema": SCHEMA, "dataset_digest": manifest["dataset_digest"], "counts": counts,
            "structure": "passed", "source_integrity": "passed", "semantic": "pending_independent_review",
            "old_test_status": "development_diagnostics", "model_execution": "not_run", "training": "not_run"}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="导出/核对短认知练习；不调用模型或运行训练")
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export")
    export.add_argument("output", type=Path)
    export.add_argument("--no-grounding", action="store_true")
    export.add_argument("--facts-max-chars", type=int, default=2200)
    validate = commands.add_parser("validate")
    validate.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "export":
            export_practice_dataset(args.output, include_grounding=not args.no_grounding, max_chars=args.facts_max_chars)
        report = validate_practice_dataset(args.output)
    except (ValueError, OSError) as exc:
        parser.exit(2, (str(exc) if isinstance(exc, DatasetError) else "practice_operation_failed") + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["load_practice_cases", "build_practice_record", "export_practice_dataset", "validate_practice_dataset", "main"]
