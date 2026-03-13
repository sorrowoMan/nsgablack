# -*- coding: utf-8 -*-
"""Project entrypoint with explicit registration zones.

Keep assembly in this file and wire components in order:
1) problem / 问题定义
2) pipeline / 表示与修复
3) bias / 软偏置
4) solver core / 求解器核心
5) observability plugins / 观测插件
6) project plugins / 项目插件
7) optional checkpoint / 可选断点续跑

Stage-gate reminder:
- Gate 1: problem semantics only
- Gate 2: layer placement
- Gate 3: catalog candidate review
- Gate 4: zone wiring (this file)
"""

from __future__ import annotations

import argparse
from datetime import datetime

from nsgablack.adapters import VNSAdapter
from nsgablack.core.evolution_solver import EvolutionSolver
from nsgablack.representation import ContextGaussianMutation
from nsgablack.representation import GaussianMutation
from nsgablack.utils.wiring import attach_checkpoint_resume
from nsgablack.utils.wiring import attach_observability_profile
from nsgablack.utils.context.context_keys import KEY_MUTATION_SIGMA

from bias.example_bias import build_bias_module
from pipeline.example_pipeline import build_pipeline
from plugins.example_plugin import ExampleProjectPlugin
from problem.example_problem import ExampleProblem


# --- Zone 1: problem / 问题定义 ---------------------------------------------
def _extend_problem_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--dimension", type=int, default=8)


def _register_problem(args) -> ExampleProblem:
    # DO: only create problem semantics.
    # DO NOT: attach plugins / strategy / repair rules here.
    return ExampleProblem(dimension=int(args.dimension))


# --- Zone 2: pipeline / 表示与修复 ------------------------------------------
def _extend_pipeline_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--no-vns-auto-context-mutator",
        action="store_true",
        help="Disable automatic GaussianMutation -> ContextGaussianMutation upgrade for VNS strategy.",
    )


def _register_pipeline(args):
    # DO: keep init/mutate/repair/encode-decode here.
    # DO NOT: put business objective semantics here.
    pipeline = build_pipeline()
    if _use_vns(args) and not bool(args.no_vns_auto_context_mutator):
        _upgrade_pipeline_for_vns(pipeline)
    return pipeline


# --- Zone 3: bias / 软偏置 -------------------------------------------------
def _extend_bias_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--enable-bias", action="store_true")


def _register_bias(problem: ExampleProblem, args):
    _ = problem
    # DO: soft guidance only.
    # DO NOT: hard-feasibility enforcement (belongs to pipeline repair).
    return build_bias_module(enable_bias=bool(args.enable_bias))


# --- Zone 4: solver core / 求解器核心 --------------------------------------
def _extend_solver_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--strategy",
        choices=["nsga2", "vns"],
        default="nsga2",
        help="Optimization strategy adapter. vns path is wired directly (no suite entrypoint).",
    )
    parser.add_argument("--pop-size", type=int, default=80, help="Population size for each generation.")
    parser.add_argument("--generations", type=int, default=60, help="Maximum number of generations.")
    parser.add_argument("--vns-batch-size", type=int, default=32, help="VNS candidates proposed per step.")
    parser.add_argument("--vns-k-max", type=int, default=5, help="VNS maximum neighborhood index.")
    parser.add_argument("--vns-base-sigma", type=float, default=0.2, help="VNS base mutation sigma.")
    parser.add_argument("--vns-scale", type=float, default=1.6, help="VNS sigma scale between neighborhoods.")
    parser.add_argument("--vns-max-sigma", type=float, default=10.0, help="VNS sigma upper bound.")
    parser.add_argument(
        "--vns-accept-tolerance",
        type=float,
        default=0.0,
        help="VNS improvement tolerance when accepting candidate.",
    )
    parser.add_argument(
        "--vns-objective-aggregation",
        choices=["sum", "first"],
        default="sum",
        help="VNS fallback scalarization for multi-objective scoring.",
    )
    parser.add_argument("--vns-no-restart", action="store_true", help="Disable VNS restart on stagnation.")
    parser.add_argument("--plugin-strict", action="store_true", help="Fail fast on plugin callback errors.")
    parser.add_argument(
        "--quickstart",
        action="store_true",
        help="Apply a lightweight profile for fast smoke runs (small pop/gens, low observability overhead).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Build and validate assembly only; do not execute solver.run().",
    )
    parser.add_argument(
        "--thread-bias-isolation",
        choices=["deepcopy", "disable_cache", "off"],
        default="deepcopy",
        help="Thread backend bias isolation policy when parallel evaluation is enabled.",
    )


