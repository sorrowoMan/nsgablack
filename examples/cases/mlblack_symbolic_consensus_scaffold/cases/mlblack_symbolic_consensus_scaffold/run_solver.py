# -*- coding: utf-8 -*-
"""Case debug CLI; delegates to the case assembly module."""

from __future__ import annotations

# CLI contract: --check builds the real assembly without running optimization.

import argparse
import sys
from pathlib import Path

from blackbase.project import load_resource_context_from_env, print_resource_context_summary
from nsgablack.project.scaffold import print_solver_check

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from build_solver import build_solver as _build_solver  # noqa: E402
else:
    from .build_solver import build_solver as _build_solver


def main(argv=None) -> int:
    contract = argparse.ArgumentParser(add_help=False)
    contract.add_argument("--check", action="store_true")
    forwarded = sys.argv[1:] if argv is None else argv
    contract_args, _ = contract.parse_known_args(forwarded)
    resource_context = load_resource_context_from_env("nsgablack")
    solver = _build_solver(
        forwarded,
        resource_context=resource_context,
    )
    if contract_args.check:
        print_solver_check(solver)
        return 0
    print_resource_context_summary(resource_context)
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
