"""Canonical distributed-worker Case CLI with the shared ``--check`` contract."""

from __future__ import annotations

from blackbase.project import run_standard_case_cli


def main(argv: list[str] | None = None) -> int:
    return run_standard_case_cli(__file__, framework="nsgablack", argv=argv)


if __name__ == "__main__":
    raise SystemExit(main())
