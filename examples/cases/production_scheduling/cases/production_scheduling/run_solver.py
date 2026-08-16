from __future__ import annotations

# CLI contract: --check builds the real assembly without running optimization.

import argparse
import os
from pathlib import Path
import random
import sys
from datetime import datetime

import numpy as np

from blackbase.project import load_resource_context_from_env, print_resource_context_summary
from nsgablack.project.scaffold import print_solver_check
from nsgablack.utils.viz import launch_from_builder

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from build_solver import _build_solver_from_args, build_solver as _build_solver  # noqa: E402
    from cli import build_parser  # noqa: E402
    from plugins.export_utils import choose_pareto_solutions, extract_pareto  # noqa: E402
else:
    from .build_solver import _build_solver_from_args, build_solver as _build_solver
    from .cli import build_parser
    from .plugins.export_utils import choose_pareto_solutions, extract_pareto


def run_case(args=None, *, resource_context=None) -> None:
    """Run an already selected production mode through the formal assembly path."""

    if args is None:
        args = build_parser().parse_args()
    elif isinstance(args, (list, tuple)):
        args = build_parser().parse_args(list(args))

    if not getattr(args, "parallel", False):
        args.parallel = True
    if not getattr(args, "parallel_backend", None):
        args.parallel_backend = "process"
    if getattr(args, "parallel_backend", None) in ("process", "ray") and getattr(args, "parallel_workers", None) is None:
        cpu = int(os.cpu_count() or 8)
        args.parallel_workers = max(4, min(cpu - 2, 12))

    if int(getattr(args, "days", 31)) != 31:
        print(f"[run] override --days={args.days} ignored; enforcing 31-day window (day0..30).")
    args.days = 31
    if str(getattr(args, "solver", "multi-agent")).startswith("baseline") and getattr(args, "parallel_backend", None) != "thread":
        args.parallel_backend = "thread"
        args.parallel = True
        print("[run] baseline solver -> force --parallel-backend thread")
    if getattr(args, "parallel_backend", None) == "thread" and getattr(args, "parallel_thread_bias_isolation", None) == "deepcopy":
        args.parallel_thread_bias_isolation = "disable_cache"
        print("[run] thread backend -> switch bias isolation to disable_cache")
    print(
        f"[run] solver={args.solver} "
        f"parallel={bool(args.parallel)} backend={args.parallel_backend} workers={args.parallel_workers} "
        f"generations={args.generations} pop_size={args.pop_size} days=31"
    )
    print("[run] production_window=day0..30 (inclusive)")
    if bool(args.parallel) and args.parallel_backend == "process":
        print("[run] Note: first parallel step may be slow on Windows due to process spawn + warmup.")
    if bool(args.parallel) and args.parallel_backend == "ray":
        print("[run] Note: ray backend requires `pip install ray`; it will start a local runtime if not already running.")

    random.seed(args.seed)
    np.random.seed(args.seed)
    solver = _build_solver_from_args(args, resource_context=resource_context)
    solver.run()
    if args.solver == "multi-agent":
        individuals, objectives = extract_pareto(solver)
        print(f"Pareto size: {0 if individuals is None else len(individuals)}")
        choices = (
            choose_pareto_solutions(solver.problem, individuals, objectives)
            if individuals is not None
            else []
        )
        if choices:
            print(
                f"Selected key Pareto candidates: {len(choices)} "
                "(export handled by production_export plugin)"
            )


def main(argv=None) -> int:
    forwarded = sys.argv[1:] if argv is None else list(argv)
    contract = argparse.ArgumentParser(add_help=False)
    contract.add_argument("--check", action="store_true")
    contract_args, _ = contract.parse_known_args(forwarded)
    args = build_parser().parse_args(forwarded)
    resource_context = load_resource_context_from_env("nsgablack")
    if bool(contract_args.check):
        args.no_run_logs = True
        solver = _build_solver_from_args(args, resource_context=resource_context)
        print_solver_check(solver)
        return 0
    if bool(args.ui):
        if not getattr(args, "run_id", None):
            args.run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        launch_from_builder(
            lambda: _build_solver_from_args(args, resource_context=resource_context),
            entry_label="build_solver.py:build_solver",
        )
        return 0
    print_resource_context_summary(resource_context)
    run_case(args, resource_context=resource_context)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
