# -*- coding: utf-8 -*-
"""CLI entrypoint for the nested supply-adjustment case."""

from __future__ import annotations

import sys
from pathlib import Path

_CASE_DIR = Path(__file__).resolve().parents[1]
if str(_CASE_DIR) not in sys.path:
    sys.path.insert(0, str(_CASE_DIR))

from _bootstrap import ensure_nsgablack_importable  # noqa: E402

ensure_nsgablack_importable(Path(__file__))

from solver.assembly import main as _main  # noqa: E402


def main(argv=None) -> int:
    _main(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
