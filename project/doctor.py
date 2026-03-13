# -*- coding: utf-8 -*-
"""Project doctor checks for local scaffold projects."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable, List, Sequence

from .catalog import find_project_root, load_project_entries
from .doctor_core import (
    DoctorDiagnostic,
    DoctorReport,
    add_diagnostic,
    format_doctor_report_text,
    iter_diagnostics_by_level as _iter_diagnostics_by_level,
)
from .doctor_core.rules import (
    check_adapter_layer_purity as _check_adapter_layer_purity_rule,
    check_broad_exception_swallow as _check_broad_exception_swallow_rule,
    check_build_solver as _check_build_solver_rule,
    check_component_catalog_registration as _check_component_catalog_registration_rule,
    check_component_order_constraints as _check_component_order_constraints_rule,
    check_context_store_policy as _check_context_store_policy_rule,
    check_process_like_bias_usage as _check_process_like_bias_usage_rule,
    check_contract_source as _check_contract_source_rule,
    check_examples_suites_solver_control_writes as _check_examples_suites_solver_control_writes_rule,
    check_metrics_provider_alignment as _check_metrics_provider_alignment_rule,
    check_registry as _check_registry_rule,
    check_runtime_private_surface as _check_runtime_private_surface_rule,
    check_structure as _check_structure_rule,
    check_snapshot_refs as _check_snapshot_refs_rule,
    check_snapshot_store_policy as _check_snapshot_store_policy_rule,
    collect_bias_instances as _collect_bias_instances_rule,
    collect_solver_components as _collect_solver_components_rule,
    looks_like_scaffold_project as _looks_like_scaffold_project_rule,
)
from ..catalog import get_catalog
from ..utils.context.context_keys import (
    KEY_CONSTRAINT_VIOLATIONS,
    KEY_CONSTRAINT_VIOLATIONS_REF,
    KEY_DECISION_TRACE,
    KEY_DECISION_TRACE_REF,
    KEY_HISTORY,
    KEY_HISTORY_REF,
    KEY_OBJECTIVES,
    KEY_OBJECTIVES_REF,
    KEY_PARETO_OBJECTIVES,
    KEY_PARETO_OBJECTIVES_REF,
    KEY_PARETO_SOLUTIONS,
    KEY_PARETO_SOLUTIONS_REF,
    KEY_POPULATION,
    KEY_POPULATION_REF,
    KEY_SNAPSHOT_KEY,
)


_REQUIRED_DIRS = ("problem", "pipeline", "bias", "adapter", "plugins")
_REQUIRED_FILES = ("README.md", "build_solver.py", "project_registry.py")
_CORE_CONTRACT_KEYS = {"context_requires", "context_provides", "context_mutates", "context_cache"}
_USAGE_KEYS = {"use_when", "minimal_wiring", "required_companions", "config_keys", "example_entry"}
_CONTEXT_ENTRY_KEYS = {"context_requires", "context_provides", "context_mutates", "context_cache", "context_notes"}
_CONTRACT_CHECK_DIRS = ("pipeline", "representation", "bias", "adapter", "adapters", "plugins")
_STATE_RECOVERY_LEVELS = {"L0", "L1", "L2"}
_FORBIDDEN_SOLVER_MIRROR_ATTRS = {
    "shared_state",
    "shared_best_x",
    "shared_best_score",
    "shared_strategy_stats",
    "event_shared_state",
    "event_queue",
    "event_inflight",
    "event_archive",
    "event_history",
    "current_x",
    "current_score",
    "sa_temperature",
    "sa_accepted",
    "sta_sigma",
    "sta_best_x",
    "sta_best_score",
    "role_reports",
    "last_candidate_roles",
    "last_candidate_units",
    "last_unit_tasks",
}
_PLUGIN_STATE_FIELDS = {"population", "objectives", "constraint_violations"}
_SNAPSHOT_REF_KEYS = (
    KEY_POPULATION_REF,
    KEY_OBJECTIVES_REF,
    KEY_CONSTRAINT_VIOLATIONS_REF,
    KEY_PARETO_SOLUTIONS_REF,
    KEY_PARETO_OBJECTIVES_REF,
    KEY_HISTORY_REF,
    KEY_DECISION_TRACE_REF,
)
_SNAPSHOT_PAYLOAD_REF_MAP = (
    (KEY_POPULATION, KEY_POPULATION_REF),
    (KEY_OBJECTIVES, KEY_OBJECTIVES_REF),
    (KEY_CONSTRAINT_VIOLATIONS, KEY_CONSTRAINT_VIOLATIONS_REF),
    (KEY_PARETO_SOLUTIONS, KEY_PARETO_SOLUTIONS_REF),
    (KEY_PARETO_OBJECTIVES, KEY_PARETO_OBJECTIVES_REF),
    (KEY_HISTORY, KEY_HISTORY_REF),
    (KEY_DECISION_TRACE, KEY_DECISION_TRACE_REF),
)
_RUNTIME_STATE_FIELDS = {
    "population",
    "objectives",
    "constraint_violations",
    "best_x",
    "best_objective",
    "pareto_solutions",
    "pareto_objectives",
    "generation",
    "evaluation_count",
    "history",
}
_SOLVER_CONTROL_FIELDS = {
    "adapter",
    "bias_module",
    "enable_bias",
    "max_steps",
    "pop_size",
    "max_generations",
    "mutation_rate",
    "crossover_rate",
}
_SOLVER_LIKE_VAR_NAMES = {
    "solver",
    "base",
    "sol",
    "opt_solver",
    "optimizer",
    "engine",
}
_EXAMPLE_SUITE_CHECK_DIRS = ("examples", "utils/suites")
_RUNTIME_PRIVATE_SURFACE_PATTERNS = ("working_*.py", "build_solver.py")
_RUNTIME_PRIVATE_SURFACE_SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "node_modules",
    "site-packages",
}
_ALLOWED_METRICS_FALLBACK_VALUES = {
    "none",
    "safe_zero",
    "default",
    "problem_data",
    "warn",
    "ignore",
}
_PROCESS_LIKE_BIAS_MODULE_PREFIXES = {
    "nsgablack.bias.algorithmic.differential_evolution",
    "nsgablack.bias.algorithmic.gradient_descent",
    "nsgablack.bias.algorithmic.moead",
    "nsgablack.bias.algorithmic.nsga2",
    "nsgablack.bias.algorithmic.nsga3",
    "nsgablack.bias.algorithmic.pattern_search",
    "nsgablack.bias.algorithmic.simulated_annealing",
    "nsgablack.bias.algorithmic.spea2",
}
_MIN_REDIS_KEY_PREFIX_LEN = 8
_MIN_REDIS_TTL_SECONDS = 30.0
_SAFE_SNAPSHOT_SERIALIZER = "safe"


def _add(diags: List[DoctorDiagnostic], level: str, code: str, msg: str, path: Path | None = None) -> None:
    add_diagnostic(diags, level, code, msg, path)


def _check_broad_exception_swallow(root: Path, diags: List[DoctorDiagnostic], *, strict: bool) -> None:
    _check_broad_exception_swallow_rule(
        root=root,
        diags=diags,
        strict=bool(strict),
        add=_add,
        looks_like_scaffold_project=_looks_like_scaffold_project,
    )


def _looks_like_scaffold_project(root: Path) -> bool:
    return _looks_like_scaffold_project_rule(root)


def _check_structure(root: Path, diags: List[DoctorDiagnostic]) -> None:
    _check_structure_rule(
        root=root,
        diags=diags,
        add=_add,
        required_dirs=_REQUIRED_DIRS,
        required_files=_REQUIRED_FILES,
    )


def _check_registry(root: Path, diags: List[DoctorDiagnostic]) -> None:
    _check_registry_rule(
        root=root,
        diags=diags,
        add=_add,
        load_project_entries=load_project_entries,
        usage_keys=_USAGE_KEYS,
        context_entry_keys=_CONTEXT_ENTRY_KEYS,
    )


def _check_build_solver(root: Path, diags: List[DoctorDiagnostic], *, instantiate: bool, strict: bool) -> None:
    _check_build_solver_rule(
        root=root,
        diags=diags,
        instantiate=bool(instantiate),
        strict=bool(strict),
        add=_add,
        check_context_store_policy=_check_context_store_policy,
        check_snapshot_store_policy=_check_snapshot_store_policy,
        check_snapshot_refs=_check_snapshot_refs,
        check_component_catalog_registration=_check_component_catalog_registration,
        check_metrics_provider_alignment=_check_metrics_provider_alignment,
        check_process_like_bias_usage=_check_process_like_bias_usage,
    )


def _check_context_store_policy(
    *,
    root: Path,
    solver: object,
    build_file: Path,
    diags: List[DoctorDiagnostic],
    strict: bool,
) -> None:
    _check_context_store_policy_rule(
        root=root,
        solver=solver,
        build_file=build_file,
        diags=diags,
        strict=bool(strict),
        add=_add,
        min_redis_key_prefix_len=_MIN_REDIS_KEY_PREFIX_LEN,
        min_redis_ttl_seconds=_MIN_REDIS_TTL_SECONDS,
    )


def _check_snapshot_store_policy(
    *,
    root: Path,
    solver: object,
    build_file: Path,
    diags: List[DoctorDiagnostic],
    strict: bool,
) -> None:
    del root
    _check_snapshot_store_policy_rule(
        solver=solver,
        build_file=build_file,
        diags=diags,
        strict=bool(strict),
        add=_add,
        min_redis_key_prefix_len=_MIN_REDIS_KEY_PREFIX_LEN,
        min_redis_ttl_seconds=_MIN_REDIS_TTL_SECONDS,
        safe_snapshot_serializer=_SAFE_SNAPSHOT_SERIALIZER,
    )


def _check_snapshot_refs(
    *,
    solver: object,
    build_file: Path,
    diags: List[DoctorDiagnostic],
    strict: bool,
) -> None:
    _check_snapshot_refs_rule(
        solver=solver,
        build_file=build_file,
        diags=diags,
        strict=bool(strict),
        add=_add,
        key_snapshot_key=KEY_SNAPSHOT_KEY,
        snapshot_ref_keys=_SNAPSHOT_REF_KEYS,
        snapshot_payload_ref_map=_SNAPSHOT_PAYLOAD_REF_MAP,
        key_population=KEY_POPULATION,
        key_objectives=KEY_OBJECTIVES,
        key_constraint_violations=KEY_CONSTRAINT_VIOLATIONS,
    )


def _collect_solver_components(solver: object) -> List[tuple[str, object]]:
    return _collect_solver_components_rule(solver)


def _collect_bias_instances(solver: object) -> List[tuple[str, object]]:
    return _collect_bias_instances_rule(solver)


def _check_process_like_bias_usage(
    *,
    solver: object,
    build_file: Path,
    diags: List[DoctorDiagnostic],
    strict: bool,
) -> None:
    _check_process_like_bias_usage_rule(
        solver=solver,
        build_file=build_file,
        diags=diags,
        strict=bool(strict),
        add=_add,
        process_like_bias_module_prefixes=_PROCESS_LIKE_BIAS_MODULE_PREFIXES,
    )


def _check_component_catalog_registration(
    *,
    root: Path,
    solver: object,
    build_file: Path,
    diags: List[DoctorDiagnostic],
    strict: bool,
) -> None:
    _check_component_catalog_registration_rule(
        root=root,
        solver=solver,
        build_file=build_file,
        diags=diags,
        strict=bool(strict),
        add=_add,
        get_catalog_entries=lambda: get_catalog().list(),
        load_project_entries=load_project_entries,
    )


def _check_adapter_layer_purity(root: Path, diags: List[DoctorDiagnostic], strict: bool) -> None:
    _check_adapter_layer_purity_rule(
        root=root,
        diags=diags,
        strict=bool(strict),
        add=_add,
    )


def _check_metrics_provider_alignment(
    *,
    solver: object,
    build_file: Path,
    diags: List[DoctorDiagnostic],
    strict: bool,
    get_component_contract,
) -> None:
    _check_metrics_provider_alignment_rule(
        solver=solver,
        build_file=build_file,
        diags=diags,
        strict=bool(strict),
        add=_add,
        get_component_contract=get_component_contract,
        collect_solver_components=_collect_solver_components,
        allowed_metrics_fallback_values=tuple(sorted(_ALLOWED_METRICS_FALLBACK_VALUES)),
    )


def _check_contract_source(root: Path, diags: List[DoctorDiagnostic], *, strict: bool) -> None:
    _check_contract_source_rule(
        root=root,
        diags=diags,
        strict=bool(strict),
        add=_add,
        contract_check_dirs=_CONTRACT_CHECK_DIRS,
        core_contract_keys=_CORE_CONTRACT_KEYS,
        runtime_state_fields=_RUNTIME_STATE_FIELDS,
        plugin_state_fields=_PLUGIN_STATE_FIELDS,
        forbidden_solver_mirror_attrs=_FORBIDDEN_SOLVER_MIRROR_ATTRS,
        state_recovery_levels=_STATE_RECOVERY_LEVELS,
    )


def _check_examples_suites_solver_control_writes(
    root: Path,
    diags: List[DoctorDiagnostic],
    *,
    strict: bool,
) -> None:
    _check_examples_suites_solver_control_writes_rule(
        root=root,
        diags=diags,
        strict=bool(strict),
        add=_add,
        solver_control_fields=_SOLVER_CONTROL_FIELDS,
        solver_like_var_names=_SOLVER_LIKE_VAR_NAMES,
        example_suite_check_dirs=_EXAMPLE_SUITE_CHECK_DIRS,
    )


def _check_runtime_private_surface(root: Path, diags: List[DoctorDiagnostic], *, strict: bool) -> None:
    _check_runtime_private_surface_rule(
        root=root,
        diags=diags,
        strict=bool(strict),
        add=_add,
        file_patterns=_RUNTIME_PRIVATE_SURFACE_PATTERNS,
        include_utils=True,
        skip_dir_names=_RUNTIME_PRIVATE_SURFACE_SKIP_DIRS,
        skip_tests=True,
    )


def _check_component_order_constraints(root: Path, diags: List[DoctorDiagnostic], *, strict: bool) -> None:
    _check_component_order_constraints_rule(
        root=root,
        diags=diags,
        strict=bool(strict),
        add=_add,
    )


def run_project_doctor(
    path: Path | str | None = None,
    *,
    instantiate_solver: bool = False,
    strict: bool = False,
) -> DoctorReport:
    target = Path(path).resolve() if path else Path.cwd()
    root = find_project_root(target)
    if root is None:
        root = target

    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    diags: List[DoctorDiagnostic] = []
    _check_structure(root, diags)
    _check_registry(root, diags)
    _check_build_solver(root, diags, instantiate=instantiate_solver, strict=bool(strict))
    _check_contract_source(root, diags, strict=bool(strict))
    _check_component_order_constraints(root, diags, strict=bool(strict))
    _check_runtime_private_surface(root, diags, strict=bool(strict))
    _check_adapter_layer_purity(root, diags, strict=bool(strict))
    _check_examples_suites_solver_control_writes(root, diags, strict=bool(strict))
    _check_broad_exception_swallow(root, diags, strict=bool(strict))
    _add_common_misuse_hints(root, diags)
    return DoctorReport(project_root=root, diagnostics=tuple(diags))


def _add_common_misuse_hints(root: Path, diags: List[DoctorDiagnostic]) -> None:
    _add(
        diags,
        "info",
        "doctor-common-misuse-hints",
        (
            "Common misuse hints: do not read/write solver population/objectives/constraint_violations directly; "
            "use resolve_population_snapshot()/commit_population_snapshot()/solver.read_snapshot(). "
            "Keep large objects in SnapshotStore and only references in Context."
        ),
        root,
    )


def format_doctor_report(report: DoctorReport) -> str:
    return format_doctor_report_text(report)


def iter_diagnostics_by_level(
    diagnostics: Iterable[DoctorDiagnostic],
    level: str,
) -> List[DoctorDiagnostic]:
    return _iter_diagnostics_by_level(diagnostics, level)
