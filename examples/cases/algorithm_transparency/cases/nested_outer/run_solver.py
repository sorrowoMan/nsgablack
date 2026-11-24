"""
CLI entry point for running the solver.

Usage:
    python run_solver.py
    python run_solver.py --check
"""

from pathlib import Path
import argparse
import sys

_project_root = Path(__file__).resolve().parents[2]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
from case_cli import main as _project_case_main


def main(argv=None):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--check", action="store_true")
    known, remaining = parser.parse_known_args(argv)
    forwarded = (["--check"] if known.check else []) + remaining
    return _project_case_main("nested_outer", argv=forwarded)


if __name__ == "__main__":
    raise SystemExit(main())
