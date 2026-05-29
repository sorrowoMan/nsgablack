from __future__ import annotations

from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from build_solver import cli_main as _cli_main  # noqa: E402
else:
    from .build_solver import cli_main as _cli_main


def main(argv=None) -> int:
    return int(_cli_main(argv))


if __name__ == "__main__":
    raise SystemExit(main())
