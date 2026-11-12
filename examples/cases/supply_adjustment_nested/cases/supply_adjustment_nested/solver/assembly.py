"""Formal L1/L2 nested assembly for event-level supply adjustment.

Outer layer:
- decision variables are shift days for each non-zero supply event (day>0)

Inner layer:
- production evaluation model computes output under adjusted supply

Rules enforced:
- day0 fixed
- only early shift (no delay)
- whole-event move (no split)
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

import numpy as np
from blackbase.resources import coerce_resource_context

_THIS_DIR = Path(__file__).resolve().parents[1]

from nsgablack.core.evolution_solver import EvolutionSolver  # noqa: E402
from nsgablack.core.composable_solver import ComposableSolver  # noqa: E402
from blackbase.resources import ResourceRequirement  # noqa: E402
from nsgablack.core.control_plane import BudgetController
from nsgablack.adapters import FixedCandidateAdapter  # noqa: E402
from nsgablack.utils.wiring import attach_default_observability_plugins  # noqa: E402

from inner_solver import InnerProductionSolverConfig
from problem import SupplyEventShiftProblem
from pipeline import build_pipeline
from runtime import load_production_case_data, resolve_production_case_dir


def _load_case_data(base_dir: Path, bom: Optional[str], supply: Optional[str], *, machines: int, materials: int, days: int, production_case_dir=None):
    """Reuse production_scheduling data loader for BOM/SUPPLY parsing."""
    del base_dir
    data = load_production_case_data(
        bom_path=bom,
        supply_path=supply,
        machines=int(machines),
        materials=int(materials),
        days=int(days),
        production_case_dir=production_case_dir,
    )
    if getattr(data, "bom_path", None) is None or getattr(data, "supply_path", None) is None:
        raise RuntimeError("BOM/SUPPLY not resolved; provide --bom and --supply explicitly.")
    print(f"[data] bom={data.bom_path}")
    print(f"[data] supply={data.supply_path}")
    return data


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="正式供应调整 -> 生产排程联合求解；今天库存固定")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--inner-seed", type=int, default=42)
    p.add_argument("--machines", type=int, default=22)
    p.add_argument("--materials", type=int, default=157)
    p.add_argument("--days", type=int, default=31)
    p.add_argument("--bom")
    p.add_argument("--supply")
    p.add_argument("--production-case-dir")
    p.add_argument("--baseline-plan", help="已废弃；供应复核使用 evaluation-only 和显式 candidate")
    p.add_argument("--max-active-machines", type=int, default=8)
    p.add_argument("--max-production-per-machine", type=float, default=3000)
    p.add_argument("--max-moved-events", type=int, default=100)
    p.add_argument("--pop-size", type=int, default=12)
    p.add_argument("--generations", type=int, default=5)
    p.add_argument("--max-evaluations", type=int, default=72)
    p.add_argument("--hybrid-refine-pop-size", "--inner-pop-size", dest="hybrid_refine_pop_size", type=int, default=24)
    p.add_argument("--hybrid-refine-generations", "--inner-generations", dest="hybrid_refine_generations", type=int, default=7)
    p.add_argument("--inner-max-evaluations", type=int, default=192)
    p.add_argument("--evaluation-only", action="store_true")
    p.add_argument("--portable-inputs", action="store_true", help="通过正式BOM/到料Artifact输入调用内层，Worker不使用协调端路径")
    p.add_argument("--parallel", action="store_true", help="仅在内层授权内启用线程评估")
    p.add_argument("--outer-parallel-workers", type=int, default=1,
                   help="同批完整生产Case的并发请求数；生效上限与本机/远端放置由Project L0授权")
    p.add_argument("--outer-parallel-backend", choices=["thread", "redis"], default="thread")
    p.add_argument("--inner-parallel-workers", type=int, default=1)
    p.add_argument("--inner-memory-mb", type=float, default=2048)
    p.add_argument("--inner-gpus", type=int, default=0)
    p.add_argument("--inner-device-token", action="append", default=[])
    p.add_argument("--inner-gpu-memory-mb", type=float, default=0)
    p.add_argument("--nested-task-timeout-seconds", type=float, default=900)
    p.add_argument("--run-id")
    p.add_argument("--run-dir", default="runs/supply_adjustment_nested")
    p.add_argument("--no-decision-trace", action="store_true")
    p.add_argument("--no-profiler", action="store_true")
    p.add_argument("--check", action="store_true")
    p.add_argument("--ui", action="store_true")
    return p


def _build_solver_from_args(args, *, resource_context=None, candidate=None):
    from evaluation.production_case import build_production_evaluator

    if args.days != 31:
        raise ValueError("supply adjustment preserves the complete day0..30 window")
    if args.max_evaluations < 1 or args.inner_max_evaluations < 1:
        raise ValueError("outer and inner evaluation caps must be positive")
    if args.baseline_plan:
        raise ValueError("baseline-plan is not a supply input; evaluate an explicit candidate using evaluation-only")
    if args.outer_parallel_backend == "redis":
        raise ValueError("configure Project L0.nested_execution for external standard Cases, not the legacy Redis candidate backend")
    if args.outer_parallel_workers < 1 or args.inner_parallel_workers < 1:
        raise ValueError("outer and inner worker requests must be positive")
    data = _load_case_data(_THIS_DIR, args.bom, args.supply,
                           machines=args.machines, materials=args.materials, days=args.days,
                           production_case_dir=args.production_case_dir)
    outer_workers = max(1, int(args.outer_parallel_workers or 1))
    inner_workers = max(1, int(args.inner_parallel_workers or 1))
    external_cases = False
    if resource_context is not None:
        grant = coerce_resource_context(resource_context)
        nested_execution = dict(grant.metadata.get("nested_execution", {}) or {})
        external_cases = "production_inner" in nested_execution.get("case_names", ())
        requested_outer, requested_inner = outer_workers, inner_workers
        if not external_cases:
            outer_workers = min(outer_workers, max(1, grant.threads))
            inner_workers = min(inner_workers, max(1, grant.threads // outer_workers))
        if (requested_outer, requested_inner) != (outer_workers, inner_workers):
            print(f"[l0] nested worker grant applied threads={grant.threads} "
                  f"outer_workers={requested_outer}->{outer_workers} inner_workers={requested_inner}->{inner_workers}")
    print(f"[parallel] outer_backend=project_case outer_workers_requested={outer_workers} "
          f"placement={'external' if external_cases else 'local'} inner_backend=thread inner_workers_requested={inner_workers}")
    requirement = _build_resource_requirement(
        threads=inner_workers, gpus=args.inner_gpus, memory_mb=args.inner_memory_mb,
        gpu_memory_mb=args.inner_gpu_memory_mb, device_tokens=tuple(args.inner_device_token),
        capabilities=("production_inner", "nested_eval"), metadata={"layer": "L2"})
    cfg = InnerProductionSolverConfig(
        pop_size=args.hybrid_refine_pop_size, generations=args.hybrid_refine_generations,
        seed=args.inner_seed, max_evaluations=args.inner_max_evaluations,
        max_active_machines_per_day=args.max_active_machines,
        max_production_per_machine=args.max_production_per_machine,
        parallel=bool(args.parallel), parallel_workers=inner_workers, parallel_backend="thread",
        parallel_strict=True, resource_requirement=requirement)
    problem = SupplyEventShiftProblem(
        base_supply=data.supply_matrix, bom_matrix=data.bom_matrix,
        production_case_dir=resolve_production_case_dir(args.production_case_dir), inner_solver_cfg=cfg,
        material_ids=np.arange(1, args.materials + 1),
        max_moved_events=None if args.max_moved_events <= 0 else args.max_moved_events,
        inner_resource_requirement=requirement)
    if args.evaluation_only:
        values = np.zeros(problem.dimension) if candidate is None else np.asarray(candidate, dtype=float)
        if values.shape != (problem.dimension,) or not np.array_equal(values, problem.decode_shifts(values)):
            raise ValueError("evaluation-only requires an already legal today-fixed supply candidate")
        solver = ComposableSolver(problem, adapter=FixedCandidateAdapter(),
                                  representation_pipeline=build_pipeline(problem, candidate=values),
                                  plugin_strict=True, snapshot_strict=True)
        solver.set_max_steps(1)
        outer_cap = 1
    else:
        if candidate is not None:
            raise ValueError("explicit candidate requires evaluation-only mode")
        solver = EvolutionSolver(problem, pop_size=args.pop_size, max_generations=args.generations,
                                 representation_pipeline=build_pipeline(problem),
                                 random_seed=args.seed, enable_parallel=False,
                                 plugin_strict=True, snapshot_strict=True)
        outer_cap = args.max_evaluations
    solver.set_random_seed(args.seed)
    solver.representation_pipeline.set_random_seed(args.seed)
    solver.register_controller(BudgetController(max_evaluations=outer_cap, name="supply_evaluation_budget"))
    solver.set_incumbent_scalarizer(_supply_adjustment_score, policy_id="supply_adjustment.weighted_sum/v1")
    problem.inner_runtime_evaluator = build_production_evaluator(
        problem, data=data, timeout_seconds=args.nested_task_timeout_seconds or 900,
        max_workers=outer_workers, portable_inputs=args.portable_inputs)
    solver.inner_resource_requirement = requirement
    solver.outer_resource_requirement = ResourceRequirement(threads=1)
    solver.supply_source = problem.inner_runtime_evaluator.projector.__self__.source
    solver.l0_runtime_summary = {
        "schema": "supply_adjustment_nested.l0_runtime_summary.v2",
        "outer_max_evaluations": outer_cap, "inner_max_evaluations": cfg.max_evaluations,
        "inner_resource_requirement": requirement.as_dict(), "formal_child_case": "production_inner",
        "outer_case_max_workers_requested": outer_workers,
        "inner_case_placement": "project_external" if external_cases else "parent_local",
        "day0_policy": "today_inventory_fixed_no_inbound_or_outbound",
    }
    if not args.check and (not args.no_decision_trace or not args.no_profiler):
        attach_default_observability_plugins(
            solver, output_dir=str(args.run_dir), run_id=args.run_id,
            enable_decision_trace=not args.no_decision_trace, enable_profiler=not args.no_profiler)
    return solver


def _supply_adjustment_score(objective_row, violation, context):
    row = np.asarray(objective_row, dtype=float).reshape(3)
    return float(row[0] + row[1] + .25 * row[2] + 1_000_000 * max(0., float(violation)))


def build_solver(argv=None, *, resource_context=None, candidate=None):
    args = build_parser().parse_args(argv if argv is not None else [])
    solver = _build_solver_from_args(args, resource_context=resource_context, candidate=candidate)
    solver.set_resource_context(resource_context)
    return solver


def _build_resource_requirement(*, threads, gpus, memory_mb, gpu_memory_mb,
                                device_tokens, capabilities, metadata):
    return ResourceRequirement(
        threads=max(1, int(threads)), gpus=max(0, int(gpus)), resource_backend="local",
        device_tokens=device_tokens, memory_mb=memory_mb if memory_mb > 0 else None,
        gpu_memory_mb=gpu_memory_mb if gpu_memory_mb > 0 else None,
        capabilities=capabilities, metadata=metadata)
