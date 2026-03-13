"""CLI parser for production_scheduling case entrypoint."""

from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Refactored production scheduling (pipeline-first).")
    parser.add_argument("--solver", choices=["multi-agent"], default="multi-agent")
    parser.add_argument("--ui", action="store_true", help="Launch Run Inspector UI before running.")
    parser.add_argument("--bom", type=str, default=None)
    parser.add_argument("--supply", type=str, default=None)
    parser.add_argument("--machines", type=int, default=22)
    parser.add_argument("--materials", type=int, default=156)
    parser.add_argument("--days", type=int, default=31)
    parser.add_argument("--max-machines", type=int, default=8)
    parser.add_argument("--min-machines", type=int, default=5)
    parser.add_argument("--min-prod", type=int, default=50)
    parser.add_argument("--max-prod", type=int, default=10000)
    parser.add_argument("--shortage-unit-penalty", type=float, default=1.0)
    parser.add_argument(
        "--penalty-objective",
        action="store_true",
        help="Include scaled penalty as an objective (default: constraint-only).",
    )
    parser.add_argument(
        "--penalty-scale",
        type=float,
        default=0.001,
        help="Scale for penalty objective when enabled.",
    )
    parser.add_argument("--pop-size", type=int, default=200)
    parser.add_argument("--generations", type=int, default=30)
    parser.add_argument("--crossover-rate", type=float, default=0.85)
    parser.add_argument("--mutation-rate", type=float, default=0.15)
    parser.add_argument("--report-every", type=int, default=10)
    parser.add_argument("--run-dir", type=str, default=None, help="Auto logs dir for benchmark/module reports.")
    parser.add_argument("--run-id", type=str, default=None, help="Run id for reports (default: timestamp).")
    parser.add_argument("--log-every", type=int, default=1, help="BenchmarkHarness CSV log frequency.")
    parser.add_argument("--no-bias-md", action="store_true", help="Disable writing bias.md in module report.")
    parser.add_argument("--no-run-logs", action="store_true", help="Disable automatic benchmark/module reports.")
    parser.add_argument("--no-profile", action="store_true", help="Disable ProfilerPlugin output in run logs.")
    parser.add_argument(
        "--no-decision-trace",
        action="store_true",
        help="Disable DecisionTracePlugin output in run logs.",
    )
    parser.add_argument(
        "--decision-trace-flush-every",
        type=int,
        default=1,
        help="Decision trace summary flush interval (generations).",
    )
    parser.add_argument("--no-export", action="store_true", help="Disable exporting schedules (no Excel/CSV output).")
    parser.add_argument("--comm-interval", type=int, default=5)
    parser.add_argument("--adapt-interval", type=int, default=20)
    parser.add_argument(
        "--explorer-adapter",
        choices=["moead", "random"],
        default="moead",
        help="Explorer role adapter: moead (default) or random search.",
    )
    parser.add_argument("--vns-batch-size", type=int, default=48, help="VNS candidates per step.")
    parser.add_argument("--vns-k-max", type=int, default=4, help="VNS neighborhood depth.")
    parser.add_argument("--vns-base-sigma", type=float, default=0.2, help="VNS initial mutation sigma.")
    parser.add_argument(
        "--exploiter-adapter",
        choices=["vns", "local"],
        default="vns",
        help="Exploiter role adapter: vns (default) or local search.",
    )
    parser.add_argument("--moead-pop-size", type=int, default=48, help="MOEA/D subproblem population size.")
    parser.add_argument("--moead-neighborhood", type=int, default=20, help="MOEA/D neighborhood size.")
    parser.add_argument("--moead-delta", type=float, default=0.9, help="MOEA/D neighbor sampling probability.")
    parser.add_argument("--moead-nr", type=int, default=2, help="MOEA/D max replacements per offspring.")
    parser.add_argument("--parallel", action="store_true", help="Enable parallel evaluation (CPU).")
    parser.add_argument(
        "--parallel-backend",
        choices=["auto", "process", "thread", "joblib", "ray"],
        default="process",
        help="Parallel backend (process recommended for heavy Python evaluation; ray is optional).",
    )
    parser.add_argument("--parallel-workers", type=int, default=None, help="Parallel worker count (default: auto).")
    parser.add_argument("--parallel-chunk-size", type=int, default=None, help="Task chunk size (default: auto).")
    parser.add_argument("--parallel-verbose", action="store_true", help="Verbose parallel evaluator logging.")
    parser.add_argument(
        "--parallel-no-precheck",
        action="store_true",
        help="Disable picklability precheck/fallback for process backend.",
    )
    parser.add_argument("--parallel-strict", action="store_true", help="Strict mode: do not fallback on parallel errors.")
    parser.add_argument(
        "--parallel-thread-bias-isolation",
        choices=["deepcopy", "disable_cache", "off"],
        default="deepcopy",
        help="Thread backend bias isolation strategy (deepcopy recommended).",
    )
    parser.add_argument(
        "--allow-infeasible-update",
        action="store_true",
        help="Disable strict material-feasible candidate filtering before adapter update.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed. Default: None (use runtime random seed).",
    )
    parser.add_argument("--no-bias", action="store_true")
    parser.add_argument(
        "--no-pipeline",
        action="store_true",
        help="Ablation: keep initializer+mutator, but disable repair/smoothing in the pipeline.",
    )
    parser.add_argument(
        "--material-cap-ratio",
        type=float,
        default=2.0,
        help="Daily material usage cap vs. average allocation (higher = higher output).",
    )
    parser.add_argument(
        "--daily-floor-ratio",
        type=float,
        default=0.55,
        help="Daily production floor vs. average allocation (higher = more stable output).",
    )
    parser.add_argument(
        "--donor-keep-ratio",
        type=float,
        default=0.7,
        help="Minimum fraction of a donor day's total kept during backfill.",
    )
    parser.add_argument(
        "--daily-cap-ratio",
        type=float,
        default=2.2,
        help="Daily production cap vs. average allocation (higher = higher output).",
    )
    parser.add_argument(
        "--budget-mode",
        choices=["average", "today"],
        default="today",
        help="Daily material budget mode (average = capped by remaining days, today = use current stock).",
    )
    parser.add_argument(
        "--smooth-strength",
        type=float,
        default=0.6,
        help="Forward smoothing strength for daily totals (0 = off).",
    )
    parser.add_argument(
        "--smooth-passes",
        type=int,
        default=2,
        help="Number of forward smoothing passes.",
    )
    parser.add_argument(
        "--reserve-ratio",
        type=float,
        default=0.6,
        help="Reserve ratio for next-day continuity (lower = higher output).",
    )
    parser.add_argument(
        "--pareto-export",
        type=int,
        default=-1,
        help="Export N Pareto schedules (-1 = all, 0 = off).",
    )
    parser.add_argument(
        "--pareto-export-mode",
        choices=["front", "crowding", "production"],
        default="crowding",
        help="How to pick Pareto schedules to export.",
    )
    parser.add_argument(
        "--coverage-bonus",
        type=float,
        default=300.0,
        help="Priority bonus for machines never produced yet (higher = richer coverage).",
    )
    parser.add_argument(
        "--coverage-reward",
        type=float,
        default=0.03,
        help="Bias reward for machine coverage ratio (higher = richer coverage).",
    )
    parser.add_argument(
        "--smoothness-penalty",
        type=float,
        default=0.01,
        help="Bias penalty weight for day-to-day changes (higher = smoother daily totals).",
    )
    parser.add_argument(
        "--variance-penalty",
        type=float,
        default=0.03,
        help="Bias penalty weight for daily production variance (higher = more stable daily totals).",
    )
    parser.add_argument(
        "--export",
        type=str,
        default=None,
        help="Save selected schedules; suffixes _penalty/_production will be appended.",
    )
    return parser
