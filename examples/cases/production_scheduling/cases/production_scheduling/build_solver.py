# -*- coding: utf-8 -*-
"""Standard assembly entry for production_scheduling case.

This file is both:
- scaffold entry (doctor/inspector expects `build_solver:build_solver`)
- real assembly module (problem/pipeline/adapter/plugins wiring)


python examples/cases/production_scheduling/solver/run_case.py --solver baseline-aco --single-objective --aco-ants 48
python examples/cases/production_scheduling/solver/run_case.py --solver multi-agent --parallel --parallel-backend thread --parallel-workers 8 `
  --moead-pop-size 50 --vns-batch-size 32 --generations 30 `
  --material-cap-ratio 2.6 --daily-cap-ratio 2.8 `
  --daily-floor-ratio 0.35 --smooth-strength 0.2 --reserve-ratio 0.4

"""

from __future__ import annotations

import random
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np

_THIS_DIR = Path(__file__).resolve().parent

from nsgablack.adapters import (  # noqa: E402
    MOEADAdapter,
    MOEADConfig,
    MultiStrategyConfig,
    StrategyRouterAdapter,
    RoleSpec,
    VNSAdapter,
    VNSConfig,
)
from nsgablack.core.composable_solver import ComposableSolver  # noqa: E402
from nsgablack.plugins import ParetoArchiveConfig, ParetoArchivePlugin  # noqa: E402
from nsgablack.utils.parallel import with_parallel_evaluation  # noqa: E402
from nsgablack.utils.wiring import attach_default_observability_plugins  # noqa: E402

from adapter import (  # noqa: E402
    ProductionACOBaselineAdapter,
    ProductionGreedyBaselineAdapter,
    ProductionLocalSearchAdapter,
    ProductionRandomSearchAdapter,
)
from bias import build_production_bias_module  # noqa: E402
from cli import build_parser  # noqa: E402
from pipeline import build_schedule_pipeline  # noqa: E402
from plugins import ConsoleProgressPlugin, ProductionExportPlugin  # noqa: E402
from plugins.export_utils import (  # noqa: E402
    choose_pareto_solutions,
    export_pareto_batch as export_pareto_batch_fn,
    export_schedule,
    extract_pareto,
    get_export_path,
    supply_tag_from_path,
    write_export_summary,
)
from problem import build_problem, build_problem_factory  # noqa: E402
from solver.strict_feasible_solver import (  # noqa: E402
    StrictFeasibleProductionSolver,
    project_schedule_material_feasible,
)


def _export_pareto_batch_with_projection(problem, individuals, objectives, base_export, mode, limit) -> int:
    return export_pareto_batch_fn(
        problem,
        individuals,
        objectives,
        base_export,
        mode,
        limit,
        project_schedule_material_feasible=project_schedule_material_feasible,
    )


def _attach_observability_plugins(solver, args) -> None:
    if bool(getattr(args, "no_run_logs", False)):
        return
    run_dir = Path(args.run_dir) if getattr(args, "run_dir", None) else (_THIS_DIR / "runs" / "production_schedule")
    run_id = str(args.run_id) if getattr(args, "run_id", None) else datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = run_dir.expanduser().resolve()
    attach_default_observability_plugins(
        solver,
        output_dir=str(run_dir),
        run_id=str(run_id),
        overwrite=True,
        enable_pareto_archive=False,
        enable_benchmark=True,
        benchmark_log_every=int(getattr(args, "log_every", 1) or 1),
        benchmark_flush_every=10,
        enable_module_report=True,
        write_bias_markdown=not bool(getattr(args, "no_bias_md", False)),
        enable_profiler=not bool(getattr(args, "no_profile", False)),
        enable_decision_trace=not bool(getattr(args, "no_decision_trace", False)),
        decision_trace_flush_every=max(1, int(getattr(args, "decision_trace_flush_every", 1))),
    )
    print(f"[run] logs_dir={run_dir} run_id={run_id}")


