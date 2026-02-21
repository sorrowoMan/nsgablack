from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Iterable, Sequence

from .registry import CatalogEntry
from .usage import build_usage_profile


def _split_values(values: Sequence[str] | None) -> tuple[str, ...]:
    out: list[str] = []
    for raw in values or ():
        for part in str(raw).split(","):
            text = part.strip()
            if text:
                out.append(text)
    return tuple(out)


def build_entry_payload(
    *,
    key: str,
    title: str,
    kind: str,
    import_path: str,
    summary: str,
    tags: Sequence[str] | None = None,
    companions: Sequence[str] | None = None,
    use_when: Sequence[str] | None = None,
    minimal_wiring: Sequence[str] | None = None,
    required_companions: Sequence[str] | None = None,
    config_keys: Sequence[str] | None = None,
    example_entry: str = "",
    context_requires: Sequence[str] | None = None,
    context_provides: Sequence[str] | None = None,
    context_mutates: Sequence[str] | None = None,
    context_cache: Sequence[str] | None = None,
    context_notes: Sequence[str] | None = None,
) -> dict[str, object]:
    base = CatalogEntry(
        key=str(key).strip(),
        title=str(title).strip(),
        kind=str(kind).strip().lower(),
        import_path=str(import_path).strip(),
        tags=_split_values(tags),
        summary=str(summary).strip(),
        companions=_split_values(companions),
        use_when=_split_values(use_when),
        minimal_wiring=_split_values(minimal_wiring),
        required_companions=_split_values(required_companions),
        config_keys=_split_values(config_keys),
        example_entry=str(example_entry).strip(),
        context_requires=_split_values(context_requires),
        context_provides=_split_values(context_provides),
        context_mutates=_split_values(context_mutates),
        context_cache=_split_values(context_cache),
        context_notes=_split_values(context_notes),
    )
    usage = build_usage_profile(base)
    return {
        "key": base.key,
        "title": base.title,
        "kind": base.kind,
        "import_path": base.import_path,
        "tags": tuple(base.tags),
        "summary": base.summary,
        "companions": tuple(base.companions),
        "use_when": tuple(usage.use_when),
        "minimal_wiring": tuple(usage.minimal_wiring),
        "required_companions": tuple(usage.required_companions),
        "config_keys": tuple(usage.config_keys),
        "example_entry": str(usage.example_entry),
        "context_requires": tuple(base.context_requires),
        "context_provides": tuple(base.context_provides),
        "context_mutates": tuple(base.context_mutates),
        "context_cache": tuple(base.context_cache),
        "context_notes": tuple(base.context_notes),
    }


def _format_list(values: Iterable[str]) -> str:
    vals = [str(v).strip() for v in values if str(v).strip()]
    return "[" + ", ".join(repr(v) for v in vals) + "]"


def render_entry_block(payload: dict[str, object]) -> str:
    return (
        "[[entry]]\n"
        f"key = {payload['key']!r}\n"
        f"title = {payload['title']!r}\n"
        f"kind = {payload['kind']!r}\n"
        f"import_path = {payload['import_path']!r}\n"
        f"tags = {_format_list(payload.get('tags', ()))}\n"
        f"summary = {payload['summary']!r}\n"
        f"companions = {_format_list(payload.get('companions', ())) }\n"
        f"context_requires = {_format_list(payload.get('context_requires', ())) }\n"
        f"context_provides = {_format_list(payload.get('context_provides', ())) }\n"
        f"context_mutates = {_format_list(payload.get('context_mutates', ())) }\n"
        f"context_cache = {_format_list(payload.get('context_cache', ())) }\n"
        f"context_notes = {_format_list(payload.get('context_notes', ())) }\n"
        f"use_when = {_format_list(payload.get('use_when', ())) }\n"
        f"minimal_wiring = {_format_list(payload.get('minimal_wiring', ())) }\n"
        f"required_companions = {_format_list(payload.get('required_companions', ())) }\n"
        f"config_keys = {_format_list(payload.get('config_keys', ())) }\n"
        f"example_entry = {str(payload.get('example_entry', '') or '').strip()!r}\n"
    )


