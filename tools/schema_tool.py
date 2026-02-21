from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class SchemaIssue:
    path: Path
    schema_name: str
    message: str


def _ensure_repo_parent_on_sys_path() -> None:
    repo_parent = Path(__file__).resolve().parents[2]
    if str(repo_parent) not in sys.path:
        sys.path.insert(0, str(repo_parent))


def _infer_schema_name(path: Path) -> Optional[str]:
    name = path.name
    if name.endswith(".modules.json"):
        return "module_report"
    if name.endswith(".bias.json"):
        return "bias_report"
    if name.endswith(".summary.json"):
        return "benchmark_summary"
    if path.parent.name == "visualizer" and name.endswith(".json"):
        return "run_inspector_snapshot"
    return None


def _iter_json_files(roots: Iterable[Path]) -> Iterable[Path]:
    for root in roots:
        if root.is_file() and root.suffix.lower() == ".json":
            yield root
            continue
        if not root.exists():
            continue
        for path in root.rglob("*.json"):
            if path.is_file():
                yield path


def check_files(paths: Iterable[Path]) -> Tuple[int, List[SchemaIssue]]:
    from nsgablack.utils.engineering.schema_version import schema_check

    checked = 0
    issues: List[SchemaIssue] = []
    for path in _iter_json_files(paths):
        schema_name = _infer_schema_name(path)
        if not schema_name:
            continue
        checked += 1
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            issues.append(SchemaIssue(path=path, schema_name=schema_name, message=f"invalid json: {exc}"))
            continue
        if not isinstance(payload, dict):
            issues.append(SchemaIssue(path=path, schema_name=schema_name, message="payload is not a JSON object"))
            continue
        ok, msg = schema_check(payload, schema_name)
        if not ok:
            issues.append(SchemaIssue(path=path, schema_name=schema_name, message=msg))
    return checked, issues


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check JSON artifact schema versions.")
    parser.add_argument(
        "paths",
        nargs="*",
        default=["runs"],
        help="Files/directories to scan (default: runs).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero when schema issues are found.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    _ensure_repo_parent_on_sys_path()
    roots = [Path(p).resolve() for p in args.paths]
    checked, issues = check_files(roots)

    print(f"schema_files_checked={checked}")
    print(f"schema_issues={len(issues)}")
    for issue in issues:
        print(f"[SCHEMA] {issue.path} ({issue.schema_name})")
        print(f"         {issue.message}")

    if args.strict and issues:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
