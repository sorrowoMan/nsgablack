"""Optional wiring helpers for plugin/parallel assembly."""

from .benchmark_harness import attach_benchmark_harness
from .module_report import attach_module_report
from .checkpoint_resume import attach_checkpoint_resume
from .ray_parallel import attach_ray_parallel
from .dynamic_switch import attach_dynamic_switch
from .default_plugins import (
    ObservabilityPreset,
    attach_default_observability_plugins,
    attach_observability_profile,
    resolve_observability_preset,
)


def set_plugin_strict(solver, strict: bool = True):
    """Set plugin manager strict failure policy in one place."""
    pm = getattr(solver, "plugin_manager", None)
    if pm is not None:
        try:
            pm.strict = bool(strict)
        except Exception:
            pass
    return solver


def set_parallel_thread_bias_isolation(solver, mode: str = "deepcopy"):
    """Set thread backend bias isolation policy in one place."""
    mode_text = str(mode or "").strip().lower()
    if mode_text not in {"deepcopy", "disable_cache", "off"}:
        raise ValueError("mode must be one of: deepcopy, disable_cache, off")

    if hasattr(solver, "_parallel_cfg") and isinstance(getattr(solver, "_parallel_cfg"), dict):
        try:
            solver._parallel_cfg["thread_bias_isolation"] = mode_text
        except Exception:
            pass

    try:
        setattr(solver, "parallel_thread_bias_isolation", mode_text)
    except Exception:
        pass

    evaluator = getattr(solver, "parallel_evaluator", None)
    if evaluator is not None and hasattr(evaluator, "thread_bias_isolation"):
        try:
            evaluator.thread_bias_isolation = mode_text
        except Exception:
            pass
    return solver

__all__ = [
    "attach_benchmark_harness",
    "attach_module_report",
    "attach_checkpoint_resume",
    "attach_ray_parallel",
    "attach_dynamic_switch",
    "attach_default_observability_plugins",
    "attach_observability_profile",
    "resolve_observability_preset",
    "ObservabilityPreset",
    "set_plugin_strict",
    "set_parallel_thread_bias_isolation",
]
