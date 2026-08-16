"""Canonical ARIMA Case CLI; supports ``--check`` without running search."""

from __future__ import annotations

from build_solver import main as _main


def main(argv: list[str] | None = None) -> int:
    _main(argv)
    return 0


if __name__ == "__main__":
    main()
