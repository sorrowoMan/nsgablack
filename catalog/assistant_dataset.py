"""Offline, source-pinned conversational data for the framework assistant.

This module builds the same input packet used by the workbench. It does not
call a model, execute a Case, consume a request, or turn protocol validation
into a claim that an answer is semantically correct.
"""
from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Mapping, Sequence
from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any


SCHEMA = "nsgablack.assistant_dataset/v1"
CASE_SCHEMA = "nsgablack.assistant_cases/v1"
PROFILE = "workbench_conversation"
SPLITS = ("train", "validation", "test")
_ROOT = Path(__file__).resolve().parents[1]
_CASES_PATH = Path(__file__).with_name("assistant_training") / "cases.json"
_ID = re.compile(r"[a-z][a-z0-9_]{0,79}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_REQUIRED_CASE = {"id", "family", "split", "instruction", "answer", "rubric", "source_checks"}
_OPTIONAL_CASE = {"design_notes", "history", "questions", "answer_notes", "answer_action"}
_SOURCE_MODULES = (
    "catalog/assistant_dataset.py", "catalog/assistant_training/cases.json",
    "catalog/lab_assistant.py", "catalog/lab_assembly.py", "catalog/lab_guide.py",
    "catalog/lab_framework.py", "catalog/lab_design.py", "catalog/lab_jobs.py",
    "catalog/skills/framework-experiment-guide/SKILL.md",
)
_MAX_FILE_BYTES = 64 * 1024 * 1024


class DatasetError(ValueError):
    """An actionable fixed category, without echoing arbitrary input."""


def _json(raw: str | bytes) -> Any:
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise DatasetError("dataset_duplicate_json_key")
            value[key] = item
        return value

    try:
        return json.loads(raw, object_pairs_hook=unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(DatasetError("dataset_nonfinite")))
    except (ValueError, UnicodeError) as exc:
        if isinstance(exc, DatasetError):
            raise
        raise DatasetError("dataset_json_invalid") from None


def _canonical(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (ValueError, TypeError):
        raise DatasetError("dataset_json_invalid") from None


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _source_path(relative: str) -> Path:
    if (not isinstance(relative, str) or "\\" in relative or not relative
            or PurePosixPath(relative).is_absolute() or ".." in PurePosixPath(relative).parts
            or ":" in relative or PurePosixPath(relative).suffix not in {".py", ".md", ".toml", ".json"}):
        raise DatasetError("dataset_source_path_invalid")
    root = _ROOT.resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise DatasetError("dataset_source_path_invalid")
    return path


def _read_source(relative: str) -> bytes:
    try:
        data = _source_path(relative).read_bytes()
    except OSError:
        raise DatasetError("dataset_source_unavailable") from None
    if not data or len(data) > _MAX_FILE_BYTES:
        raise DatasetError("dataset_source_size_invalid")
    return data


def _file_evidence(relative: str) -> dict:
    return {"repository": "nsgablack", "path": relative,
            "sha256": hashlib.sha256(_read_source(relative)).hexdigest()}


def _source_check(check: Mapping) -> dict:
    if (not isinstance(check, Mapping) or set(check) != {"path", "anchor"}
            or not isinstance(check["anchor"], str) or not check["anchor"]):
        raise DatasetError("dataset_source_check_invalid")
    data = _read_source(check["path"])
    try:
        lines = data.decode("utf-8-sig").splitlines()
    except UnicodeError:
        raise DatasetError("dataset_source_encoding_invalid") from None
    starts = [i for i, line in enumerate(lines) if check["anchor"] in line]
    if len(starts) != 1:
        raise DatasetError("dataset_source_anchor_changed")
    start = starts[0]
    return {"repository": "nsgablack", "path": check["path"], "anchor": check["anchor"],
            "line": start + 1, "end_line": min(len(lines), start + 8),
            "sha256": hashlib.sha256(data).hexdigest(),
            "excerpt": "\n".join(lines[start:start + 8])}


def _validate_cases(cases: Sequence[Mapping]) -> None:
    if not isinstance(cases, (tuple, list)) or not cases:
        raise DatasetError("dataset_cases_invalid")
    identities, inputs, families = set(), set(), {}
    for case in cases:
        if (not isinstance(case, Mapping) or not _REQUIRED_CASE <= set(case)
                or set(case) - _REQUIRED_CASE - _OPTIONAL_CASE):
            raise DatasetError("dataset_case_shape_invalid")
        for field in ("id", "family"):
            if not isinstance(case[field], str) or not _ID.fullmatch(case[field]):
                raise DatasetError("dataset_case_identity_invalid")
        if case["id"] in identities:
            raise DatasetError("dataset_duplicate_case")
        identities.add(case["id"])
        split = case["split"]
        if split not in SPLITS:
            raise DatasetError("dataset_split_invalid")
        if families.setdefault(case["family"], split) != split:
            raise DatasetError("dataset_family_leakage")
        for field, limit in (("instruction", 8192), ("answer", 1800)):
            if not isinstance(case[field], str) or not 1 <= len(case[field]) <= limit:
                raise DatasetError("dataset_case_text_invalid")
        request = _digest({key: case.get(key, "" if key == "design_notes" else [])
                           for key in ("instruction", "design_notes", "history")})
        if request in inputs:
            raise DatasetError("dataset_duplicate_input")
        inputs.add(request)
        rubric = case["rubric"]
        if (not isinstance(rubric, Mapping) or set(rubric) != {"delivery", "criteria", "forbidden_inferences"}
                or rubric["delivery"] not in {"discussion", "clarification", "draft"}
                or any(not isinstance(rubric[key], list) or not rubric[key]
                       or any(not isinstance(item, str) or not item for item in rubric[key])
                       for key in ("criteria", "forbidden_inferences"))):
            raise DatasetError("dataset_rubric_invalid")
        if not isinstance(case["source_checks"], list) or not case["source_checks"]:
            raise DatasetError("dataset_source_checks_required")


def load_cases() -> tuple[dict, ...]:
    """Read the authored, reviewed-against-source seed; no export/model call."""
    try:
        value = _json(_CASES_PATH.read_bytes())
    except OSError:
        raise DatasetError("dataset_seed_unavailable") from None
    if (not isinstance(value, dict) or set(value) != {"schema", "version", "cases"}
            or value["schema"] != CASE_SCHEMA or not isinstance(value["version"], str)):
        raise DatasetError("dataset_seed_invalid")
    _validate_cases(value["cases"])
    return tuple(deepcopy(value["cases"]))


def _reference_answer(case: Mapping, packet: Mapping) -> dict:
    draft = None
    changes = []
    evidence = []
    action = case.get("answer_action")
    if action is not None:
        if not isinstance(action, Mapping):
            raise DatasetError("dataset_action_invalid")
        draft = deepcopy(packet["assembly"])
        if action.get("kind") == "seed" and set(action) == {"kind", "value"}:
            draft["seed"] = action["value"]
            changes = ["随机种子改为 " + str(action["value"])]
            evidence = [draft["nodes"][0]["component"]]
        elif action == {"kind": "expression"}:
            draft["dimension"] = 1
            draft["problem"] = {"component": "problem.expression", "parameters": {
                "variables": [{"name": "x", "low": 0., "high": 2., "type": "continuous"}],
                "objectives": [{"name": "平方", "expression": "x**2", "direction": "min"}],
                "constraints": []}}
            draft["pipeline"]["initializer"] = {"component": "repr.problem_uniform", "parameters": {}}
            changes = ["定义 x 的连续边界与平方最小化目标", "同步 dimension=1 和问题边界初始化"]
            evidence = ["problem.expression", "repr.problem_uniform"]
        else:
            raise DatasetError("dataset_action_invalid")
    # Cite only factual IDs actually present in the production retrieval packet.
    # No expected answer/rubric/source-check metadata is inserted in that packet.
    if not evidence:
        evidence = [row["id"] for row in packet["framework_context"]["contracts"]]
    answer = {"base_digest": packet["base_digest"], "draft": draft,
              "explanation": case["answer"], "changes": changes,
              "questions": deepcopy(case.get("questions", [])), "evidence_keys": evidence}
    if "answer_notes" in case:
        answer["design_notes"] = case["answer_notes"]
    return answer


def build_record(case: Mapping) -> dict:
    """Build production messages plus separate reference/rubric/provenance.

    Labels are available to offline evaluators only. Pass ``record['packet']``
    (or ``messages[:2]``) to inference, never the complete record.
    """
    _validate_cases([case])
    from .lab_assembly import assembly_from_recipe
    from .lab_assistant import build_assistant_packet, assistant_messages, validate_draft

    packet = build_assistant_packet(assembly_from_recipe("ga"), instruction=case["instruction"],
        guide_context={"stage": "assembly", "design_notes": case.get("design_notes", ""),
                       "history": deepcopy(case.get("history", []))})
    checks = [_source_check(item) for item in case["source_checks"]]
    reference = _reference_answer(case, packet)
    validated = validate_draft(reference, base_digest=packet["base_digest"],
                               catalog=packet["assembly_catalog"], framework_context=packet["framework_context"])
    expected = case["rubric"]["delivery"]
    actual = ("draft" if reference["draft"] is not None else
              "clarification" if reference["questions"] else "discussion")
    if actual != expected or validated["verification_status"] != "not_run":
        raise DatasetError("dataset_reference_delivery_invalid")
    messages = assistant_messages(packet)
    messages.append({"role": "assistant", "content": _canonical(reference)})
    return {"id": case["id"], "family": case["family"], "split": case["split"],
            "profile": PROFILE, "messages": messages, "packet": deepcopy(packet),
            "reference_answer": reference, "rubric": deepcopy(case["rubric"]),
            "provenance": {"review_status": "agent_source_checked", "human_review": "not_done",
                           "runtime_validation": "not_run", "scenario": "authored_fixture",
                           "source_checks": checks}}


def _record_metadata(record: Mapping, line: int) -> dict:
    messages = record["messages"]
    return {key: deepcopy(record[key]) for key in ("id", "family", "split", "profile", "rubric", "provenance")} | {
        "line": line, "messages_sha256": _digest(messages), "packet_sha256": _digest(record["packet"]),
        "reference_sha256": _digest(record["reference_answer"]),
        "message_characters": [len(row["content"]) for row in messages],
        "message_utf8_bytes": [len(row["content"].encode("utf-8")) for row in messages],
        "token_count": None, "tokenizer": None}


def export_dataset(output_dir: str | Path, *, cases: Sequence[Mapping] | None = None) -> dict:
    """Export HF conversational JSONL and a pinned metadata manifest offline.

    A new or empty directory is required. No existing corpus is overwritten.
    ``test.jsonl`` contains references for an offline evaluator, but is never
    merged into ``train.jsonl``. The manifest explicitly records this boundary.
    """
    selected = load_cases() if cases is None else tuple(deepcopy(cases))
    _validate_cases(selected)
    records = [build_record(case) for case in selected]
    from .lab_assistant import PROMPT_VERSION
    from .lab_guide import read_guide

    sources = set(_SOURCE_MODULES)
    for record in records:
        sources.update(row["path"] for row in record["provenance"]["source_checks"])
        for group in ("contracts", "components"):
            sources.update(row["source"]["path"] for row in record["packet"]["framework_context"][group])
    manifest = {"schema": SCHEMA, "profile": PROFILE, "dataset_version": _json(_CASES_PATH.read_bytes())["version"],
                "prompt_version": PROMPT_VERSION, "guide_metadata": read_guide()["metadata"],
                "source_files": [_file_evidence(path) for path in sorted(sources)], "files": {}, "cases": [],
                "validation": {"protocol": "passed", "semantic": "pending_independent_review",
                               "model_execution": "not_run", "training": "not_run"},
                "split_policy": "family_disjoint; test references excluded from training and inference packets",
                "length_policy": "full production context; tokenize before training; never silently truncate"}
    payloads = {}
    for split in SPLITS:
        rows = [row for row in records if row["split"] == split]
        data = "".join(_canonical({"messages": row["messages"]}) + "\n" for row in rows).encode("utf-8")
        name = split + ".jsonl"
        payloads[name] = data
        manifest["files"][name] = {"rows": len(rows), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
        manifest["cases"].extend(_record_metadata(row, i) for i, row in enumerate(rows, 1))
    manifest["dataset_digest"] = _digest(manifest)
    output = Path(output_dir)
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise DatasetError("dataset_output_not_empty")
    output.mkdir(parents=True, exist_ok=True)
    for name, data in payloads.items():
        with (output / name).open("xb") as handle:
            handle.write(data)
    with (output / "metadata.json").open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    validate_dataset(output)
    return deepcopy(manifest)


def _read_export_file(root: Path, name: str) -> bytes:
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()):
        raise DatasetError("dataset_export_path_invalid")
    try:
        data = path.read_bytes()
    except OSError:
        raise DatasetError("dataset_export_missing") from None
    if len(data) > _MAX_FILE_BYTES:
        raise DatasetError("dataset_export_too_large")
    return data


def _load_export(output_dir: str | Path) -> tuple[dict, tuple[dict, ...]]:
    root = Path(output_dir)
    manifest = _json(_read_export_file(root, "metadata.json"))
    if (not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA or manifest.get("profile") != PROFILE
            or set(manifest.get("files", {})) != {split + ".jsonl" for split in SPLITS}
            or not isinstance(manifest.get("cases"), list) or not manifest["cases"]
            or not isinstance(manifest.get("source_files"), list) or not manifest["source_files"]):
        raise DatasetError("dataset_manifest_invalid")
    unsigned = {key: value for key, value in manifest.items() if key != "dataset_digest"}
    if manifest.get("dataset_digest") != _digest(unsigned):
        raise DatasetError("dataset_manifest_digest_mismatch")
    source_paths = set()
    for source in manifest["source_files"]:
        if (not isinstance(source, dict) or set(source) != {"repository", "path", "sha256"}
                or source["repository"] != "nsgablack" or not isinstance(source["sha256"], str)
                or not _SHA.fullmatch(source["sha256"]) or source["path"] in source_paths):
            raise DatasetError("dataset_source_manifest_invalid")
        source_paths.add(source["path"])
        if _file_evidence(source["path"]) != source:
            raise DatasetError("dataset_source_drift")
    if not set(_SOURCE_MODULES) <= source_paths:
        raise DatasetError("dataset_source_manifest_incomplete")
    from .lab_assistant import PROMPT_VERSION, assistant_messages, build_assistant_packet, validate_draft
    from .lab_guide import read_guide
    if manifest.get("prompt_version") != PROMPT_VERSION or manifest.get("guide_metadata") != read_guide()["metadata"]:
        raise DatasetError("dataset_prompt_drift")
    if manifest.get("validation") != {"protocol": "passed", "semantic": "pending_independent_review",
                                      "model_execution": "not_run", "training": "not_run"}:
        raise DatasetError("dataset_validation_claim_invalid")
    meta_by_position, identities, families = {}, set(), {}
    for item in manifest["cases"]:
        if (not isinstance(item, dict) or item.get("split") not in SPLITS
                or type(item.get("line")) is not int or item["line"] < 1
                or not isinstance(item.get("id"), str) or not _ID.fullmatch(item["id"])
                or not isinstance(item.get("family"), str) or not _ID.fullmatch(item["family"])
                or item.get("profile") != PROFILE):
            raise DatasetError("dataset_case_metadata_invalid")
        key = (item["split"], item["line"])
        if key in meta_by_position or item["id"] in identities:
            raise DatasetError("dataset_duplicate_case")
        identities.add(item["id"])
        if families.setdefault(item["family"], item["split"]) != item["split"]:
            raise DatasetError("dataset_family_leakage")
        meta_by_position[key] = item
    records, message_hashes, input_hashes, consumed = [], set(), set(), set()
    for split in SPLITS:
        name = split + ".jsonl"
        data = _read_export_file(root, name)
        rows = data.splitlines()
        descriptor = manifest["files"][name]
        if descriptor != {"rows": len(rows), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}:
            raise DatasetError("dataset_file_digest_mismatch")
        for line, raw in enumerate(rows, 1):
            value = _json(raw)
            item = meta_by_position.get((split, line))
            if not isinstance(value, dict) or set(value) != {"messages"} or item is None:
                raise DatasetError("dataset_record_invalid")
            messages = value["messages"]
            if (not isinstance(messages, list) or len(messages) != 3
                    or any(not isinstance(row, dict) or set(row) != {"role", "content"}
                           or row["role"] != role or not isinstance(row["content"], str) or not row["content"]
                           for row, role in zip(messages, ("system", "user", "assistant")))):
                raise DatasetError("dataset_messages_invalid")
            packet, reference = _json(messages[1]["content"]), _json(messages[2]["content"])
            if not isinstance(packet, dict) or not isinstance(reference, dict):
                raise DatasetError("dataset_record_invalid")
            hashes = {"messages_sha256": _digest(messages), "packet_sha256": _digest(packet),
                      "reference_sha256": _digest(reference)}
            if any(item.get(key) != digest for key, digest in hashes.items()):
                raise DatasetError("dataset_record_digest_mismatch")
            if hashes["messages_sha256"] in message_hashes:
                raise DatasetError("dataset_duplicate_messages")
            message_hashes.add(hashes["messages_sha256"])
            if hashes["packet_sha256"] in input_hashes:
                raise DatasetError("dataset_duplicate_input")
            input_hashes.add(hashes["packet_sha256"])
            if assistant_messages(packet) != messages[:2]:
                raise DatasetError("dataset_prompt_mismatch")
            # A packet must remain the actual closed production packet shape,
            # with references/rubric never mixed into its model-visible input.
            if set(packet) != {"prompt_version", "base_digest", "assembly", "instruction", "assembly_catalog",
                               "problem_definition", "guide_context", "guide_metadata", "framework_context", "online_options"}:
                raise DatasetError("dataset_packet_shape_invalid")
            try:
                rebuilt = build_assistant_packet(packet["assembly"], instruction=packet["instruction"],
                                                  guide_context=packet["guide_context"])
            except Exception:
                raise DatasetError("dataset_packet_invalid") from None
            if rebuilt != packet:
                raise DatasetError("dataset_packet_drift")
            checked = validate_draft(reference, base_digest=packet["base_digest"],
                catalog=packet["assembly_catalog"], framework_context=packet["framework_context"])
            delivery = ("draft" if reference["draft"] is not None else
                        "clarification" if reference["questions"] else "discussion")
            rubric, provenance = item.get("rubric"), item.get("provenance")
            if (not isinstance(rubric, dict) or rubric.get("delivery") != delivery
                    or not isinstance(rubric.get("criteria"), list) or not rubric["criteria"]
                    or not isinstance(rubric.get("forbidden_inferences"), list)
                    or not isinstance(provenance, dict)
                    or provenance.get("review_status") != "agent_source_checked"
                    or provenance.get("human_review") != "not_done"
                    or provenance.get("runtime_validation") != "not_run"
                    or provenance.get("scenario") != "authored_fixture"
                    or not isinstance(provenance.get("source_checks"), list) or not provenance["source_checks"]
                    or checked["verification_status"] != "not_run"):
                raise DatasetError("dataset_provenance_invalid")
            for check in provenance["source_checks"]:
                if (not isinstance(check, dict) or check.get("path") not in source_paths
                        or _source_check({"path": check.get("path"), "anchor": check.get("anchor")}) != check):
                    raise DatasetError("dataset_source_check_drift")
            for group in ("contracts", "components"):
                for evidence in packet["framework_context"][group]:
                    source = evidence["source"]
                    if source["path"] not in source_paths or _file_evidence(source["path"])["sha256"] != source["sha256"]:
                        raise DatasetError("dataset_retrieval_source_drift")
            record = {key: deepcopy(item[key]) for key in ("id", "family", "split", "profile", "rubric", "provenance")}
            record.update(messages=messages, packet=packet, reference_answer=reference)
            if _record_metadata(record, line) != item:
                raise DatasetError("dataset_metadata_mismatch")
            records.append(record)
            consumed.add((split, line))
    if consumed != set(meta_by_position):
        raise DatasetError("dataset_metadata_rows_mismatch")
    return manifest, tuple(records)


def validate_dataset(output_dir: str | Path) -> dict:
    """Check provenance, split leakage, JSON protocol and current source drift.

    Passing this function does not grade free-text semantics or claim that a
    model, Case, training loop, or generated program has been run.
    """
    manifest, records = _load_export(output_dir)
    counts = Counter(row["split"] for row in records)
    return {"schema": SCHEMA, "dataset_digest": manifest["dataset_digest"], "records": len(records),
            "splits": {split: counts[split] for split in SPLITS}, "protocol": "passed",
            "source_integrity": "passed", "family_separation": "passed",
            "semantic": "pending_independent_review", "model_execution": "not_run", "training": "not_run"}


def load_exported_records(output_dir: str | Path, *, split: str = "test") -> tuple[dict, ...]:
    """Load only after the full exported corpus passes integrity validation."""
    if split not in SPLITS:
        raise DatasetError("dataset_split_invalid")
    _, records = _load_export(output_dir)
    return tuple(deepcopy(row) for row in records if row["split"] == split)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="离线导出/校验框架助手会话语料，不调用模型。")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("export", "validate"):
        command = commands.add_parser(name)
        command.add_argument("output_dir", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "export":
            export_dataset(args.output_dir)
        result = validate_dataset(args.output_dir)
    except (DatasetError, OSError, ValueError) as exc:
        parser.exit(2, "语料操作失败：" + (str(exc) if isinstance(exc, DatasetError) else "dataset_validation_failed") + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["DatasetError", "load_cases", "build_record", "export_dataset", "validate_dataset", "load_exported_records", "main"]