def _register_case_plugins(solver, problem, args) -> None:
    """Explicit plugin registration zone."""
    archive_size = int(getattr(args, "pareto_archive_size", 512) or 0)
    archive_max_size = None if archive_size <= 0 else archive_size
    archive_update_every = max(1, int(getattr(args, "pareto_archive_update_every", 5) or 1))
    solver.add_plugin(
        ParetoArchivePlugin(
            config=ParetoArchiveConfig(
                max_size=archive_max_size,
                update_every=archive_update_every,
            )
        )
    )
    solver.add_plugin(ConsoleProgressPlugin(report_every=args.report_every))
    solver.add_plugin(
        ProductionExportPlugin(
            problem,
            args,
            extract_pareto=extract_pareto,
            choose_pareto_solutions=choose_pareto_solutions,
            project_schedule_material_feasible=project_schedule_material_feasible,
            get_export_path=get_export_path,
            export_schedule=export_schedule,
            write_export_summary=write_export_summary,
            export_pareto_batch=_export_pareto_batch_with_projection,
            supply_tag_from_path=supply_tag_from_path,
        )
    )


def run_nsga2(problem, args):
    del problem, args
    raise RuntimeError(
        "nsga2 path has been removed from this application entrypoint. "
        "Use `--solver multi-agent` (default) for cooperative search."
    )


