# -*- coding: utf-8 -*-
"""CLI/config surface for the mlblack symbolic consensus scaffold."""

from __future__ import annotations

import argparse
from pathlib import Path

CASE_ROOT = Path(__file__).resolve().parents[2]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Formal scaffold: nsgablack orchestrates mlblack symbolic consensus runs.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--mlblack-root", type=str, default=r"C:\Users\hp\Desktop\mlblack")
    parser.add_argument("--benchmark-key", type=str, default="arrhenius_gate_like")
    parser.add_argument("--n-total", type=int, default=240)
    parser.add_argument("--train-ratio", type=float, default=0.8)
    parser.add_argument("--noise-std", type=float, default=0.025)
    parser.add_argument("--consensus-cycles", type=int, default=1)
    parser.add_argument("--unlocked-runs-per-cycle", type=int, default=3)
    parser.add_argument("--locked-runs-per-cycle", type=int, default=2)
    parser.add_argument("--vanilla-runs", type=int, default=3)
    parser.add_argument("--locked-runs", type=int, default=2)
    parser.add_argument("--search-seed-base", type=int, default=100)
    parser.add_argument("--locked-search-seed-base", type=int, default=900)
    parser.add_argument("--core-equivalence-mode", type=str, default="family")
    parser.add_argument("--inner-fit-steps", type=int, default=2)
    parser.add_argument("--inner-fit-population", type=int, default=4)
    parser.add_argument("--task-fit-steps", type=int, default=3)
    parser.add_argument("--task-fit-population", type=int, default=4)
    parser.add_argument("--outer-adapter", type=str, choices=("complex", "vns"), default="complex")
    parser.add_argument("--generations", type=int, default=5)
    parser.add_argument("--pop-size", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--nsga-pop-size", type=int, default=12)
    parser.add_argument("--spea-archive-size", type=int, default=12)
    parser.add_argument("--de-pop-size", type=int, default=12)
    parser.add_argument("--trust-region-batch-size", type=int, default=6)
    parser.add_argument("--pattern-step-size", type=float, default=0.12)
    parser.add_argument("--vns-k-max", type=int, default=4)
    parser.add_argument("--vns-base-sigma", type=float, default=0.18)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--run-id", type=str, default="")
    parser.add_argument("--run-dir", type=str, default=str(CASE_ROOT / "runs" / "mlblack_symbolic_consensus"))
    parser.add_argument("--db-path", type=str, default="")
    parser.add_argument("--namespace", type=str, default="nsgablack_mlblack_symbolic_consensus")
    parser.add_argument("--tag-prefix", type=str, default="nsgablack")
    parser.add_argument("--inner-time-budget-ms", type=float, default=180000.0)
    parser.add_argument("--max-inner-calls", type=int, default=200)
    parser.add_argument("--no-bias", action="store_true")
    parser.add_argument("--no-logs", action="store_true")
    parser.add_argument("--check", action="store_true")
    return parser
