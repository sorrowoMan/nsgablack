# -*- coding: utf-8 -*-
"""Thin entrypoint for the mlblack symbolic consensus scaffold."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from _bootstrap import ensure_nsgablack_importable  # noqa: E402

ensure_nsgablack_importable(Path(__file__))

from case_scaffold.config.parser import build_parser  # noqa: E402
from case_scaffold.orchestration.solver import build_solver_from_args  # noqa: E402


def build_solver(argv: Optional[list[str]] = None):
    args = build_parser().parse_args(argv if argv is not None else [])
    return build_solver_from_args(args)


def main(argv: Optional[list[str]] = None) -> None:
    args = build_parser().parse_args(argv if argv is not None else None)
    solver = build_solver_from_args(args)
    result = solver.run()
    best_x = getattr(solver, "best_x", None)
    print(f"[case] status={result.get('status')} steps={solver.generation}")
    if best_x is not None:
        decoded = solver.problem._decode_plan(best_x)
        print(f"[case] best_plan={decoded}")
    inner_result = getattr(solver.problem, "last_inner_result", None)
    if isinstance(inner_result, dict):
        print(
            "[case] best_inner "
            f"exact={inner_result.get('best_exact_term_recovery_score')} "
            f"family={inner_result.get('best_family_level_term_recovery_score')} "
            f"rmse={inner_result.get('best_test_rmse')} "
            f"phase={inner_result.get('best_phase')}"
        )
        print(f"[case] summary={inner_result.get('summary_path')}")


if __name__ == "__main__":
    main()