def build_multi_agent_solver(problem, args):
    """Build solver for multi-agent cooperation (no run)."""
    pipeline = build_schedule_pipeline(
        problem,
        problem.constraints,
        material_cap_ratio=args.material_cap_ratio,
        daily_floor_ratio=args.daily_floor_ratio,
        donor_keep_ratio=args.donor_keep_ratio,
        daily_cap_ratio=args.daily_cap_ratio,
        reserve_ratio=args.reserve_ratio,
        coverage_bonus=args.coverage_bonus,
        budget_mode=args.budget_mode,
        smooth_strength=args.smooth_strength,
        smooth_passes=args.smooth_passes,
    )
    if bool(getattr(args, "no_pipeline", False)):
        pipeline.repair = None

    bias_module = (
        None
        if args.no_bias
        else build_production_bias_module(
            problem,
            weights={
                "coverage_reward": args.coverage_reward,
                "smoothness_penalty": args.smoothness_penalty,
                "variance_penalty": args.variance_penalty,
            },
        )
    )

    total_batch = max(8, int(args.pop_size))
    explorer_batch = max(4, int(total_batch * 0.65))
    exploiter_batch = max(4, total_batch - explorer_batch)

    roles = []
    if str(getattr(args, "explorer_adapter", "moead")).lower() == "random":
        roles.append(
            RoleSpec(
                name="explorer",
                adapter=lambda uid: ProductionRandomSearchAdapter(batch_size=max(4, explorer_batch // 4)),
                n_units=4,
                weight=1.0,
            )
        )
    else:
        moead_pop = max(4, int(getattr(args, "moead_pop_size", max(8, args.pop_size // 2))))
        moead_neighbor = max(2, int(getattr(args, "moead_neighborhood", 20)))
        moead_nr = max(1, int(getattr(args, "moead_nr", 2)))
        moead_delta = float(getattr(args, "moead_delta", 0.9))
        roles.append(
            RoleSpec(
                name="explorer",
                adapter=lambda uid: MOEADAdapter(
                    MOEADConfig(
                        population_size=moead_pop,
                        neighborhood_size=moead_neighbor,
                        batch_size=max(4, explorer_batch),
                        delta=moead_delta,
                        nr=moead_nr,
                        variation="pipeline",
                        random_seed=(None if args.seed is None else int(args.seed) + int(uid)),
                    )
                ),
                n_units=1,
                weight=1.0,
            )
        )

    if str(getattr(args, "exploiter_adapter", "vns")).lower() == "local":
        roles.append(
            RoleSpec(
                name="exploiter",
                adapter=lambda uid: ProductionLocalSearchAdapter(batch_size=max(2, exploiter_batch // 2)),
                n_units=2,
                weight=1.0,
            )
        )
    else:
        vns_batch = max(4, int(getattr(args, "vns_batch_size", exploiter_batch)))
        vns_kmax = max(1, int(getattr(args, "vns_k_max", 4)))
        vns_sigma = float(getattr(args, "vns_base_sigma", 0.2))
        roles.append(
            RoleSpec(
                name="exploiter",
                adapter=lambda uid: VNSAdapter(
                    VNSConfig(
                        batch_size=vns_batch,
                        k_max=vns_kmax,
                        base_sigma=vns_sigma,
                        scale=1.6,
                        objective_aggregation="sum",
                    )
                ),
                n_units=1,
                weight=1.0,
            )
        )

    cfg = MultiStrategyConfig(
        total_batch_size=total_batch,
        objective_aggregation="sum",
        adapt_weights=True,
        stagnation_window=max(5, int(args.adapt_interval)),
        enable_regions=False,
        region_update_interval=max(0, int(args.comm_interval)),
        phase_schedule=(("explore", max(5, int(args.generations // 3))), ("exploit", -1)),
        phase_roles={"explore": ["explorer"], "exploit": ["exploiter"]},
    )
    controller = StrategyRouterAdapter(roles=roles, config=cfg)

    base_solver_cls = ComposableSolver if bool(getattr(args, "allow_infeasible_update", False)) else StrictFeasibleProductionSolver
    SolverClass = with_parallel_evaluation(base_solver_cls)
    factory = (
        build_problem_factory(args, base_dir=_THIS_DIR)
        if args.parallel and args.parallel_backend in ("process", "ray")
        else None
    )
    solver = SolverClass(
        problem=problem,
        adapter=controller,
        representation_pipeline=pipeline,
        bias_module=bias_module,
        enable_parallel=bool(args.parallel),
        parallel_backend=args.parallel_backend,
        parallel_max_workers=args.parallel_workers,
        parallel_chunk_size=args.parallel_chunk_size,
        parallel_verbose=bool(args.parallel_verbose),
        parallel_precheck=not bool(args.parallel_no_precheck),
        parallel_strict=bool(args.parallel_strict),
        parallel_thread_bias_isolation=str(args.parallel_thread_bias_isolation),
        parallel_problem_factory=factory,
    )

    _attach_observability_plugins(solver, args)
    _register_case_plugins(solver, problem, args)
    solver.set_max_steps(int(args.generations))
    return solver


def run_multi_agent(problem, args, *, resource_context=None):
    solver = build_multi_agent_solver(problem, args)
    solver.set_resource_context(resource_context)
    solver.run()

    individuals, objectives = extract_pareto(solver)
    print(f"Pareto size: {0 if individuals is None else len(individuals)}")
    choices = choose_pareto_solutions(problem, individuals, objectives) if individuals is not None else []
    if choices:
        print(f"Selected key Pareto candidates: {len(choices)} (export handled by production_export plugin)")


def build_baseline_solver(problem, args, *, mode: str) -> ComposableSolver:
    pipeline = build_schedule_pipeline(
        problem,
        problem.constraints,
        material_cap_ratio=args.material_cap_ratio,
        daily_floor_ratio=args.daily_floor_ratio,
        donor_keep_ratio=args.donor_keep_ratio,
        daily_cap_ratio=args.daily_cap_ratio,
        reserve_ratio=args.reserve_ratio,
        coverage_bonus=args.coverage_bonus,
        budget_mode=args.budget_mode,
        smooth_strength=args.smooth_strength,
        smooth_passes=args.smooth_passes,
    )
    if bool(getattr(args, "no_pipeline", False)):
        pipeline.repair = None

    bias_module = None if args.no_bias else build_production_bias_module(problem, weights={})
    if bias_module is not None and hasattr(bias_module, "cache_enabled"):
        try:
            setattr(bias_module, "cache_enabled", False)
        except Exception:
            pass

    if mode == "baseline-aco":
        adapter = ProductionACOBaselineAdapter(
            ants=int(args.aco_ants),
            evaporation=float(args.aco_evaporation),
            alpha=float(args.aco_alpha),
            beta=float(args.aco_beta),
            q=float(args.aco_q),
        )
    else:
        adapter = ProductionGreedyBaselineAdapter()

    base_solver_cls = ComposableSolver if bool(getattr(args, "allow_infeasible_update", False)) else StrictFeasibleProductionSolver
    SolverClass = with_parallel_evaluation(base_solver_cls)
    factory = (
        build_problem_factory(args, base_dir=_THIS_DIR)
        if args.parallel and args.parallel_backend in ("process", "ray")
        else None
    )
    solver = SolverClass(
        problem=problem,
        adapter=adapter,
        representation_pipeline=pipeline,
        bias_module=bias_module,
        enable_parallel=bool(args.parallel),
        parallel_backend=args.parallel_backend,
        parallel_max_workers=args.parallel_workers,
        parallel_chunk_size=args.parallel_chunk_size,
        parallel_verbose=bool(args.parallel_verbose),
        parallel_precheck=not bool(args.parallel_no_precheck),
        parallel_strict=bool(args.parallel_strict),
        parallel_thread_bias_isolation=str(args.parallel_thread_bias_isolation),
        parallel_problem_factory=factory,
    )
    _attach_observability_plugins(solver, args)
    _register_case_plugins(solver, problem, args)
    solver.set_max_steps(int(args.generations))
    return solver


def _build_solver_from_args(args, *, resource_context=None) -> ComposableSolver:
    if int(getattr(args, "days", 31)) != 31:
        print(f"[run] override --days={args.days} ignored; enforcing 31-day window (day0..30).")
    args.days = 31
    if str(getattr(args, "solver", "multi-agent")).startswith("baseline"):
        if not bool(getattr(args, "single_objective", False)):
            args.single_objective = True
            print("[run] baseline solver -> force --single-objective (maximize total output only)")
        if getattr(args, "parallel_backend", None) != "thread":
            args.parallel_backend = "thread"
            args.parallel = True
            print("[run] baseline solver -> force --parallel-backend thread")
        if getattr(args, "parallel_thread_bias_isolation", None) == "deepcopy":
            args.parallel_thread_bias_isolation = "disable_cache"
            print("[run] baseline solver -> force --parallel-thread-bias-isolation disable_cache")
    problem = build_problem(args, base_dir=_THIS_DIR, print_paths=True)
    if args.solver == "baseline-aco":
        solver = build_baseline_solver(problem, args, mode="baseline-aco")
    elif args.solver == "baseline-greedy":
        solver = build_baseline_solver(problem, args, mode="baseline-greedy")
    else:
        solver = build_multi_agent_solver(problem, args)
    solver.set_resource_context(resource_context)
    return solver


def build_solver(argv: Optional[list] = None, *, case_root: Optional[Path] = None, resource_context=None, component_overrides=None) -> ComposableSolver:
    del case_root
    overrides = dict(component_overrides or {})
    configured_argv = overrides.pop("argv", argv)
    parser = build_parser()
    args = parser.parse_args(configured_argv if configured_argv is not None else [])
    if bool(getattr(args, "check", False)):
        args.no_run_logs = True
    if not getattr(args, "run_id", None):
        args.run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    random.seed(args.seed)
    np.random.seed(args.seed)
    solver = _build_solver_from_args(args, resource_context=resource_context)
    from nsgablack.project import apply_solver_component_overrides

    apply_solver_component_overrides(solver, overrides)
    return solver
