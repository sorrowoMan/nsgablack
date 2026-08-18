# -*- coding: utf-8 -*-
# Canonical Case build_solver entry (Project/Case/Scaffold layout).

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from _bootstrap import ensure_nsgablack_importable

ensure_nsgablack_importable(Path(__file__))

from adapter.config import event, group, phase, serial
from assembly import (
    apply_solver_profile,
    attach_checkpoint,
    attach_evaluation,
    attach_governance,
    attach_observability,
    attach_ops,
    attach_runtime,
    attach_search,
    build_modeling,
)
from config import get_project_config
from solver.config import apply_runtime_governance, apply_store_profile, build_evolution_solver


def _normalize_strategy(value: str | None) -> str:
    if value is None:
        return "default"
    return str(value).strip().lower()


def build_solver(run_id: str | None = None, *, strategy: str | None = None, quickstart: bool = False, resource_context=None, component_overrides=None):
    cfg = get_project_config()
    strategy_key = _normalize_strategy(strategy)

    # --- Modeling -----------------------------------------------------
    problem, pipeline, bias_module = build_modeling(
        cfg,
        problem_key="example",
        pipeline_key="default",
        bias_key="none",
    )
    solver = build_evolution_solver(problem, bias_module=bias_module)
    apply_store_profile(solver, cfg.store_profiles, "default")
    apply_runtime_governance(solver, cfg.runtime_governance, "default")
    solver.set_representation_pipeline(pipeline)

    # --- Core ---------------------------------------------------------
    apply_solver_profile(solver, cfg, "default")

    # --- Search orchestration (built-in) ------------------------------
    if strategy_key not in {"", "default", "none"}:
        search_adapter = build_search(cfg.adapters, primary_key=strategy_key, mode="single")
        attach_search(solver, search_adapter)

    # --- L0 -----------------------------------------------------------
    attach_runtime(solver, cfg, "local_cpu")

    # --- L4 -----------------------------------------------------------
    attach_evaluation(solver, cfg, ())

    # --- L3 Governance ------------------------------------------------
    attach_governance(solver, cfg, ())

    # --- L1/L2 Observability + Ops -----------------------------------
    run_id = str(run_id) if run_id else datetime.now().strftime("%Y%m%d_%H%M%S")
    obs_profile = "quickstart" if bool(quickstart) else "default"
    attach_observability(solver, cfg, run_id, obs_profile)
    attach_ops(solver, cfg, ())

    # Optional checkpoint
    # attach_checkpoint(solver, cfg, "default")
    from nsgablack.project import apply_solver_component_overrides
    apply_solver_component_overrides(solver, component_overrides)
    solver.set_resource_context(resource_context)
    return solver


# --- Search orchestration (built-in) --------------------------------------
def build_search(registry, *, primary_key: str, mode: str) -> object | None:
    base = group(registry, "primary", [primary_key])
    mode = str(mode or "single").lower()
    if "serial" in mode or "multi" in mode:
        phases = [phase("primary", base)]
        return serial(registry, "search_flow", phases)
    if "event" in mode:
        return event(registry, "event_flow", [base])
    return base


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build and run the classification threshold calibration case.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Build and validate assembly only; do not execute solver.run().",
    )
    parser.add_argument("--run-id", default=None, help="Optional run id. Auto-generated when omitted.")
    parser.add_argument(
        "--strategy",
        default="default",
        help="Search strategy key (default).",
    )
    parser.add_argument(
        "--quickstart",
        action="store_true",
        help="Use quickstart observability profile.",
    )
    return parser


def _print_result(solver, result: dict) -> None:
    pareto_payload = result.get("pareto_solutions", None)
    solutions = None
    if isinstance(pareto_payload, dict):
        objs = pareto_payload.get("objectives")
        solutions = pareto_payload.get("solutions")
        if solutions is None:
            solutions = pareto_payload.get("population")
    else:
        objs = result.get("pareto_objectives", None)
        solutions = pareto_payload
    if objs is None or len(objs) <= 0:
        print("[classification_threshold] run finished but no pareto objectives were returned")
        return
    best_idx = min(range(len(objs)), key=lambda idx: float(objs[idx][1]))
    best = objs[best_idx]
    problem = getattr(solver, "problem", None)
    if solutions is not None and problem is not None and best_idx < len(solutions):
        problem.evaluate(solutions[best_idx])
    print(
        "[classification_threshold] "
        f"valid_log_loss={float(best[0]):.6f} "
        f"f1_loss={float(best[1]):.6f} "
        f"intervention_rate={float(best[2]):.6f}"
    )
    report = getattr(problem, "last_report", {}) or {}
    recipe = report.get("recipe", {})
    if recipe:
        print(f"[classification_threshold] best_recipe={recipe}")
    if report:
        print(
            "[classification_threshold] "
            f"valid_f1={float(report.get('valid_f1', 0.0)):.6f} "
            f"precision={float(report.get('valid_precision', 0.0)):.6f} "
            f"recall={float(report.get('valid_recall', 0.0)):.6f}"
        )


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    solver = build_solver(run_id=args.run_id, strategy=args.strategy, quickstart=bool(args.quickstart))
    if bool(args.check):
        plugin_count = len(getattr(getattr(solver, "plugin_manager", None), "plugins", []) or [])
        providers = getattr(getattr(solver, "evaluation_mediator", None), "list_providers", None)
        provider_count = len(tuple(providers())) if callable(providers) else 0
        pipeline = getattr(solver, "representation_pipeline", None)
        mutator_name = type(getattr(pipeline, "mutator", None)).__name__
        print(
            "[check] assembly ok | "
            f"problem={type(getattr(solver, 'problem', None)).__name__} | "
            f"pipeline={type(getattr(solver, 'representation_pipeline', None)).__name__} | "
            f"mutator={mutator_name} | "
            f"adapter={type(getattr(solver, 'adapter', None)).__name__} | "
            f"providers={provider_count} | "
            f"plugins={plugin_count}"
        )
        return
    _print_result(solver, solver.run(return_dict=True))


if __name__ == "__main__":
    main()
