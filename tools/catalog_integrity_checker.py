from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


@dataclass(frozen=True)
class CheckFailure:
    key: str
    kind: str
    import_path: str
    error: str


@dataclass(frozen=True)
class CheckWarning:
    key: str
    kind: str
    import_path: str
    message: str


@dataclass(frozen=True)
class CheckResult:
    total_entries: int
    import_failures: Tuple[CheckFailure, ...]
    context_warnings: Tuple[CheckWarning, ...]
    usage_warnings: Tuple[CheckWarning, ...]
    by_kind: Dict[str, int]


class CatalogIntegrityChecker:
    """Validate catalog entry import paths and optional context contract presence."""

    _CONTRACT_FIELDS: Tuple[str, ...] = (
        "context_requires",
        "context_provides",
        "context_mutates",
        "context_cache",
        "context_notes",
    )

    _USAGE_FIELDS: Tuple[str, ...] = (
        "use_when",
        "minimal_wiring",
        "required_companions",
        "config_keys",
        "example_entry",
    )

    def __init__(
        self,
        *,
        check_context: bool = False,
        check_usage: bool = True,
        context_kinds: Tuple[str, ...] = ("plugin",),
        usage_kinds: Tuple[str, ...] | None = None,
        require_context_notes: bool = False,
    ):
        self.check_context = bool(check_context)
        self.check_usage = bool(check_usage)
        self.context_kinds = {str(k).strip().lower() for k in context_kinds if str(k).strip()}
        self.usage_kinds = (
            {str(k).strip().lower() for k in usage_kinds if str(k).strip()}
            if usage_kinds is not None
            else None
        )
        self.require_context_notes = bool(require_context_notes)

    def run(self) -> CheckResult:
        from nsgablack.catalog import get_catalog

        catalog = get_catalog(refresh=True)
        entries = list(catalog.list())
        import_failures: List[CheckFailure] = []
        context_warnings: List[CheckWarning] = []
        usage_warnings: List[CheckWarning] = []
        by_kind: Dict[str, int] = {}

        for entry in entries:
            by_kind[entry.kind] = by_kind.get(entry.kind, 0) + 1
            try:
                symbol = entry.load()
            except Exception as exc:  # noqa: BLE001
                import_failures.append(
                    CheckFailure(
                        key=entry.key,
                        kind=entry.kind,
                        import_path=entry.import_path,
                        error=repr(exc),
                    )
                )
                continue

            if self.check_context and entry.kind in self.context_kinds:
                if not self._has_any_contract(entry, symbol):
                    context_warnings.append(
                        CheckWarning(
                            key=entry.key,
                            kind=entry.kind,
                            import_path=entry.import_path,
                            message="missing context contract fields (entry + symbol)",
                        )
                    )
                elif self.require_context_notes and not self._has_context_notes(entry, symbol):
                    context_warnings.append(
                        CheckWarning(
                            key=entry.key,
                            kind=entry.kind,
                            import_path=entry.import_path,
                            message="missing context_notes (add concise semantics/side-effect notes)",
                        )
                    )

            if self.check_usage and (self.usage_kinds is None or entry.kind in self.usage_kinds):
                missing = self._missing_usage_fields(entry)
                if missing:
                    usage_warnings.append(
                        CheckWarning(
                            key=entry.key,
                            kind=entry.kind,
                            import_path=entry.import_path,
                            message=f"missing usage fields: {', '.join(missing)}",
                        )
                    )

        return CheckResult(
            total_entries=len(entries),
            import_failures=tuple(import_failures),
            context_warnings=tuple(context_warnings),
            usage_warnings=tuple(usage_warnings),
            by_kind=by_kind,
        )

    def _has_any_contract(self, entry: object, symbol: object | None) -> bool:
        for name in self._CONTRACT_FIELDS:
            value = getattr(entry, name, None)
            if self._normalize_values(value):
                return True
        if symbol is None:
            return False
        for name in self._CONTRACT_FIELDS:
            if hasattr(symbol, name):
                value = getattr(symbol, name)
                if self._normalize_values(value):
                    return True
        return False

    def _has_context_notes(self, entry: object, symbol: object | None) -> bool:
        if self._normalize_values(getattr(entry, "context_notes", None)):
            return True
        if symbol is None:
            return False
        return bool(self._normalize_values(getattr(symbol, "context_notes", None)))

    @staticmethod
    def _normalize_values(value: object) -> Tuple[str, ...]:
        if value is None:
            return ()
        if isinstance(value, str):
            text = value.strip()
            return (text,) if text else ()
        if isinstance(value, dict):
            return tuple(str(k).strip() for k in value.keys() if str(k).strip())
        if isinstance(value, (list, tuple, set)):
            out: List[str] = []
            for item in value:
                text = str(item).strip()
                if text:
                    out.append(text)
            return tuple(out)
        text = str(value).strip()
        return (text,) if text else ()

    def _missing_usage_fields(self, entry: object) -> Tuple[str, ...]:
        missing: List[str] = []
        for name in self._USAGE_FIELDS:
            value = getattr(entry, name, None)
            if name == "example_entry":
                if not str(value or "").strip():
                    missing.append(name)
                continue
            if not self._normalize_values(value):
                missing.append(name)
        return tuple(missing)


