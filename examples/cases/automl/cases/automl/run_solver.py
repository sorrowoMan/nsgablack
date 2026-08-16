# -*- coding: utf-8 -*-
"""Case debug CLI; delegates to the case assembly module."""

from __future__ import annotations

# CLI contract: --check builds the real assembly without running optimization.

import inspect
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from build_solver import main as _main  # noqa: E402
else:
    from .build_solver import main as _main


def main(argv=None) -> int:
    try:
        sig = inspect.signature(_main)
    except (TypeError, ValueError):
        _main()
        return 0
    if len(sig.parameters) == 0:
        _main()
    else:
        _main(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
