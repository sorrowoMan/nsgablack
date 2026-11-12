"""Canonical factory; the original Case owns task validation and publication."""

from pathlib import Path
import os
import sys
from blackbase.project import build_case, load_case_builder


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    if config:
        raise ValueError("production_inner accepts its versioned task in component_overrides")
    source_project = Path(__file__).resolve().parents[3] / "supply_adjustment_nested"
    case = build_case(load_case_builder(source_project, "production_inner"),
                      resource_context=resource_context, component_overrides=component_overrides)
    if os.environ.get("NSGABLACK_RUNTIME_REPAIR_REFERENCE") == "legacy":
        import numpy as np
        repair = case.solver.representation_pipeline.problem_repair
        if not callable(getattr(repair, "_selection_availability", None)):
            raise TypeError("legacy repair reference requires the canonical supply-aware repair")
        cap = float(repair.base_repair.max_production_per_machine)
        def legacy_selection(stock, requirements):
            return lambda m: cap if requirements[m].size == 0 else float(np.min(stock[requirements[m]]))
        repair._selection_availability = legacy_selection
    if os.environ.get("NSGABLACK_RUNTIME_COST_WORKLOAD") == "iteration":
        from .plugins.step_cost import StepCostObserver
        case.solver.add_plugin(StepCostObserver())
    if "NSGABLACK_RUNTIME_PROFILE_DIR" in os.environ:
        start_profile = getattr(sys.modules.get("sitecustomize"), "start_profile", None)
        if not callable(start_profile):
            raise RuntimeError("runtime profiling requires sitecustomize.start_profile()")
        start_profile(case=case)
    return case