def _ensure_repo_parent_on_sys_path() -> None:
    # tools/catalog_integrity_checker.py -> repo_root = parents[1], parent of repo = parents[2]
    repo_parent = Path(__file__).resolve().parents[2]
    if str(repo_parent) not in sys.path:
        sys.path.insert(0, str(repo_parent))


def _print_result(result: CheckResult) -> None:
    print(f"catalog_entries={result.total_entries}")
    print(f"import_failures={len(result.import_failures)}")
    if result.by_kind:
        by_kind = ", ".join(f"{k}:{result.by_kind[k]}" for k in sorted(result.by_kind))
        print(f"by_kind={by_kind}")

    for item in result.import_failures:
        print(f"[FAIL] {item.key} ({item.kind}) {item.import_path}")
        print(f"       {item.error}")

    if result.context_warnings:
        print(f"context_warnings={len(result.context_warnings)}")
        for item in result.context_warnings:
            print(f"[WARN] {item.key} ({item.kind}) {item.import_path}")
            print(f"       {item.message}")
    if result.usage_warnings:
        print(f"usage_warnings={len(result.usage_warnings)}")
        for item in result.usage_warnings:
            print(f"[WARN] {item.key} ({item.kind}) {item.import_path}")
            print(f"       {item.message}")


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check nsgablack catalog import integrity.")
    parser.add_argument(
        "--check-context",
        action="store_true",
        help="Also warn for selected kinds without context contracts.",
    )
    parser.add_argument(
        "--context-kinds",
        type=str,
        default="plugin",
        help="Comma-separated kinds for context checks (default: plugin).",
    )
    parser.add_argument(
        "--strict-context",
        action="store_true",
        help="Return non-zero when context warnings exist.",
    )
    parser.add_argument(
        "--require-context-notes",
        action="store_true",
        help="Require context_notes for entries selected by --context-kinds.",
    )
    parser.add_argument(
        "--check-usage",
        action="store_true",
        help="Also check usage contracts (use_when/minimal_wiring/required_companions/config_keys/example_entry).",
    )
    parser.add_argument(
        "--usage-kinds",
        type=str,
        default="",
        help="Optional comma-separated kinds for usage checks (default: all kinds).",
    )
    parser.add_argument(
        "--strict-usage",
        action="store_true",
        help="Return non-zero when usage warnings exist.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    _ensure_repo_parent_on_sys_path()
    context_kinds = tuple(k.strip().lower() for k in str(args.context_kinds or "").split(",") if k.strip())
    usage_kinds = tuple(k.strip().lower() for k in str(args.usage_kinds or "").split(",") if k.strip()) or None
    checker = CatalogIntegrityChecker(
        check_context=bool(args.check_context),
        check_usage=bool(args.check_usage or args.strict_usage),
        context_kinds=context_kinds,
        usage_kinds=usage_kinds,
        require_context_notes=bool(args.require_context_notes),
    )
    result = checker.run()
    _print_result(result)

    if result.import_failures:
        return 2
    if bool(args.strict_context) and result.context_warnings:
        return 1
    if bool(args.strict_usage) and result.usage_warnings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