def _register_solver(problem: ExampleProblem, pipeline, bias_module, args) -> EvolutionSolver:
    # DO: wire solver + adapter/strategy parameters.
    # DO NOT: spread plugin registration into this zone.
    solver = EvolutionSolver(problem, bias_module=bias_module)
    solver.pop_size = int(args.pop_size)
    solver.max_generations = int(args.generations)
    solver.mutation_rate = 0.2
    solver.crossover_rate = 0.8
    solver.enable_progress_log = True
    solver.report_interval = max(1, solver.max_generations // 10)
    solver.set_representation_pipeline(pipeline)
    solver.parallel_thread_bias_isolation = str(args.thread_bias_isolation)
    if _use_vns(args):
        solver.set_adapter(
            VNSAdapter(
                batch_size=max(1, int(args.vns_batch_size)),
                k_max=max(0, int(args.vns_k_max)),
                base_sigma=max(1e-12, float(args.vns_base_sigma)),
                scale=max(1e-12, float(args.vns_scale)),
                max_sigma=max(1e-12, float(args.vns_max_sigma)),
                accept_tolerance=float(args.vns_accept_tolerance),
                restart_on_stagnation=not bool(args.vns_no_restart),
                objective_aggregation=str(args.vns_objective_aggregation),
            )
        )
    if hasattr(solver, "plugin_manager") and getattr(solver, "plugin_manager", None) is not None:
        try:
            solver.plugin_manager.strict = bool(args.plugin_strict)
        except Exception:
            pass
    return solver


# --- Zone 5: observability plugins / 观测插件 -------------------------------
def _extend_observability_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--observability-profile",
        choices=["quickstart", "default", "strict"],
        default="default",
        help="Plug-and-play profile for observability wiring.",
    )
    parser.add_argument("--no-profiler", action="store_true", help="Disable runtime profiler plugin.")
    parser.add_argument("--no-decision-trace", action="store_true", help="Disable decision-trace plugin.")
    parser.add_argument("--run-dir", default="runs", help="Output directory for run artifacts.")
    parser.add_argument("--run-id", default=None, help="Optional run id. Auto-generated when omitted.")


def _register_observability_plugins(solver: EvolutionSolver, args, run_id: str) -> None:
    # Framework observability/runtime plugins only.
    attach_observability_profile(
        solver,
        profile=str(args.observability_profile),
        output_dir=str(args.run_dir),
        run_id=run_id,
        enable_profiler=False if bool(args.no_profiler) else None,
        enable_decision_trace=False if bool(args.no_decision_trace) else None,
    )


# --- Zone 6: project plugins / 项目插件 ------------------------------------
def _extend_project_plugin_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--enable-example-plugin", action="store_true", help="Enable the example project plugin.")


def _register_project_plugins(solver: EvolutionSolver, args) -> None:
    # Register domain/business plugins in this zone only.
    if bool(args.enable_example_plugin):
        solver.add_plugin(ExampleProjectPlugin(interval=5, verbose=True))


# --- Zone 7: optional checkpoint / 可选断点续跑 -----------------------------
def _extend_checkpoint_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--enable-checkpoint", action="store_true", help="Enable checkpoint + auto-resume wiring.")
    parser.add_argument("--checkpoint-dir", default="runs/checkpoints", help="Directory for checkpoint files.")
    parser.add_argument(
        "--trust-checkpoint",
        action="store_true",
        help="Explicitly trust unsigned checkpoints for resume (not allowed with strict mode).",
    )


