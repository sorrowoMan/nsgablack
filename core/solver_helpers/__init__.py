"""Internal helper utilities for SolverBase implementation."""

from .snapshot_helpers import (
    build_snapshot_payload,
    build_snapshot_refs,
    snapshot_meta,
    strip_large_context_fields,
)
from .control_plane_helpers import (
    collect_runtime_context_projection,
    increment_evaluation_counter,
    get_best_snapshot_fields,
    set_best_snapshot_fields,
    set_generation_value,
    set_pareto_snapshot_fields,
)
from .store_helpers import (
    build_context_store_or_memory,
    build_snapshot_store_or_memory,
)
from .context_helpers import (
    build_solver_context,
    ensure_snapshot_readable,
    get_solver_context_view,
)
from .bias_helpers import apply_bias_module
from .evaluation_helpers import (
    evaluate_individual_with_plugins_and_bias,
    evaluate_population_with_plugins_and_bias,
)
from .run_helpers import apply_runtime_control_slot, run_solver_loop
from .result_helpers import format_run_result
from .candidate_helpers import sample_random_candidate
from .component_scheduler import ComponentDependencyScheduler, ComponentOrderError

__all__ = [
    "apply_bias_module",
    "build_context_store_or_memory",
    "build_solver_context",
    "build_snapshot_store_or_memory",
    "collect_runtime_context_projection",
    "ensure_snapshot_readable",
    "evaluate_individual_with_plugins_and_bias",
    "evaluate_population_with_plugins_and_bias",
    "get_solver_context_view",
    "build_snapshot_payload",
    "build_snapshot_refs",
    "increment_evaluation_counter",
    "apply_runtime_control_slot",
    "format_run_result",
    "run_solver_loop",
    "ComponentDependencyScheduler",
    "ComponentOrderError",
    "get_best_snapshot_fields",
    "sample_random_candidate",
    "set_best_snapshot_fields",
    "set_generation_value",
    "set_pareto_snapshot_fields",
    "snapshot_meta",
    "strip_large_context_fields",
]