def upsert_catalog_entry(path: Path, payload: dict[str, object], *, replace: bool = True) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8") if file_path.exists() else ""
    lines = text.splitlines(keepends=True)

    starts = [i for i, line in enumerate(lines) if line.strip() == "[[entry]]"]
    starts.append(len(lines))
    header = lines[: starts[0]] if starts and starts[0] > 0 else []

    key_pat = re.compile(r"^\s*key\s*=\s*['\"]([^'\"]+)['\"]")
    blocks: list[tuple[str, str]] = []
    for idx in range(len(starts) - 1):
        s, e = starts[idx], starts[idx + 1]
        block = "".join(lines[s:e]) if s < len(lines) else ""
        key = ""
        for ln in block.splitlines():
            m = key_pat.match(ln)
            if m:
                key = m.group(1).strip()
                break
        if not key:
            continue
        if replace and key == str(payload.get("key", "")).strip():
            continue
        blocks.append((key, block))

    blocks.append((str(payload["key"]), render_entry_block(payload)))
    body = "\n".join(block.rstrip("\n") for _, block in blocks).strip()
    output = "".join(header).rstrip() + ("\n\n" if header else "") + body + "\n"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(output, encoding="utf-8")


def remove_catalog_entry(path: Path, key: str) -> bool:
    """Remove one entry block by key. Returns True if removed."""
    file_path = Path(path)
    if not file_path.exists():
        return False

    text = file_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if line.strip() == "[[entry]]"]
    if not starts:
        return False
    starts.append(len(lines))

    key_pat = re.compile(r"^\s*key\s*=\s*['\"]([^'\"]+)['\"]")
    header = lines[: starts[0]] if starts and starts[0] > 0 else []
    blocks: list[str] = []
    removed = False
    target = str(key).strip()

    for idx in range(len(starts) - 1):
        s, e = starts[idx], starts[idx + 1]
        block = "".join(lines[s:e]) if s < len(lines) else ""
        block_key = ""
        for ln in block.splitlines():
            m = key_pat.match(ln)
            if m:
                block_key = m.group(1).strip()
                break
        if not block_key:
            continue
        if block_key == target:
            removed = True
            continue
        blocks.append(block.rstrip("\n"))

    if not removed:
        return False

    body = "\n".join(blocks).strip()
    output = "".join(header).rstrip()
    if output and body:
        output = output + "\n\n" + body + "\n"
    elif body:
        output = body + "\n"
    else:
        output = (output + "\n") if output else ""
    file_path.write_text(output, encoding="utf-8")
    return True


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Quick add/update a catalog entry in TOML with explicit usage fields.")
    parser.add_argument("--file", default="catalog/entries.toml", help="Target TOML file path.")
    parser.add_argument("--key", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument(
        "--kind",
        required=True,
        choices=("adapter", "bias", "plugin", "representation", "suite", "tool", "example"),
    )
    parser.add_argument("--import-path", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--tags", action="append", default=[])
    parser.add_argument("--companions", action="append", default=[])
    parser.add_argument("--use-when", action="append", default=[])
    parser.add_argument("--minimal-wiring", action="append", default=[])
    parser.add_argument("--required-companions", action="append", default=[])
    parser.add_argument("--config-keys", action="append", default=[])
    parser.add_argument("--example-entry", default="")
    parser.add_argument("--context-requires", action="append", default=[])
    parser.add_argument("--context-provides", action="append", default=[])
    parser.add_argument("--context-mutates", action="append", default=[])
    parser.add_argument("--context-cache", action="append", default=[])
    parser.add_argument("--context-notes", action="append", default=[])
    parser.add_argument(
        "--no-replace",
        action="store_true",
        help="Do not replace existing key block; append a new block instead.",
    )
    args = parser.parse_args(argv)

    payload = build_entry_payload(
        key=args.key,
        title=args.title,
        kind=args.kind,
        import_path=args.import_path,
        summary=args.summary,
        tags=args.tags,
        companions=args.companions,
        use_when=args.use_when,
        minimal_wiring=args.minimal_wiring,
        required_companions=args.required_companions,
        config_keys=args.config_keys,
        example_entry=args.example_entry,
        context_requires=args.context_requires,
        context_provides=args.context_provides,
        context_mutates=args.context_mutates,
        context_cache=args.context_cache,
        context_notes=args.context_notes,
    )
    target = Path(args.file)
    upsert_catalog_entry(target, payload, replace=not bool(args.no_replace))
    print(f"catalog entry upserted: {payload['key']} -> {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