def _register_optional_checkpoint(solver: EvolutionSolver, args) -> None:
    # Optional engineering capability; keep isolated from core zones.
    if not bool(args.enable_checkpoint):
        return
    attach_checkpoint_resume(
        solver,
        checkpoint_dir=str(args.checkpoint_dir),
        auto_resume=True,
        strict=not bool(args.trust_checkpoint),
        trust_checkpoint=bool(args.trust_checkpoint),
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build and run the standard NSGABlack project scaffold.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    _extend_problem_args(parser)
    _extend_pipeline_args(parser)
    _extend_bias_args(parser)
    _extend_solver_args(parser)
    _extend_observability_args(parser)
    _extend_project_plugin_args(parser)
    _extend_checkpoint_args(parser)
    return parser


def _parse_args(argv: list[str] | None = None):
    parser = _build_parser()
    args, _ = parser.parse_known_args(argv)
    if bool(getattr(args, "quickstart", False)):
        args.pop_size = min(int(args.pop_size), 20)
        args.generations = min(int(args.generations), 10)
        args.observability_profile = "quickstart"
        args.no_profiler = True
        args.no_decision_trace = True
    return args


def _use_vns(args) -> bool:
    return str(getattr(args, "strategy", "nsga2")).strip().lower() == "vns"


def _upgrade_pipeline_for_vns(pipeline) -> None:
    mutator = getattr(pipeline, "mutator", None)
    if isinstance(mutator, ContextGaussianMutation):
        return
    if not isinstance(mutator, GaussianMutation):
        return
    pipeline.mutator = ContextGaussianMutation(
        base_sigma=float(getattr(mutator, "sigma", 0.1)),
        sigma_key=KEY_MUTATION_SIGMA,
        low=getattr(mutator, "low", None),
        high=getattr(mutator, "high", None),
    )


def build_solver(argv: list[str] | None = None) -> EvolutionSolver:
    args = _parse_args(argv)
    run_id = str(args.run_id) if args.run_id else datetime.now().strftime("%Y%m%d_%H%M%S")

    problem = _register_problem(args)
    pipeline = _register_pipeline(args)
    bias_module = _register_bias(problem, args)
    solver = _register_solver(problem, pipeline, bias_module, args)
    _register_observability_plugins(solver, args, run_id)
    _register_project_plugins(solver, args)
    _register_optional_checkpoint(solver, args)
    return solver


def main() -> None:
    args = _parse_args()
    solver = build_solver()
    if bool(getattr(args, "check", False)):
        plugin_count = len(getattr(getattr(solver, "plugin_manager", None), "plugins", []) or [])
        pipeline = getattr(solver, "representation_pipeline", None)
        mutator_name = type(getattr(pipeline, "mutator", None)).__name__
        print(
            "[check] assembly ok | "
            f"problem={type(getattr(solver, 'problem', None)).__name__} | "
            f"pipeline={type(getattr(solver, 'representation_pipeline', None)).__name__} | "
            f"mutator={mutator_name} | "
            f"adapter={type(getattr(solver, 'adapter', None)).__name__} | "
            f"plugins={plugin_count}"
        )
        return
    if bool(getattr(args, "quickstart", False)):
        print("[quickstart] lightweight profile enabled (small pop/gens, observability reduced)")
    result = solver.run(return_dict=True)
    pareto_payload = result.get("pareto_solutions", None)
    if isinstance(pareto_payload, dict):
        objs = pareto_payload.get("objectives")
    else:
        objs = result.get("pareto_objectives", None)
    if objs is not None and len(objs) > 0:
        best_f1 = min(float(row[0]) for row in objs)
        print(f"[example] best_objective_0={best_f1:.6f}")
    else:
        print("[example] run finished but no pareto objectives were returned")


if __name__ == "__main__":
    main()
