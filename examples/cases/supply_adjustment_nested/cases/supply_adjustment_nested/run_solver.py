from __future__ import annotations

# CLI contract: --check builds the real assembly without running optimization.

import argparse
from pathlib import Path
import sys

from blackbase.project import load_resource_context_from_env, print_resource_context_summary
from nsgablack.project.scaffold import print_solver_check
from nsgablack.utils.viz import launch_from_builder

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from build_solver import build_solver as _build_solver  # noqa: E402
else:
    from .build_solver import build_solver as _build_solver


def main(argv=None) -> int:
    contract = argparse.ArgumentParser(add_help=False)
    contract.add_argument("--check", action="store_true")
    contract.add_argument("--ui", action="store_true")
    forwarded = sys.argv[1:] if argv is None else argv
    contract_args, _ = contract.parse_known_args(forwarded)
    resource_context = load_resource_context_from_env("nsgablack")
    if contract_args.ui:
        launch_from_builder(
            lambda: _build_solver(forwarded, resource_context=resource_context),
            entry_label="build_solver.py:build_solver",
        )
        return 0
    solver = _build_solver(
        forwarded,
        resource_context=resource_context,
    )
    if contract_args.check:
        print_solver_check(solver)
        return 0
    print_resource_context_summary(resource_context)
    result = solver.run()
    if isinstance(result, dict):
        status = result.get("status", "unknown")
        steps = result.get("steps_executed", "-")
        best = result.get("best_objective", "-")
    else:
        status = getattr(result, "status", "completed")
        steps = getattr(result, "steps_executed", getattr(result, "steps", "-"))
        best = getattr(result, "best_objective", getattr(solver, "best_objective", "-"))
    print(f"done: status={status} steps={steps} best={best}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
