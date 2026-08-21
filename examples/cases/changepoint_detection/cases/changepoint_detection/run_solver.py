# -*- coding: utf-8 -*-
"""Changepoint-detection benchmark CLI for the canonical Case assembly."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from build_solver import build_solver  # noqa: E402
else:
    from .build_solver import build_solver

from nsgablack.project.scaffold import print_solver_check


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Changepoint detection benchmark")
    parser.add_argument("--n", type=int, default=200)
    parser.add_argument("--max-cp", type=int, default=3)
    parser.add_argument("--adapter", type=str, default="de")
    parser.add_argument("--max-steps", type=int, default=150)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    rng = np.random.default_rng(args.seed)
    cp1, cp2 = int(args.n * 0.3), int(args.n * 0.7)
    signal = np.concatenate(
        [
            rng.normal(0, 1, cp1),
            rng.normal(5, 1, cp2 - cp1),
            rng.normal(2, 1, args.n - cp2),
        ]
    )
    solver = build_solver(
        signal=signal,
        max_changepoints=args.max_cp,
        adapter=args.adapter,
        max_steps=args.max_steps,
    )
    solver.set_random_seed(args.seed)
    if args.check:
        print_solver_check(solver)
        return 0

    try:
        import ruptures as rpt

        baseline = [c for c in rpt.Pelt(model="l2").fit(signal).predict(pen=10) if c < args.n]
    except ImportError:
        baseline = [cp1, cp2]
    started = time.perf_counter()
    solver.run()
    elapsed = time.perf_counter() - started
    detected = (
        solver.problem.get_changepoints(solver.best_x).tolist()
        if solver.best_x is not None
        else []
    )
    print(f"True:   [{cp1}, {cp2}]")
    print(f"PELT:   {baseline}")
    print(f"nsgablack ({args.adapter}): {detected}  ({elapsed:.2f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
