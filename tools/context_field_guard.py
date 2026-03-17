from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


@dataclass(frozen=True)
class GuardIssue:
    location: str
    message: str


def _ensure_repo_parent_on_sys_path() -> None:
    repo_parent = Path(__file__).resolve().parents[2]
    if str(repo_parent) not in sys.path:
        sys.path.insert(0, str(repo_parent))


def _iter_context_fields(entry) -> Iterable[tuple[str, str]]:
    for field in ("context_requires", "context_provides", "context_mutates", "context_cache"):
        values = getattr(entry, field, ()) or ()
        for value in values:
            key = str(value).strip()
            if key:
                yield field, key


def check_catalog_context_keys() -> List[GuardIssue]:
    from nsgablack.catalog import get_catalog
    from nsgablack.core.state.context_field_governance import is_canonical_context_key
    from nsgablack.core.state.context_keys import normalize_context_key

    issues: List[GuardIssue] = []
    for entry in get_catalog(refresh=True).list():
        for field, key in _iter_context_fields(entry):
            norm = normalize_context_key(key)
            if norm.startswith("metrics."):
                continue
            if not is_canonical_context_key(key):
                issues.append(
                    GuardIssue(
                        location=f"catalog:{entry.key}:{field}",
                        message=f"non-canonical context key: {key!r} (normalized={norm!r})",
                    )
                )
    return issues


def check_context_field_rules_doc(path: Path | None = None) -> List[GuardIssue]:
    from nsgablack.core.state.context_field_governance import (
        CONTEXT_FIELD_SCHEMA_NAME,
        CONTEXT_FIELD_SCHEMA_VERSION,
    )

    doc = path or Path("docs/user_guide/CONTEXT_FIELD_RULES.md")
    issues: List[GuardIssue] = []
    if not doc.is_file():
        return [GuardIssue(location=str(doc), message="missing governance doc")]

    text = doc.read_text(encoding="utf-8")
    name_m = re.search(r"context_field_schema_name\s*:\s*([\w\.-]+)", text)
    ver_m = re.search(r"context_field_schema_version\s*:\s*(\d+)", text)
    if not name_m:
        issues.append(GuardIssue(location=str(doc), message="schema name marker not found"))
    else:
        got = str(name_m.group(1)).strip()
        if got != str(CONTEXT_FIELD_SCHEMA_NAME):
            issues.append(
                GuardIssue(
                    location=str(doc),
                    message=f"schema name mismatch: doc={got!r}, code={CONTEXT_FIELD_SCHEMA_NAME!r}",
                )
            )
    if not ver_m:
        issues.append(GuardIssue(location=str(doc), message="schema version marker not found"))
    else:
        got_v = int(ver_m.group(1))
        if got_v != int(CONTEXT_FIELD_SCHEMA_VERSION):
            issues.append(
                GuardIssue(
                    location=str(doc),
                    message=f"schema version mismatch: doc={got_v}, code={CONTEXT_FIELD_SCHEMA_VERSION}",
                )
            )
    return issues


def run_guard() -> List[GuardIssue]:
    issues: List[GuardIssue] = []
    issues.extend(check_catalog_context_keys())
    issues.extend(check_context_field_rules_doc())
    return issues


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Context field governance guard.")
    parser.add_argument("--strict", action="store_true", help="Return non-zero when any issue exists.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    _ensure_repo_parent_on_sys_path()
    issues = run_guard()

    print(f"context_field_guard_issues={len(issues)}")
    for issue in issues:
        print(f"[CONTEXT-GUARD] {issue.location}: {issue.message}")

    if args.strict and issues:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
