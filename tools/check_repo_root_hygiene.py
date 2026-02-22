from __future__ import annotations

import argparse
from pathlib import Path
from typing import List


def _find_violations(repo_root: Path) -> List[str]:
    violations: List[str] = []

    root_pycache = repo_root / "__pycache__"
    if root_pycache.exists():
        violations.append("__pycache__/")

    for path in repo_root.glob("*_history.json"):
        if path.is_file():
            violations.append(path.name)

    return violations


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check repository-root hygiene (no __pycache__ or *_history.json in root)."
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Repository root path. Defaults to current directory.",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    violations = _find_violations(root)
    if not violations:
        print(f"[hygiene] OK: {root}")
        return 0

    print(f"[hygiene] FAIL: disallowed root artifacts found under {root}")
    for item in violations:
        print(f" - {item}")
    print("Move history files to runs/ or artifacts/, and remove root __pycache__.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
