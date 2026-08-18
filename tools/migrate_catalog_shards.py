"""Split Case-local aggregate Catalog TOML files into canonical kind shards."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Sequence


_ENTRY_START = re.compile(r"(?m)(?=^\[\[entry\]\]\s*$)")
_KIND = re.compile(r'(?m)^kind\s*=\s*"([a-zA-Z0-9_-]+)"\s*$')


def split_catalog(source: Path, *, delete_source: bool = False) -> tuple[Path, ...]:
    """Split one ``catalog/entries.toml`` without reformatting entry blocks."""

    source = source.resolve()
    if source.name != "entries.toml" or source.parent.name != "catalog":
        raise ValueError(f"expected a catalog/entries.toml path, got {source}")
    raw = source.read_text(encoding="utf-8-sig")
    blocks = [part.strip() for part in _ENTRY_START.split(raw) if part.lstrip().startswith("[[entry]]")]
    if not blocks:
        raise ValueError(f"no [[entry]] records found in {source}")

    by_kind: dict[str, list[str]] = {}
    for index, block in enumerate(blocks):
        match = _KIND.search(block)
        if match is None:
            raise ValueError(f"entry {index} in {source} has no string kind")
        by_kind.setdefault(match.group(1).lower(), []).append(block)

    target_dir = source.parent / "entries"
    target_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for kind, rows in sorted(by_kind.items()):
        target = target_dir / f"{kind}.toml"
        if target.exists():
            raise FileExistsError(f"refusing to overwrite existing shard: {target}")
        target.write_text(
            f"# Canonical Case {kind} catalog shard.\n\n" + "\n\n".join(rows) + "\n",
            encoding="utf-8",
        )
        written.append(target)

    if delete_source:
        source.unlink()
    return tuple(written)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--delete-source", action="store_true")
    args = parser.parse_args(argv)
    for source in args.paths:
        outputs = split_catalog(source, delete_source=bool(args.delete_source))
        print(f"{source}: {len(outputs)} shard(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
