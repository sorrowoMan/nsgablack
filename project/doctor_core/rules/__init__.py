"""Rule modules for project doctor."""

from .adapter_purity import check_adapter_layer_purity
from .broad_except import check_broad_exception_swallow
from .build_solver import check_build_solver
from .component_catalog import (
    check_component_catalog_registration,
    check_process_like_bias_usage,
    collect_bias_instances,
    collect_solver_components,
)
from .component_order import check_component_order_constraints
from .contract_source import check_contract_source
from .examples_suites import check_examples_suites_solver_control_writes
from .metrics_provider import check_metrics_provider_alignment
from .registry_checks import check_registry
from .runtime_surface import check_runtime_private_surface
from .runtime_governance import (
    check_no_plugin_evaluation_short_circuit,
    check_runtime_governance_runtime_state,
)
from .scaffold import check_structure, looks_like_scaffold_project
from .snapshot_context_policy import (
    check_context_store_policy,
    check_large_objects_in_context,
    check_snapshot_refs,
    check_snapshot_store_policy,
)

__all__ = [
    "check_adapter_layer_purity",
    "check_broad_exception_swallow",
    "check_build_solver",
    "check_component_catalog_registration",
    "check_component_order_constraints",
    "check_context_store_policy",
    "check_large_objects_in_context",
    "check_process_like_bias_usage",
    "check_contract_source",
    "check_examples_suites_solver_control_writes",
    "check_registry",
    "check_metrics_provider_alignment",
    "check_runtime_private_surface",
    "check_no_plugin_evaluation_short_circuit",
    "check_runtime_governance_runtime_state",
    "check_structure",
    "check_snapshot_refs",
    "check_snapshot_store_policy",
    "collect_bias_instances",
    "collect_solver_components",
    "looks_like_scaffold_project",
]
