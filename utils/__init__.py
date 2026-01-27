"""
Utilities namespace.

Design:
- Keep `import nsgablack.utils` cheap (no heavy imports, no optional deps).
- Provide "category entrypoints" (subpackages) for discoverability.
- Keep older flat imports working via lazy re-exports + DeprecationWarning.

Recommended:
- Use `python -m nsgablack catalog search <keyword>` to locate the canonical path.
"""

from __future__ import annotations

from importlib import import_module

__all__ = [
    # Category entrypoints (recommended)
    "analysis",
    "constraints",
    "context",
    "engineering",
    "parallel",
    "performance",
    "plugins",
    "runs",
    "runtime",
    "suites",
    "surrogate",
    "viz",
]


def __getattr__(name):
    if name in {
        "analysis",
        "constraints",
        "context",
        "engineering",
        "parallel",
        "performance",
        "plugins",
        "runs",
        "runtime",
        "suites",
        "surrogate",
        "viz",
    }:
        return import_module(f"{__name__}.{name}")

    legacy = {
        # parallel
        "ParallelEvaluator": ("nsgablack.utils.parallel", "ParallelEvaluator"),
        "BatchEvaluator": ("nsgablack.utils.parallel", "BatchEvaluator"),
        "create_batch_evaluator": ("nsgablack.utils.parallel", "create_batch_evaluator"),
        "with_parallel_evaluation": ("nsgablack.utils.parallel", "with_parallel_evaluation"),
        # engineering
        "ExperimentResult": ("nsgablack.utils.engineering.experiment", "ExperimentResult"),
        "load_config": ("nsgablack.utils.engineering.config_loader", "load_config"),
        "merge_dicts": ("nsgablack.utils.engineering.config_loader", "merge_dicts"),
        "apply_config": ("nsgablack.utils.engineering.config_loader", "apply_config"),
        "ConfigError": ("nsgablack.utils.engineering.config_loader", "ConfigError"),
        "configure_logging": ("nsgablack.utils.engineering.logging_config", "configure_logging"),
        "JsonFormatter": ("nsgablack.utils.engineering.logging_config", "JsonFormatter"),
        # constraints
        "evaluate_constraints_safe": ("nsgablack.utils.constraints.constraint_utils", "evaluate_constraints_safe"),
        "evaluate_constraints_batch_safe": ("nsgablack.utils.constraints.constraint_utils", "evaluate_constraints_batch_safe"),
        # analysis
        "pareto_filter": ("nsgablack.utils.analysis.metrics", "pareto_filter"),
        "hypervolume_2d": ("nsgablack.utils.analysis.metrics", "hypervolume_2d"),
        "igd": ("nsgablack.utils.analysis.metrics", "igd"),
        "reference_front_zdt1": ("nsgablack.utils.analysis.metrics", "reference_front_zdt1"),
        "reference_front_zdt3": ("nsgablack.utils.analysis.metrics", "reference_front_zdt3"),
        "reference_front_dtlz2": ("nsgablack.utils.analysis.metrics", "reference_front_dtlz2"),
        # performance
        "fast_is_dominated": ("nsgablack.utils.performance.numba_helpers", "fast_is_dominated"),
        "NUMBA_AVAILABLE": ("nsgablack.utils.performance.numba_helpers", "NUMBA_AVAILABLE"),
        "njit": ("nsgablack.utils.performance.numba_helpers", "njit"),
        # headless
        "CallableSingleObjectiveProblem": ("nsgablack.utils.runs.headless", "CallableSingleObjectiveProblem"),
        "run_headless_single_objective": ("nsgablack.utils.runs.headless", "run_headless_single_objective"),
        # optional visualization
        "SolverVisualizationMixin": ("nsgablack.utils.viz", "SolverVisualizationMixin"),
    }
    if name in legacy:
        import warnings

        mod, sym = legacy[name]
        warnings.warn(
            f"nsgablack.utils.{name} is a legacy flat import; "
            f"prefer importing from `{mod}:{sym}` or a category entrypoint (e.g. nsgablack.utils.engineering).",
            DeprecationWarning,
            stacklevel=2,
        )
        m = import_module(mod)
        return getattr(m, sym)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
