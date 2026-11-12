"""Canonical factory; all supply semantics remain in the original Case."""

from pathlib import Path
import os
import sys
from blackbase.project import build_case, load_case_builder


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    if config:
        raise ValueError("runtime probe configuration belongs to Project component_overrides")
    source_project = Path(__file__).resolve().parents[3] / "supply_adjustment_nested"
    case = build_case(load_case_builder(source_project, "supply_adjustment_nested"),
                      resource_context=resource_context, component_overrides=component_overrides)
    if "NSGABLACK_RUNTIME_PROFILE_DIR" in os.environ:
        start_profile = getattr(sys.modules.get("sitecustomize"), "start_profile", None)
        if not callable(start_profile):
            raise RuntimeError("runtime profiling requires sitecustomize.start_profile()")
        start_profile()
    return case
