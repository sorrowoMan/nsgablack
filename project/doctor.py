# -*- coding: utf-8 -*-
"""Project doctor checks for local scaffold projects."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable, List, Sequence

from blackbase.project.doctor import run_common_project_doctor as _run_common_project_doctor
from blackbase.project.doctor import DoctorCheckCoverage
from blackbase.project.doctor_scope import IGNORED_SOURCE_DIRS, discover_doctor_roots

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
    check_large_objects_in_context,
    check_process_like_bias_usage as _check_process_like_bias_usage_rule,
    check_contract_source as _check_contract_source_rule,
    check_examples_suites_solver_control_writes as _check_examples_suites_solver_control_writes_rule,
    check_metrics_provider_alignment as _check_metrics_provider_alignment_rule,
    check_no_plugin_evaluation_short_circuit as _check_no_plugin_evaluation_short_circuit_rule,
    check_registry as _check_registry_rule,
    check_runtime_governance_runtime_state as _check_runtime_governance_runtime_state_rule,
    check_runtime_private_surface as _check_runtime_private_surface_rule,
    check_standard_case_scaffolds as _check_standard_case_scaffolds_rule,
    check_snapshot_refs as _check_snapshot_refs_rule,
    check_snapshot_store_policy as _check_snapshot_store_policy_rule,
    check_solver_step_outcomes as _check_solver_step_outcomes_rule,
    collect_bias_instances as _collect_bias_instances_rule,
    collect_solver_components as _collect_solver_components_rule,
    looks_like_scaffold_project as _looks_like_scaffold_project_rule,
)
from ..catalog import get_catalog
from ..catalog.audit import audit_catalog
from nsgablack.context_keys import (
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
} | IGNORED_SOURCE_DIRS
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


def _add(diags: List[DoctorDiagnostic], level: str, code: str, msg: str, path: Path | None = None, *, line=None, column=None) -> None:
    add_diagnostic(diags, level, code, msg, path, line=line, column=column)


def _check_broad_exception_swallow(root: Path, diags: List[DoctorDiagnostic], *, strict: bool) -> None:
    _check_broad_exception_swallow_rule(
        root=root,
        diags=diags,
        strict=bool(strict),
        add=_add,
    )


def _looks_like_scaffold_project(root: Path) -> bool:
    return _looks_like_scaffold_project_rule(root)


def _looks_like_framework_repository(root: Path) -> bool:
    """Return whether ``root`` is a framework repository, not a Case."""

    if not (root / "pyproject.toml").is_file():
        return False
    if not (root / "catalog" / "entries").is_dir():
        return False
    nsgablack_markers = (
        root / "core" / "blank_solver.py",
        root / "project" / "doctor.py",
    )
    mlblack_markers = (
        root / "core" / "problem.py",
        root / "integrations" / "nsgablack_control.py",
    )
    return all(path.exists() for path in nsgablack_markers) or all(
        path.exists() for path in mlblack_markers
    )


def _check_standard_case_scaffolds(root: Path, diags: List[DoctorDiagnostic]) -> None:
    _check_standard_case_scaffolds_rule(root=root, diags=diags, add=_add)


def _check_nsg_scaffold_guides(root: Path, diags: List[DoctorDiagnostic]) -> None:
    """Enforce one README as the only Case documentation entry."""

    if (root / "project_config.py").is_file() and (root / "cases").is_dir():
        for case_root in sorted((root / "cases").iterdir()):
            if case_root.is_dir() and (case_root / "build_solver.py").is_file():
                _check_nsg_scaffold_guides(case_root, diags)
        return
    if not _looks_like_scaffold_project(root):
        _add(
            diags,
            "info",
            "structure-skip",
            "Skip nsgablack scaffold guide checks (no formal Project/Case scaffold detected).",
            root,
        )
        return
    readme = root / "README.md"
    if not readme.is_file():
        _add(
            diags,
            "warn",
            "missing-case-readme",
            "Case documentation belongs in one README.md.",
            readme,
        )

    legacy_docs = (
        root / "START_HERE.md",
        root / "BUILD_SOLVER_REGISTRATION.md",
        root / "COMPONENT_REGISTRATION.md",
        root / "docs" / "contracts" / "COMPONENT_CONTRACT_TEMPLATE.md",
        root / "tests" / "templates" / "README.md",
    )
    for path in legacy_docs:
        if path.is_file():
            _add(
                diags,
                "warn",
                "legacy-case-doc",
                "Move useful content into the Case README and remove the duplicated legacy document.",
                path,
            )


def _check_registry(root: Path, diags: List[DoctorDiagnostic]) -> None:
    if (root / "project_config.py").is_file() and (root / "cases").is_dir():
        for case_root in sorted((root / "cases").iterdir()):
            if case_root.is_dir() and (case_root / "build_solver.py").is_file():
                _check_registry(case_root, diags)
        return
    if _looks_like_framework_repository(root):
        _add(
            diags,
            "info",
            "framework-registry-scope",
            "Framework repository Catalog is validated by catalog audit, not as a Case-local registry.",
            root / "catalog" / "entries",
        )
        return
    with project_import_context(root):
        _check_registry_rule(
            root=root,
            diags=diags,
            add=_add,
            load_project_entries=load_project_entries,
            usage_keys=_USAGE_KEYS,
            context_entry_keys=_CONTEXT_ENTRY_KEYS,
        )


def _check_build_solver(root: Path, diags: List[DoctorDiagnostic], *, instantiate: bool, strict: bool) -> None:
    if (root / "project_config.py").is_file() and (root / "cases").is_dir():
        for case_root in sorted((root / "cases").iterdir()):
            if not case_root.is_dir() or case_root.name == "__pycache__":
                continue
            if not (
                (case_root / ".case").is_file()
                or (case_root / "build_solver.py").is_file()
                or (case_root / "build_trainer.py").is_file()
            ):
                continue
            _check_build_solver(case_root, diags, instantiate=instantiate, strict=strict)
        return
    if not _looks_like_scaffold_project(root) and not (root / ".case").is_file():
        _add(
            diags,
            "info",
            "build-entry-skip",
            "Skip build entry checks because the inspected root is not a Case scaffold.",
            root,
        )
        return
    with project_import_context(root):
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
            check_runtime_governance_runtime_state=_check_runtime_governance_runtime_state,
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


def _check_solver_step_outcomes(
    root: Path,
    diags: List[DoctorDiagnostic],
    *,
    strict: bool,
) -> None:
    _check_solver_step_outcomes_rule(
        root=root,
        diags=diags,
        strict=bool(strict),
        add=_add,
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


def _check_runtime_governance_runtime_state(
    *,
    solver: object,
    build_file: Path,
    diags: List[DoctorDiagnostic],
    strict: bool,
) -> None:
    _check_runtime_governance_runtime_state_rule(
        solver=solver,
        build_file=build_file,
        diags=diags,
        strict=bool(strict),
        add=_add,
    )


def _check_component_order_constraints(root: Path, diags: List[DoctorDiagnostic], *, strict: bool) -> None:
    _check_component_order_constraints_rule(
        root=root,
        diags=diags,
        strict=bool(strict),
        add=_add,
    )


def _check_catalog_audit(diags: List[DoctorDiagnostic], *, profile: str) -> None:
    try:
        report = audit_catalog(profile=profile, runtime=False)
    except Exception as exc:
        _add(diags, "warn", "catalog-audit-failed", f"Catalog audit failed: {exc}")
        return
    _add(diags, "info", "catalog-audit-scope",
         f"Catalog profile={profile}; static audit. "
         f"Unchecked import={report.import_unchecked}, params={report.params_unchecked}; "
         "recipe signature checks do not prove component execution.")
    if report.import_failures or report.context_failures or report.method_failures or report.param_failures:
        msg = (
            "Catalog audit failures detected: "
            f"import={report.import_failures} context={report.context_failures} "
            f"methods={report.method_failures} params={report.param_failures}."
        )
        _add(diags, "warn", "catalog-audit-issues", msg)


from blackbase.context.key_registry import with_project_context_keys, context_key_scope, load_context_keys


@with_project_context_keys
def run_project_doctor(
    path: Path | str | None = None,
    *,
    instantiate_solver: bool = False,
    strict: bool = False,
    catalog_audit: bool = False,
    catalog_profile: str = "framework-core",
) -> DoctorReport:
    target = Path(path).resolve() if path else Path.cwd()
    root = find_project_root(target)
    if root is None:
        root = target

    diags: List[DoctorDiagnostic] = []
    common_report = _run_common_project_doctor(root, strict=bool(strict))
    diags.extend(common_report.diagnostics)
    coverage = list(common_report.coverage)
    _, cases = discover_doctor_roots(root)

    def checked(name, scope, action):
        start = len(diags)
        paths = (scope.parent.parent, scope) if scope.parent.name == "cases" else (scope,)
        try:
            with context_key_scope(load_context_keys(*paths)):
                action()
        except (ValueError, TypeError) as exc:
            if "context" not in str(exc).lower():
                raise
            _add(diags, "error", "context-registry-invalid", str(exc), scope)
        rows = diags[start:]
        skipped = rows and all(item.level == "info" and (item.code.endswith("-skip") or item.code == "framework-registry-scope") for item in rows)
        coverage.append(DoctorCheckCoverage(name, str(scope), "skipped" if skipped else "completed",
                                           "; ".join(item.message for item in rows) if skipped else ""))

    checked("optimization-scaffold-guidance", root, lambda: _check_standard_case_scaffolds(root, diags))
    for case in cases:
        checked("case-guidance", case, lambda: _check_nsg_scaffold_guides(case, diags))
        checked("case-registry", case, lambda: _check_registry(case, diags))
        checked("case-build" if instantiate_solver else "case-import", case,
                lambda: _check_build_solver(case, diags, instantiate=instantiate_solver, strict=bool(strict)))
        if not instantiate_solver:
            coverage.append(DoctorCheckCoverage("case-build", str(case), "skipped", "Enable --build to execute assembly and runtime checks"))
    if not cases:
        coverage.append(DoctorCheckCoverage("case-build", str(root), "skipped", "No Case discovered"))
    if _looks_like_framework_repository(root):
        checked("framework-registry", root, lambda: _check_registry(root, diags))
    for scope in dict.fromkeys((root, *cases)):
        checked("source-contracts", scope, lambda: _check_contract_source(scope, diags, strict=bool(strict)))
        checked("component-order", scope, lambda: _check_component_order_constraints(scope, diags, strict=bool(strict)))
        checked("evaluation-boundary", scope, lambda: _check_no_plugin_evaluation_short_circuit_rule(
            root=scope, diags=diags, strict=bool(strict), add=_add))
    for name, check in (
        ("solver-step", _check_solver_step_outcomes),
        ("private-runtime", _check_runtime_private_surface),
        ("adapter-purity", _check_adapter_layer_purity),
        ("example-control", _check_examples_suites_solver_control_writes),
        ("broad-exception", _check_broad_exception_swallow),
    ):
        checked(name, root, lambda: check(root, diags, strict=bool(strict)))
    checked("large-context-writes", root, lambda: check_large_objects_in_context(
        root=root, diags=diags, strict=bool(strict), add=_add))
    if bool(catalog_audit):
        checked("catalog-audit", root, lambda: _check_catalog_audit(diags, profile=catalog_profile))
    else:
        coverage.append(DoctorCheckCoverage("catalog-audit", str(root), "skipped", "Enable --catalog-audit; profile=" + catalog_profile))
    _add_common_misuse_hints(root, diags)
    return DoctorReport(project_root=root, diagnostics=tuple(dict.fromkeys(diags)), coverage=tuple(coverage))


def _add_common_misuse_hints(root: Path, diags: List[DoctorDiagnostic]) -> None:
    _add(
        diags,
        "info",
        "doctor-common-misuse-hints",
        (
            "Common misuse hints: do not read/write solver population/objectives/constraint_violations directly; "
            "use get_population_snapshot()/commit_population_snapshot()/solver.read_snapshot(). "
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

from blackbase.project.runtime import project_import_context
