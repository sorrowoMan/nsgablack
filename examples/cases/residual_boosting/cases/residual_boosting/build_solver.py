# -*- coding: utf-8 -*-
# Canonical Case build_solver entry (Project/Case/Scaffold layout).

from __future__ import annotations

from datetime import datetime
from pathlib import Path

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
