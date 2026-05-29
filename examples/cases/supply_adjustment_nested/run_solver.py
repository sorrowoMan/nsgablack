from __future__ import annotations

from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from build_solver import main as _main  # noqa: E402
else:
    from .build_solver import main as _main


def main(argv=None) -> int:
    _main(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
