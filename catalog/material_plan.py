"""Plan offline Catalog teaching material from supplied JSON, without generation.

Run ``python -m nsgablack.catalog.material_plan --input examples.json``;
``--ai-records records.json`` adds an independent inventory of supplied notes.
The default output is JSON on stdout; only explicit ``--output`` writes a file.
No component, tutorial, model, database or network API is executed by this tool.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .curation_seed import extract_source_guide_seed
from .usage_learning import (documentation_baseline_parts, documentation_fields,
                             documentation_variations, select_documentation_guide)


CATEGORIES = ("detailed_with_variants", "complete_main", "migration_reference", "source_fragment",
              "documentation_navigation", "project_case_navigation", "missing_source")
_FIELDS = {
    "use_when": ("什么时候用",),
    "preparation": ("先准备什么", "输入与前提", "输入与位置", "输入"),
    "placement": ("放在哪", "装配位置"),
    "steps": ("接入步骤",),
    "result_checks": ("怎样判断接对", "预期输出", "预期结果", "输出与消费"),
    "entrypoint": ("运行入口",),
}
_SIX_LABELS = {"什么时候用", "先准备什么", "放在哪", "接入步骤", "怎样判断接对", "运行入口"}
_PLACEHOLDER = re.compile(
    r"同一正式\s*Case\s*已构造的\s*solver\s*与问题候选管线|"
    r"得到已装配组件或回调返回值|结果检查说明待补|尚未提供可照做|"
    r"结果待补|待补充|待完善|\bTODO\b|\bTBD\b", re.I)
_ACTIONS = {
    "detailed_with_variants": "可按来源展示完整主例和现有变体；不转成AI审核记录。",
    "complete_main": "可按来源展示主例；尚缺完整实质变体。",
    "migration_reference": "展示当前限制与具体替代接线；不能当作原组件已可装配或已运行。",
    "source_fragment": "按片段范围展示；先补所列前提、位置或结果检查缺口。",
    "documentation_navigation": "展示文档入口与来源，保持阅读导航语义。",
    "project_case_navigation": "展示原Project/Case入口和已声明命令；运行前阅读其真实配置。",
    "missing_source": "先补组件与来源的明确绑定，不能以通用说明代替用法。",
}


def _sha(value: str | bytes) -> str:
    return hashlib.sha256(value.encode("utf-8") if isinstance(value, str) else value).hexdigest()


def _measure(text: str) -> dict[str, int]:
    return {"chars": len(text), "utf8_bytes": len(text.encode("utf-8"))}


def _snippets(example: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    if example is None:
        return []
    return [item for item in example.get("snippets", ())
            if isinstance(item, Mapping) and isinstance(item.get("text"), str)
            and isinstance(item.get("path"), str)]


def _complete(example: Mapping[str, Any]) -> bool:
    snippets = _snippets(example)
    return bool(snippets) and all(item.get("complete") is True for item in snippets)


def _source_ref(snippet: Mapping[str, Any]) -> dict[str, Any]:
    result = {key: snippet[key] for key in (
        "path", "start_line", "end_line", "sha256", "file_sha256", "complete") if key in snippet}
    observed = _sha(snippet["text"])
    result.update(text_sha256=observed, text_size=_measure(snippet["text"]),
                  declared_excerpt_digest_matches=(observed == snippet["sha256"]
                    if isinstance(snippet.get("sha256"), str) else None),
                  proof_scope="supplied_index_excerpt; source files not reopened")
    return result


def _primary(key: str, examples: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    guide = select_documentation_guide(examples)
    if guide is not None:
        return guide
    candidates = [example for example in examples if _snippets(example) or example.get("run_command")]
    if not candidates:
        return None
    return min(candidates, key=lambda item: (
        item.get("binding") != "focused", not _complete(item),
        item.get("kind") not in ({"project", "case"} if key.startswith("example.") else {"documentation"}),
    ))


def _python_info(parts: Sequence[tuple[str, str, str | None]]) -> dict[str, Any]:
    blocks = [text for kind, text, language in parts if kind == "code" and language == "python" and text.strip()]
    issues, substantive = [], False
    for index, text in enumerate(blocks):
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            issues.append({"block_index": index, "line": exc.lineno, "code": "python_syntax_invalid"})
            continue
        if any(isinstance(node, ast.Constant) and node.value is Ellipsis for node in ast.walk(tree)):
            issues.append({"block_index": index, "code": "python_placeholder_ellipsis"})
        substantive |= any(not isinstance(node, (ast.Import, ast.ImportFrom, ast.Pass))
                           and not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
                                    and isinstance(node.value.value, str)) for node in tree.body)
    return {"blocks": len(blocks), "substantive": substantive, "issues": issues,
            "code_size": _measure("".join(blocks)),
            "scope": "syntax only; signatures/imports/behavior not checked"}


def _ai_rows(payload: object) -> dict[str, list[Mapping[str, Any]]]:
    if payload is None:
        return {}
    if isinstance(payload, Mapping):
        payload = payload.get("records", payload.get("rows"))
    if not isinstance(payload, list):
        raise ValueError("AI records must be an exported list or records/rows list")
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for item in payload:
        if not isinstance(item, Mapping):
            raise ValueError("AI record rows must be objects")
        record = item.get("record", item)
        if not isinstance(record, Mapping):
            raise ValueError("AI record must be an object")
        key = item.get("key") or record.get("entry_key")
        if not isinstance(key, str) or not key:
            raise ValueError("AI records require key or entry_key")
        grouped[key].append(record)
    return dict(grouped)


def _ai_reference(records: Sequence[Mapping[str, Any]], sources: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not records:
        return {"status": "not_supplied", "completed_by_this_tool": False}
    if len(records) > 1:
        return {"status": "ambiguous_multiple_records", "count": len(records), "completed_by_this_tool": False}
    record = records[0]
    note = record.get("note") if isinstance(record.get("note"), Mapping) else {}
    review = note.get("tutorial_review") if isinstance(note.get("tutorial_review"), Mapping) else {}
    tutorial = note.get("tutorial") if isinstance(note.get("tutorial"), Mapping) else {}
    fragments = [tutorial.get("code", "")]
    fragments += [item.get("code", "") for item in tutorial.get("extensions", ()) if isinstance(item, Mapping)]
    text = "".join(item for item in fragments if isinstance(item, str))
    source_hashes = {item.get("path"): item.get("file_sha256") for item in sources if item.get("file_sha256")}
    matches, conflicts, unknown = set(), set(), set()
    for evidence in record.get("evidence", ()):
        if not isinstance(evidence, Mapping) or evidence.get("path") not in source_hashes:
            continue
        path = evidence["path"]
        if not isinstance(evidence.get("file_sha256"), str) or not evidence["file_sha256"]:
            unknown.add(path)
            continue
        (matches if evidence.get("file_sha256") == source_hashes[path] else conflicts).add(path)
    usage = record.get("usage") if isinstance(record.get("usage"), Mapping) else {}
    return {"status": "record_supplied", "source_digest": record.get("source_digest"),
            "generated_at": record.get("generated_at"), "declared_generator_model": record.get("model"),
            "declared_reviewer_model": usage.get("review_actual_model"),
            "declared_review_decision": review.get("decision"), "code_size": _measure(text),
            "shared_source_hash_matches": sorted(matches), "shared_source_hash_conflicts": sorted(conflicts),
            "shared_source_hash_unknown": sorted(unknown),
            "currency": "source_hash_conflict" if conflicts else "shared_files_match_only" if matches else "not_established",
            "completed_by_this_tool": False,
            "proof_scope": "supplied metadata only; no AI review, full packet digest or runtime revalidation"}


def build_material_plan(index: Mapping[str, Any], ai_records: object = None) -> dict[str, Any]:
    """Inventory supplied material without promoting fragments/notes to proof."""
    if not isinstance(index, Mapping) or not isinstance(index.get("entries"), Mapping) or not isinstance(index.get("examples"), Mapping):
        raise ValueError("Examples index requires entries and examples objects")
    examples_by_id, ai_by_key = index["examples"], _ai_rows(ai_records)
    categories, gaps, totals, records = Counter(), Counter(), Counter(), []
    # Aliases often share the same guide. Reuse pure parsing only within this
    # call, keyed by the actual supplied objects rather than declared IDs or
    # digests. Entry-specific issues, notes and receipts are still built below.
    primary_cache, material_cache = {}, {}
    index_issues = defaultdict(list)
    for issue in index.get("issues", ()):
        if isinstance(issue, Mapping):
            index_issues[issue.get("example_id")].append(str(issue.get("error", "index_issue")))
    for key, identifiers in index["entries"].items():
        if not isinstance(key, str) or not isinstance(identifiers, (list, tuple)):
            raise ValueError("Each entry must map a key to example identifiers")
        linked, entry_gaps = [], []
        for identifier in identifiers:
            example = examples_by_id.get(identifier) if isinstance(identifier, str) else None
            if not isinstance(example, Mapping):
                entry_gaps.append({"code": "missing_example_binding", "example_id": identifier})
                continue
            linked.append(example)
            for error in index_issues.get(identifier, ()):
                entry_gaps.append({"code": "index_source_issue", "example_id": identifier, "error": error})
        selection_key = (key.startswith("example."), tuple(id(item) for item in linked))
        if selection_key not in primary_cache:
            primary_cache[selection_key] = _primary(key, linked)
        primary = primary_cache[selection_key]
        is_doc = key.startswith("doc.") or (primary is not None and primary.get("kind") == "doc")
        is_project = primary is not None and primary.get("kind") in {"project", "case"}
        needs_seed = primary is not None and not (is_doc or is_project)
        material_key = (id(primary), needs_seed)
        if material_key not in material_cache:
            snippets = _snippets(primary)
            fields = documentation_fields(snippets)
            parts = [part for snippet in snippets for part in documentation_baseline_parts(snippet)]
            python = _python_info(parts)
            # The full extracted seed is large; the inventory only consumes
            # its presence and variant count, never its source fragments.
            seed = extract_source_guide_seed((primary,)) if needs_seed else None
            seed_count = len(seed["variants"]) if seed is not None else None
            material_cache[material_key] = (snippets, fields, python, seed_count,
                                            len(documentation_variations(snippets)))
        snippets, fields, parsed_python, seed_count, declared_count = material_cache[material_key]
        # Every output row remains independently mutable. Only these known
        # JSON analysis fields need copying; never deepcopy supplied objects.
        python = {**parsed_python, "issues": [dict(issue) for issue in parsed_python["issues"]],
                  "code_size": dict(parsed_python["code_size"])}
        field_plan = {}
        for role, names in _FIELDS.items():
            label = next((name for name in names if fields.get(name)), None)
            values = list(fields[label]) if label else []
            placeholders = [value for value in values if _PLACEHOLDER.search(value)]
            field_plan[role] = {"source_label": label,
                                "values": [value for value in values if value not in placeholders],
                                "placeholder_values": placeholders}
        # All teaching fields, code, source refs and completeness must describe
        # the same selected guide, even when an entry links several sources.
        complete_fields = (primary is not None and _complete(primary) and _SIX_LABELS <= fields.keys()
                           and all(field_plan[role]["values"] and not field_plan[role]["placeholder_values"] for role in _FIELDS))
        complete_main = (complete_fields and python["blocks"] > 0
                         and python["substantive"] and not python["issues"])
        if primary is None:
            category = "missing_source"
        elif is_doc:
            category = "documentation_navigation"
        elif is_project:
            category = "project_case_navigation"
        elif primary.get("usage_status") == "migration_reference" and complete_fields and not python["issues"]:
            category = "migration_reference"
        elif seed_count is not None:
            category = "detailed_with_variants"
        elif complete_main:
            category = "complete_main"
        elif snippets:
            category = "source_fragment"
        else:
            category = "missing_source"
        if category not in {"documentation_navigation", "project_case_navigation"}:
            for role, value in field_plan.items():
                if value["placeholder_values"]:
                    entry_gaps.append({"code": "placeholder_" + role, "source_label": value["source_label"]})
                elif not value["values"]:
                    entry_gaps.append({"code": "missing_" + role})
            if category not in {"detailed_with_variants", "migration_reference"}:
                entry_gaps.append({"code": "no_complete_substantive_variant"})
            if not python["blocks"] and category != "migration_reference":
                entry_gaps.append({"code": "no_baseline_python"})
        if snippets and not all(item.get("complete") is True for item in snippets):
            entry_gaps.append({"code": "incomplete_or_undeclared_excerpt"})
        entry_gaps += python["issues"]
        sources = [_source_ref(item) for item in snippets]
        for source in sources:
            if not source.get("file_sha256"):
                entry_gaps.append({"code": "missing_source_file_digest", "path": source["path"]})
            if source["declared_excerpt_digest_matches"] is False:
                entry_gaps.append({"code": "excerpt_digest_mismatch", "path": source["path"]})
        source_text = "".join(item["text"] for item in snippets)
        receipts = [{"example_id": item.get("id"), "verification": dict(item["verification"])} for item in linked
                    if isinstance(item.get("verification"), Mapping) and item["verification"].get("status") == "executed"]
        ai = _ai_reference(ai_by_key.get(key, ()), sources)
        record = {"key": key, "category": category, "primary_example_id": primary.get("id") if primary else None,
                  "next_action": _ACTIONS[category], "fields": field_plan, "gaps": entry_gaps,
                  "source_refs": sources, "source_text_size": _measure(source_text), "baseline_python": python,
                  "declared_variant_count": declared_count,
                  "complete_variant_count": seed_count if seed_count is not None else 0,
                  "declared_run_commands": [{"example_id": item.get("id"), "command": item["run_command"],
                      "working_directory": item.get("working_directory")} for item in linked if item.get("run_command")],
                  "proof": {"source_binding": "supplied_index_only_not_rechecked_against_files",
                      "declared_source_digests": [item.get("source_digest") for item in linked if item.get("source_digest")],
                      "declared_index_statuses": sorted({str((item.get("verification") or {}).get("status", "unverified")) for item in linked}),
                      "execution_status": "declared_receipt_not_revalidated" if receipts else "not_recorded",
                      "declared_execution_receipts": receipts, "component_execution": False, "ai_review_performed": False},
                  "ai_record": ai}
        categories[category] += 1
        gaps.update({item["code"] for item in entry_gaps})
        totals["selected_source_chars"] += len(source_text)
        totals["selected_source_utf8_bytes"] += len(source_text.encode("utf-8"))
        totals["baseline_python_blocks"] += python["blocks"]
        totals["entries_with_ai_record"] += bool(ai_by_key.get(key))
        totals["entries_with_declared_execution_receipt"] += bool(receipts)
        totals["entries_with_placeholder_fields"] += any(value["placeholder_values"] for value in field_plan.values())
        totals["entries_with_baseline_python"] += python["blocks"] > 0
        records.append(record)
    for name in ("selected_source_chars", "selected_source_utf8_bytes", "baseline_python_blocks",
                 "entries_with_ai_record", "entries_with_declared_execution_receipt",
                 "entries_with_placeholder_fields", "entries_with_baseline_python"):
        totals.setdefault(name, 0)
    canonical = json.dumps(index, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {"schema": "catalog.offline_material_plan/v1", "index_value_sha256": _sha(canonical),
            "record_count": len(records), "index_example_count": len(examples_by_id),
            "categories": {category: categories[category] for category in CATEGORIES},
            "gap_entry_counts": dict(sorted(gaps.items())), "totals": dict(totals),
            "ai_records_supplied": sum(map(len, ai_by_key.values())),
            "ai_keys_outside_index": sorted(set(ai_by_key) - index["entries"].keys()),
            "scope": ["Local inventory only. Source, AI-review and execution declarations remain distinct.",
                      "Completeness means explicit source teaching fields and syntactic code, never algorithm correctness or runnable host proof.",
                      "Missing/placeholder information is listed, not generated. No token estimates, API/DB calls, component imports or tutorial execution.",
                      "Character and UTF-8 sizes count selected text per entry; shared excerpts can therefore be counted more than once."],
            "entries": records}


def _read_json(path: Path) -> tuple[object, dict[str, Any]]:
    data = path.read_bytes()
    return json.loads(data.decode("utf-8-sig")), {"path": str(path), "sha256": _sha(data), "utf8_bytes": len(data)}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Existing examples index JSON")
    parser.add_argument("--ai-records", type=Path, help="Optional existing exported notes JSON")
    parser.add_argument("--output", type=Path, help="Write JSON here instead of stdout")
    args = parser.parse_args(argv)
    index, index_proof = _read_json(args.input)
    records, ai_proof = _read_json(args.ai_records) if args.ai_records else (None, None)
    plan = build_material_plan(index, records)
    plan["input_files"] = {"examples_index": index_proof, "ai_records": ai_proof}
    output = json.dumps(plan, ensure_ascii=False, indent=2) + "\n"
    if args.output is None:
        print(output, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
        print(json.dumps({"records": plan["record_count"], "categories": plan["categories"],
                          "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
