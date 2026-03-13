# -*- coding: utf-8 -*-
"""CLI entrypoint for production_scheduling case."""

from __future__ import annotations

import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_CASE_DIR = _THIS_DIR.parent
if str(_CASE_DIR) not in sys.path:
    sys.path.insert(0, str(_CASE_DIR))

from _bootstrap import ensure_nsgablack_importable  # noqa: E402

ensure_nsgablack_importable(Path(__file__))

from build_solver import cli_main  # noqa: E402


def main(argv=None) -> int:
    return int(cli_main(argv, case_root=_CASE_DIR))


if __name__ == "__main__":
    raise SystemExit(main())
