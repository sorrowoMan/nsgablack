"""Per-component usage coverage over an explicit public Catalog snapshot.

This audits evidence, presentation and Python syntax without importing or
executing a component. A usage card is distinct from a successful Project run.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import json
from pathlib import Path
import re

from .examples import load_example_index, validate_example_index


def _python_sections(snippet):
    if str(snippet.get("path", "")).endswith(".py"):
        return [snippet["text"]] if snippet.get("complete") else []
    return re.findall(r"^```(?:python|py)\s*\n(.*?)^```\s*$", snippet.get("text", ""), re.M | re.S)


def audit_usage(index, catalog_entries):
    index = validate_example_index(index)
    entries = [entry.as_dict() if hasattr(entry, "as_dict") else dict(entry) for entry in catalog_entries]
    rows, counts = [], Counter()
    for entry in entries:
        key = entry["key"]
        identifiers = index["entries"].get(key, [])
        recipes, syntax_errors = [], []
        for identifier in identifiers:
            record = index["examples"][identifier]
            complete = (record["binding"] == "focused" and record["snippets"]
                        and all(record[name] for name in ("inputs", "steps", "dependencies", "expected_outputs")))
            if not complete:
                continue
            invalid = False
            for snippet in record["snippets"]:
                for source in _python_sections(snippet):
                    try:
                        ast.parse(source)
                    except SyntaxError as exc:
                        invalid = True
                        syntax_errors.append({"example_id": identifier, "path": snippet["path"],
                                              "line_in_block": exc.lineno, "reason": "python_syntax_invalid"})
            if not invalid:
                recipes.append(identifier)
        if recipes:
            quality = "usage_recipe"
        elif key not in index["entries"]:
            quality = "absent_from_index"
        elif identifiers:
            quality = "reference_only"
        elif entry.get("minimal_wiring"):
            quality = "wiring_only"
        else:
            quality = "missing"
        counts[quality] += 1
        statuses = {index["examples"][identifier]["verification"]["status"] for identifier in identifiers}
        rows.append({"key": key, "kind": entry.get("kind"), "import_path": entry.get("import_path"),
            "quality": quality, "usage_examples": recipes, "all_examples": identifiers,
            "execution_receipt": "executed" in statuses, "syntax_errors": syntax_errors,
            "framework": entry.get("metadata", {}).get("catalog_framework", "nsgablack")})
    expected = {entry["key"] for entry in entries}
    return {"schema": "nsgablack.catalog.example_audit/v1", "components": len(rows),
        "counts": dict(counts), "complete_usage": all(row["quality"] == "usage_recipe" for row in rows),
        "index_extra_keys": sorted(set(index["entries"]) - expected), "rows": rows,
        "limits": "Use cards and syntax checks do not establish runtime, algorithm or backend correctness."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--catalog-json", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-usage", action="store_true")
    args = parser.parse_args(argv)
    catalog = json.loads(args.catalog_json.read_text(encoding="utf-8"))
    if not isinstance(catalog, list) or len(catalog) > 10000:
        parser.error("catalog snapshot must be a bounded list")
    report = audit_usage(load_example_index(args.index), catalog)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("components", "counts", "complete_usage")}))
    return int(args.require_usage and not report["complete_usage"])


if __name__ == "__main__":
    raise SystemExit(main())
