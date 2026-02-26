# -*- coding: utf-8 -*-
"""Project doctor checks for local scaffold projects."""

from __future__ import annotations

import ast
import importlib
import importlib.util
import inspect
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence

from .catalog import find_project_root, load_project_entries
from ..catalog import get_catalog


@dataclass(frozen=True)
class DoctorDiagnostic:
    level: str  # info / warn / error
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class DoctorReport:
    project_root: Path
    diagnostics: Sequence[DoctorDiagnostic]

    @property
    def error_count(self) -> int:
        return sum(1 for d in self.diagnostics if d.level == "error")

    @property
    def warn_count(self) -> int:
        return sum(1 for d in self.diagnostics if d.level == "warn")

    @property
    def info_count(self) -> int:
        return sum(1 for d in self.diagnostics if d.level == "info")


_REQUIRED_DIRS = ("problem", "pipeline", "bias", "adapter", "plugins")
_REQUIRED_FILES = ("README.md", "build_solver.py", "project_registry.py")
_CONTRACT_KEYS = {
    "context_requires",
    "context_provides",
    "context_mutates",
    "context_cache",
    "context_notes",
    "requires_context_keys",
    "provides_context_keys",
    "mutates_context_keys",
    "cache_context_keys",
    "runtime_requires",
    "runtime_provides",
    "runtime_mutates",
    "runtime_cache",
}
_USAGE_KEYS = {"use_when", "minimal_wiring", "required_companions", "config_keys", "example_entry"}
_CONTEXT_ENTRY_KEYS = {"context_requires", "context_provides", "context_mutates", "context_cache", "context_notes"}
_CONTRACT_CHECK_DIRS = ("pipeline", "bias", "adapter", "plugins")
_COMPONENT_NAME_SUFFIXES = (
    "Adapter",
    "Plugin",
    "Bias",
    "Mutator",
    "Mutation",
    "Repair",
    "Initializer",
    "Codec",
    "Pipeline",
)
_COMPONENT_BASE_NAMES = {
    "AlgorithmAdapter",
    "Plugin",
    "BaseBias",
    "BiasModule",
    "RepresentationPipeline",
}
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


def _add(diags: List[DoctorDiagnostic], level: str, code: str, msg: str, path: Path | None = None) -> None:
    diags.append(
        DoctorDiagnostic(
            level=level,
            code=code,
            message=msg,
            path=str(path) if path is not None else None,
        )
    )


def _load_module_from_file(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot import module from file: {file_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[call-arg]
    return module


def _resolve_import_path(import_path: str):
    module_path, sep, attr_path = str(import_path).partition(":")
    if not module_path or not sep or not attr_path:
        raise ValueError(f"Invalid import_path: {import_path!r} (expected 'module:attr')")
    module = importlib.import_module(module_path)
    obj = module
    for part in attr_path.split("."):
        obj = getattr(obj, part)
    return obj


def _looks_like_scaffold_project(root: Path) -> bool:
    return (root / "project_registry.py").is_file() or (root / "build_solver.py").is_file()


def _check_structure(root: Path, diags: List[DoctorDiagnostic]) -> None:
    if not _looks_like_scaffold_project(root):
        _add(
            diags,
            "info",
            "structure-skip",
            "Skip scaffold hard-checks (no project_registry.py/build_solver.py detected).",
            root,
        )
        return

    for name in _REQUIRED_DIRS:
        folder = root / name
        if not folder.is_dir():
            _add(diags, "error", "missing-dir", f"Missing required directory: {name}", folder)
        elif not (folder / "README.md").is_file():
            _add(diags, "warn", "missing-folder-readme", f"Recommended: add {name}/README.md", folder / "README.md")

    for name in _REQUIRED_FILES:
        file_path = root / name
        if not file_path.is_file():
            _add(diags, "error", "missing-file", f"Missing required file: {name}", file_path)

    if not (root / "START_HERE.md").is_file():
        _add(diags, "warn", "missing-start-here", "Recommended: add START_HERE.md onboarding file", root / "START_HERE.md")
    if not (root / "COMPONENT_REGISTRATION.md").is_file():
        _add(
            diags,
            "warn",
            "missing-component-registration-guide",
            "Recommended: add COMPONENT_REGISTRATION.md to explain what/why/how of local Catalog registration",
            root / "COMPONENT_REGISTRATION.md",
        )


def _check_registry(root: Path, diags: List[DoctorDiagnostic]) -> None:
    registry_file = root / "project_registry.py"
    if not registry_file.is_file():
        _add(diags, "info", "registry-skip", "Skip registry checks (project_registry.py not found).", registry_file)
        return
    try:
        entries = list(load_project_entries(root))
    except Exception as exc:
        _add(diags, "error", "registry-load-failed", f"Failed to load project_registry.py: {exc}", registry_file)
        return

    if not entries:
        _add(diags, "warn", "registry-empty", "project_registry.py returned no entries", registry_file)
        return

    keys = [e.key for e in entries]
    duplicated = sorted({k for k in keys if keys.count(k) > 1})
    if duplicated:
        _add(diags, "error", "registry-duplicate-key", f"Duplicated Catalog key(s): {', '.join(duplicated)}", registry_file)

    for entry in entries:
        missing_usage: List[str] = []
        for field in sorted(_USAGE_KEYS):
            value = getattr(entry, field, None)
            if field == "example_entry":
                if not str(value or "").strip():
                    missing_usage.append(field)
            elif field in {"required_companions", "config_keys"}:
                # Empty tuple/list is valid: component may have no mandatory companions/config knobs.
                if value is None:
                    missing_usage.append(field)
            elif not value:
                missing_usage.append(field)
        if missing_usage:
            _add(
                diags,
                "error",
                "registry-usage-missing",
                f"[{entry.key}] missing usage fields: {', '.join(missing_usage)}",
                registry_file,
            )

        missing_context: List[str] = []
        for field in sorted(_CONTEXT_ENTRY_KEYS):
            value = getattr(entry, field, None)
            if field == "context_notes":
                if not str(value or "").strip():
                    missing_context.append(field)
                continue
            if value is None:
                missing_context.append(field)
        if missing_context:
            _add(
                diags,
                "error",
                "registry-context-missing",
                f"[{entry.key}] missing context fields: {', '.join(missing_context)}",
                registry_file,
            )

        try:
            _resolve_import_path(entry.import_path)
        except Exception as exc:
            _add(
                diags,
                "error",
                "registry-import-failed",
                f"[{entry.key}] import_path cannot be resolved: {entry.import_path} ({exc})",
                registry_file,
            )

    _add(diags, "info", "registry-count", f"Catalog entries: {len(entries)}", registry_file)


def _check_build_solver(root: Path, diags: List[DoctorDiagnostic], *, instantiate: bool, strict: bool) -> None:
    build_file = root / "build_solver.py"
    if not build_file.is_file():
        return

    try:
        module = _load_module_from_file("nsgablack_project_build_solver", build_file)
    except Exception as exc:
        _add(diags, "error", "build-solver-import-failed", f"Cannot import build_solver.py: {exc}", build_file)
        return

    build_fn = getattr(module, "build_solver", None)
    if not callable(build_fn):
        _add(diags, "error", "build-solver-missing", "build_solver.py has no callable build_solver()", build_file)
        return

    _add(diags, "info", "build-solver-found", "Detected build_solver()", build_file)

    if not instantiate:
        return

    try:
        sig = inspect.signature(build_fn)
        if len(sig.parameters) == 0:
            solver = build_fn()
        else:
            solver = build_fn([])
    except Exception as exc:
        _add(diags, "error", "build-solver-instantiate-failed", f"build_solver() failed: {exc}", build_file)
        return

    if solver is None:
        _add(diags, "error", "build-solver-none", "build_solver() returned None", build_file)
        return

    _add(diags, "info", "build-solver-instantiated", f"build_solver() returned: {solver.__class__.__name__}", build_file)
    _check_context_store_policy(
        root=root,
        solver=solver,
        build_file=build_file,
        diags=diags,
        strict=bool(strict),
    )
    _check_component_catalog_registration(
        root=root,
        solver=solver,
        build_file=build_file,
        diags=diags,
        strict=bool(strict),
    )

    try:
        from ..utils.context.context_contracts import (
            collect_solver_contracts,
            detect_context_conflicts,
            get_component_contract,
        )

        contracts = collect_solver_contracts(solver)
    except Exception as exc:
        _add(diags, "warn", "contracts-collect-failed", f"Cannot collect context contracts: {exc}", build_file)
        return

    if not contracts:
        _add(diags, "warn", "contracts-empty", "No context contracts were collected", build_file)
        return

    empty_contract_names: List[str] = []
    for name, contract in contracts:
        if not any([contract.requires, contract.provides, contract.mutates, contract.cache, contract.notes]):
            empty_contract_names.append(name)

    if empty_contract_names:
        preview = ", ".join(empty_contract_names[:6])
        suffix = "..." if len(empty_contract_names) > 6 else ""
        _add(
            diags,
            "error" if strict else "warn",
            "contracts-not-explicit",
            f"Components without explicit context fields: {preview}{suffix}",
            build_file,
        )
    else:
        _add(diags, "info", "contracts-ok", "Collected explicit context contract fields", build_file)

    try:
        conflicts = detect_context_conflicts(contracts)
    except Exception as exc:
        _add(diags, "warn", "contracts-conflict-check-failed", f"Conflict check failed: {exc}", build_file)
        return
    if conflicts:
        preview = "; ".join(conflicts[:3])
        suffix = " ..." if len(conflicts) > 3 else ""
        _add(
            diags,
            "warn",
            "contracts-conflict-risk",
            f"Potential multi-writer context keys: {preview}{suffix}",
            build_file,
        )

    try:
        _check_metrics_provider_alignment(
            solver=solver,
            build_file=build_file,
            diags=diags,
            strict=bool(strict),
            get_component_contract=get_component_contract,
        )
    except Exception as exc:
        _add(diags, "warn", "metrics-provider-check-failed", f"Metrics provider check failed: {exc}", build_file)

    try:
        _check_process_like_bias_usage(
            solver=solver,
            build_file=build_file,
            diags=diags,
            strict=bool(strict),
        )
    except Exception as exc:
        _add(diags, "warn", "algorithm-as-bias-check-failed", f"Process-level bias check failed: {exc}", build_file)


def _normalize_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _check_context_store_policy(
    *,
    root: Path,
    solver: object,
    build_file: Path,
    diags: List[DoctorDiagnostic],
    strict: bool,
) -> None:
    backend = str(getattr(solver, "context_store_backend", "") or "").strip().lower()
    if not backend:
        runtime = getattr(solver, "runtime", None)
        store = getattr(runtime, "context_store", None)
        if store is not None:
            cls_name = store.__class__.__name__.lower()
            backend = "redis" if "redis" in cls_name else "memory"
    if backend != "redis":
        return

    level = "error" if strict else "warn"

    key_prefix = str(getattr(solver, "context_store_key_prefix", "") or "").strip()
    if not key_prefix:
        _add(
            diags,
            level,
            "redis-key-prefix-missing",
            "Redis context backend requires non-empty context_store_key_prefix.",
            build_file,
        )
    else:
        if len(key_prefix) < _MIN_REDIS_KEY_PREFIX_LEN:
            _add(
                diags,
                level,
                "redis-key-prefix-too-short",
                (
                    f"context_store_key_prefix is too short ({len(key_prefix)}); "
                    f"recommended >= {_MIN_REDIS_KEY_PREFIX_LEN} chars."
                ),
                build_file,
            )
        root_token = _normalize_token(root.name)
        prefix_token = _normalize_token(key_prefix)
        if root_token and root_token not in prefix_token:
            _add(
                diags,
                level,
                "redis-key-prefix-missing-project-name",
                (
                    "context_store_key_prefix should contain project name token "
                    f"('{root.name}') to avoid cross-project key pollution."
                ),
                build_file,
            )

    ttl = getattr(solver, "context_store_ttl_seconds", None)
    if ttl is None:
        _add(
            diags,
            "warn",
            "redis-ttl-policy-implicit",
            (
                "Redis TTL policy is implicit (context_store_ttl_seconds=None). "
                "Set an explicit value (seconds) or 0 for no-expire strategy."
            ),
            build_file,
        )
        return
    try:
        ttl_value = float(ttl)
    except Exception:
        _add(
            diags,
            level,
            "redis-ttl-invalid",
            f"context_store_ttl_seconds must be numeric or None; got: {ttl!r}",
            build_file,
        )
        return
    if 0.0 < ttl_value < _MIN_REDIS_TTL_SECONDS:
        _add(
            diags,
            "warn",
            "redis-ttl-too-small",
            (
                f"context_store_ttl_seconds={ttl_value:g}s may expire keys too early; "
                f"recommended >= {_MIN_REDIS_TTL_SECONDS:g}s."
            ),
            build_file,
        )


def _collect_solver_components(solver: object) -> List[tuple[str, object]]:
    out: List[tuple[str, object]] = []
    seen: set[tuple[str, int]] = set()

    def _add(name: str, obj: object | None) -> None:
        if obj is None:
            return
        marker = (str(name), id(obj))
        if marker in seen:
            return
        seen.add(marker)
        out.append((str(name), obj))

    _add("representation_pipeline", getattr(solver, "representation_pipeline", None))
    _add("bias_module", getattr(solver, "bias_module", None))

    adapter = getattr(solver, "adapter", None)
    _add("adapter", adapter)
    if adapter is not None:
        for idx, spec in enumerate(getattr(adapter, "strategies", ()) or ()):
            sub = getattr(spec, "adapter", None)
            name = str(getattr(spec, "name", f"strategy_{idx}"))
            _add(f"adapter.strategy.{name}", sub)
        for idx, role in enumerate(getattr(adapter, "roles", ()) or ()):
            role_name = str(getattr(role, "name", f"role_{idx}"))
            role_adapter = getattr(role, "adapter", None)
            _add(f"adapter.role.{role_name}", role_adapter if not callable(role_adapter) else None)
        for unit in getattr(adapter, "units", ()) or ():
            role_name = str(getattr(unit, "role", "role"))
            unit_id = int(getattr(unit, "unit_id", 0))
            _add(f"adapter.unit.{role_name}#{unit_id}", getattr(unit, "adapter", None))

    plugin_manager = getattr(solver, "plugin_manager", None)
    if plugin_manager is not None:
        plugins = getattr(plugin_manager, "plugins", None) or []
        for plugin in plugins:
            name = getattr(plugin, "name", plugin.__class__.__name__)
            _add(f"plugin.{name}", plugin)
    return out


def _collect_bias_instances(solver: object) -> List[tuple[str, object]]:
    out: List[tuple[str, object]] = []
    seen: set[int] = set()

    bias_module = getattr(solver, "bias_module", None)
    if bias_module is None:
        return out

    manager = getattr(bias_module, "_manager", None)
    if manager is None:
        return out

    for mgr_name in ("algorithmic_manager", "domain_manager"):
        sub_manager = getattr(manager, mgr_name, None)
        biases = getattr(sub_manager, "biases", None)
        if not isinstance(biases, dict):
            continue
        for key, bias in biases.items():
            if bias is None:
                continue
            marker = id(bias)
            if marker in seen:
                continue
            seen.add(marker)
            out.append((f"bias.{mgr_name}.{key}", bias))
    return out


def _check_process_like_bias_usage(
    *,
    solver: object,
    build_file: Path,
    diags: List[DoctorDiagnostic],
    strict: bool,
) -> None:
    hits: List[str] = []
    for bias_name, bias_obj in _collect_bias_instances(solver):
        cls_name = bias_obj.__class__.__name__
        cls_module = str(getattr(bias_obj.__class__, "__module__", ""))
        if not any(cls_module.startswith(prefix) for prefix in _PROCESS_LIKE_BIAS_MODULE_PREFIXES):
            continue
        hits.append(f"{bias_name}({cls_module}:{cls_name})")

    if not hits:
        return

    preview = ", ".join(hits[:8])
    suffix = " ..." if len(hits) > 8 else ""
    _add(
        diags,
        "error" if strict else "warn",
        "algorithm-as-bias",
        (
            "Process-level algorithm classes are attached as bias; move them to adapter/strategy layer: "
            f"{preview}{suffix}"
        ),
        build_file,
    )


def _component_import_path(obj: object) -> str:
    cls = getattr(obj, "__class__", None)
    if cls is None:
        return ""
    module = str(getattr(cls, "__module__", "") or "").strip()
    name = str(getattr(cls, "__name__", "") or "").strip()
    if not module or not name:
        return ""
    return f"{module}:{name}"


def _check_component_catalog_registration(
    *,
    root: Path,
    solver: object,
    build_file: Path,
    diags: List[DoctorDiagnostic],
    strict: bool,
) -> None:
    try:
        framework_entries = list(get_catalog().list())
    except Exception as exc:
        _add(diags, "warn", "catalog-check-failed", f"Global catalog load failed: {exc}", build_file)
        return

    framework_paths = {str(getattr(e, "import_path", "") or "") for e in framework_entries}
    local_paths: set[str] = set()
    try:
        # Keep loading to ensure project registry itself is healthy when present.
        local_entries = list(load_project_entries(root))
        local_paths = {str(getattr(e, "import_path", "") or "") for e in local_entries}
    except Exception:
        # Project registry may be intentionally absent outside scaffold projects.
        local_paths = set()

    missing_framework: List[str] = []
    unregistered_project: List[str] = []
    for comp_name, comp_obj in _collect_solver_components(solver) + _collect_bias_instances(solver):
        import_path = _component_import_path(comp_obj)
        if not import_path:
            continue
        if import_path.startswith("nsgablack."):
            if import_path not in framework_paths:
                missing_framework.append(f"{comp_name} -> {import_path}")
        else:
            if import_path not in local_paths:
                unregistered_project.append(f"{comp_name} -> {import_path}")

    if missing_framework:
        _add(
            diags,
            "error" if strict else "warn",
            "framework-component-not-in-catalog",
            (
                "Framework components used by build_solver are missing in global catalog: "
                + ", ".join(missing_framework[:10])
                + (" ..." if len(missing_framework) > 10 else "")
            ),
            build_file,
        )
    if unregistered_project:
        _add(
            diags,
            "info",
            "project-component-unregistered",
            (
                "Detected project components not registered in project catalog: "
                + ", ".join(unregistered_project[:10])
                + (" ..." if len(unregistered_project) > 10 else "")
            ),
            build_file,
        )


def _check_adapter_layer_purity(root: Path, diags: List[DoctorDiagnostic], strict: bool) -> None:
    adapter_roots = [root / "adapter", root / "core" / "adapters"]
    hits: List[str] = []

    for adapter_root in adapter_roots:
        if not adapter_root.is_dir():
            continue
        for py_file in adapter_root.rglob("*.py"):
            if py_file.name.startswith("__"):
                continue
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                continue

            imported_algorithmic_bias = False
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    module = str(node.module or "")
                    if "bias.core.base" in module:
                        for alias in node.names:
                            if alias.name == "AlgorithmicBias":
                                imported_algorithmic_bias = True
                                break
                if imported_algorithmic_bias:
                    break

            for node in tree.body:
                if not isinstance(node, ast.ClassDef):
                    continue
                if node.name.endswith("Bias"):
                    hits.append(f"{py_file}:{node.name}")
                    continue
                if imported_algorithmic_bias:
                    for base in node.bases:
                        base_text = ast.unparse(base)
                        if "AlgorithmicBias" in base_text:
                            hits.append(f"{py_file}:{node.name}")
                            break

    if not hits:
        return

    preview = ", ".join(hits[:6])
    suffix = " ..." if len(hits) > 6 else ""
    _add(
        diags,
        "error" if strict else "warn",
        "adapter-layer-purity",
        f"Adapter layer contains bias-like classes; use AlgorithmAdapter propose/update pattern: {preview}{suffix}",
        root,
    )


def _iter_metric_requires(name: str, obj: object, contract: object | None) -> List[str]:
    requires: List[str] = []

    if contract is not None:
        for key in getattr(contract, "requires", ()) or ():
            text = str(key).strip()
            if text.startswith("metrics.") and len(text) > len("metrics."):
                requires.append(text.split(".", 1)[1])

    raw = getattr(obj, "requires_metrics", ()) or ()
    if isinstance(raw, str):
        raw = (raw,)
    for key in raw:
        text = str(key).strip()
        if not text:
            continue
        if text.startswith("metrics."):
            text = text.split(".", 1)[1]
        if text:
            requires.append(text)

    return sorted(set(requires))


def _read_metrics_fallback_value(obj: object) -> str | None:
    if not hasattr(obj, "metrics_fallback"):
        return None
    value = getattr(obj, "metrics_fallback", None)
    if value is None:
        return None
    text = str(value).strip().lower()
    return text or None


def _is_valid_metrics_fallback_value(value: str) -> bool:
    return str(value).strip().lower() in _ALLOWED_METRICS_FALLBACK_VALUES


def _has_metrics_fallback(obj: object, _contract: object | None) -> bool:
    # Fallback must be explicit in component config/contract policy.
    # Avoid notes/description keyword heuristics.
    policy = str(getattr(obj, "missing_metrics_policy", "") or "").strip().lower()
    if policy in {"warn", "ignore", "none", "off"}:
        return True
    fallback = _read_metrics_fallback_value(obj) or ""
    return fallback in {"safe_zero", "problem_data", "default", "warn", "ignore"}


def _check_metrics_provider_alignment(
    *,
    solver: object,
    build_file: Path,
    diags: List[DoctorDiagnostic],
    strict: bool,
    get_component_contract,
) -> None:
    providers_by_metric: dict[str, set[str]] = {}
    wildcard_metrics_providers: set[str] = set()
    consumers: List[tuple[str, str, bool]] = []
    checked_fallback_obj_ids: set[int] = set()

    components = _collect_solver_components(solver)
    for comp_name, comp_obj in components:
        marker_id = id(comp_obj)
        if marker_id not in checked_fallback_obj_ids:
            checked_fallback_obj_ids.add(marker_id)
            fallback = _read_metrics_fallback_value(comp_obj)
            if fallback is not None and not _is_valid_metrics_fallback_value(fallback):
                allowed = ", ".join(sorted(_ALLOWED_METRICS_FALLBACK_VALUES))
                _add(
                    diags,
                    "error" if strict else "warn",
                    "metrics-fallback-invalid",
                    f"{comp_name} has invalid metrics_fallback='{fallback}' (allowed: {allowed})",
                    build_file,
                )
        contract = get_component_contract(comp_obj)
        if contract is None:
            continue

        for key in list(getattr(contract, "provides", ()) or ()) + list(getattr(contract, "mutates", ()) or ()):
            text = str(key).strip()
            if text == "metrics":
                wildcard_metrics_providers.add(comp_name)
                continue
            if text.startswith("metrics.") and len(text) > len("metrics."):
                metric_name = text.split(".", 1)[1].strip()
                if not metric_name:
                    continue
                providers_by_metric.setdefault(metric_name, set()).add(comp_name)

        for metric_name in _iter_metric_requires(comp_name, comp_obj, contract):
            consumers.append((comp_name, metric_name, _has_metrics_fallback(comp_obj, contract)))

    missing: List[str] = []
    for comp_name, metric_name, has_fallback in consumers:
        if providers_by_metric.get(metric_name):
            continue
        if wildcard_metrics_providers:
            continue
        if has_fallback:
            continue
        missing.append(f"{comp_name} -> metrics.{metric_name}")

    if not missing:
        return

    preview = "; ".join(sorted(missing)[:8])
    suffix = " ..." if len(missing) > 8 else ""
    _add(
        diags,
        "error" if strict else "warn",
        "metrics-provider-missing",
        "requires_metrics has no provider/fallback in current assembly: " + preview + suffix,
        build_file,
    )


def _class_has_contract(class_node: ast.ClassDef) -> bool:
    for node in class_node.body:
        if isinstance(node, ast.FunctionDef) and node.name == "get_context_contract":
            return True
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in _CONTRACT_KEYS:
                    return True
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id in _CONTRACT_KEYS:
            return True
    return False


def _iter_class_attr_values(class_node: ast.ClassDef, attr_name: str) -> List[ast.expr]:
    out: List[ast.expr] = []
    for node in class_node.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == attr_name:
                    out.append(node.value)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == attr_name and node.value is not None:
                out.append(node.value)
    return out


def _literal_str_value(node: ast.expr) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return str(node.value)
    return None


def _check_class_metrics_fallback_literal(
    class_node: ast.ClassDef,
    path: Path,
    diags: List[DoctorDiagnostic],
    *,
    strict: bool,
) -> None:
    values = _iter_class_attr_values(class_node, "metrics_fallback")
    if not values:
        return

    for value_node in values:
        literal = _literal_str_value(value_node)
        if literal is None:
            _add(
                diags,
                "error" if strict else "warn",
                "metrics-fallback-nonliteral",
                f"Class {class_node.name} metrics_fallback must be a string literal enum value",
                path,
            )
            continue

        normalized = literal.strip().lower()
        if not _is_valid_metrics_fallback_value(normalized):
            allowed = ", ".join(sorted(_ALLOWED_METRICS_FALLBACK_VALUES))
            _add(
                diags,
                "error" if strict else "warn",
                "metrics-fallback-invalid",
                f"Class {class_node.name} has invalid metrics_fallback='{literal}' (allowed: {allowed})",
                path,
            )


def _base_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return str(node.id)
    if isinstance(node, ast.Attribute):
        return str(node.attr)
    return ""


def _is_component_class(class_node: ast.ClassDef) -> bool:
    if class_node.name.startswith("_"):
        return False
    if class_node.name.endswith(_COMPONENT_NAME_SUFFIXES):
        return True
    for base in class_node.bases:
        base_name = _base_name(base)
        if not base_name:
            continue
        if base_name in _COMPONENT_BASE_NAMES or base_name.endswith(_COMPONENT_NAME_SUFFIXES):
            return True
    return False


def _is_not_implemented_raise(node: ast.AST) -> bool:
    if not isinstance(node, ast.Raise):
        return False
    exc = node.exc
    if isinstance(exc, ast.Name):
        return exc.id == "NotImplementedError"
    if isinstance(exc, ast.Call):
        func = exc.func
        if isinstance(func, ast.Name):
            return func.id == "NotImplementedError"
        if isinstance(func, ast.Attribute):
            return str(func.attr) == "NotImplementedError"
    if isinstance(exc, ast.Attribute):
        return str(exc.attr) == "NotImplementedError"
    return False


def _check_class_template_not_implemented(
    class_node: ast.ClassDef,
    path: Path,
    diags: List[DoctorDiagnostic],
    *,
    strict: bool,
) -> None:
    hits: List[str] = []
    for stmt in class_node.body:
        if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for n in ast.walk(stmt):
            if _is_not_implemented_raise(n):
                line = int(getattr(n, "lineno", getattr(stmt, "lineno", 0)) or 0)
                hits.append(f"{stmt.name}@L{line}")
                break
    if not hits:
        return
    _add(
        diags,
        "error" if strict else "warn",
        "template-not-implemented",
        f"Class {class_node.name} has NotImplementedError placeholders (模板未完成): "
        + ", ".join(hits[:8])
        + (" ..." if len(hits) > 8 else ""),
        path,
    )


def _check_contract_source(root: Path, diags: List[DoctorDiagnostic], *, strict: bool) -> None:
    for folder_name in _CONTRACT_CHECK_DIRS:
        folder = root / folder_name
        if not folder.is_dir():
            continue
        py_files = [p for p in folder.rglob("*.py") if p.name != "__init__.py"]
        for py_file in py_files:
            try:
                content = py_file.read_text(encoding="utf-8-sig")
                tree = ast.parse(content, filename=str(py_file))
            except Exception as exc:
                _add(diags, "warn", "source-parse-failed", f"Cannot parse source file: {exc}", py_file)
                continue
            _check_forbidden_solver_mirror_writes(tree, py_file, diags, strict=bool(strict))
            _check_runtime_bypass_writes(tree, py_file, diags, strict=bool(strict))
            if strict and folder_name == "plugins" and py_file.name != "base.py":
                _check_plugin_solver_state_access(tree, py_file, diags)

            class_nodes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
            if not class_nodes:
                continue

            for class_node in class_nodes:
                if not _is_component_class(class_node):
                    continue
                _check_class_metrics_fallback_literal(class_node, py_file, diags, strict=bool(strict))
                _check_class_template_not_implemented(class_node, py_file, diags, strict=bool(strict))
                if not _class_has_contract(class_node):
                    _add(
                        diags,
                        "error" if strict else "warn",
                        "class-contract-missing",
                        f"Class {class_node.name} has no explicit context contract fields",
                        py_file,
                    )


class _SolverMirrorWriteVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.hits: List[tuple[int, str]] = []

    def visit_Assign(self, node: ast.Assign) -> None:  # noqa: N802
        for target in node.targets:
            self._check_target(target)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:  # noqa: N802
        self._check_target(node.target)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        # Detect setattr(solver, "field", value)
        func = node.func
        if isinstance(func, ast.Name) and func.id == "setattr" and len(node.args) >= 2:
            obj = node.args[0]
            key = node.args[1]
            if isinstance(obj, ast.Name) and obj.id == "solver":
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    attr = key.value.strip()
                    if attr in _FORBIDDEN_SOLVER_MIRROR_ATTRS:
                        self.hits.append((int(getattr(node, "lineno", 0) or 0), attr))
        self.generic_visit(node)

    def _check_target(self, target: ast.expr) -> None:
        if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "solver":
            attr = str(target.attr)
            if attr in _FORBIDDEN_SOLVER_MIRROR_ATTRS:
                self.hits.append((int(getattr(target, "lineno", 0) or 0), attr))


def _check_forbidden_solver_mirror_writes(
    tree: ast.AST,
    path: Path,
    diags: List[DoctorDiagnostic],
    *,
    strict: bool,
) -> None:
    visitor = _SolverMirrorWriteVisitor()
    visitor.visit(tree)
    if not visitor.hits:
        return
    uniq: List[str] = []
    seen = set()
    for line, attr in visitor.hits:
        key = (line, attr)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(f"{attr}@L{line}")
    _add(
        diags,
        "error" if strict else "warn",
        "solver-mirror-write",
        "Forbidden solver mirror writes found (use runtime context projection instead): "
        + ", ".join(uniq[:8])
        + (" ..." if len(uniq) > 8 else ""),
        path,
    )


def _is_solver_ref(node: ast.AST) -> bool:
    if isinstance(node, ast.Name) and node.id == "solver":
        return True
    # self.solver
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
        and node.attr == "solver"
    )


def _extract_runtime_state_field_from_target(target: ast.AST) -> str | None:
    if isinstance(target, ast.Attribute) and _is_solver_ref(target.value):
        attr = str(target.attr)
        if attr in _RUNTIME_STATE_FIELDS:
            return attr
    if isinstance(target, ast.Subscript):
        value = target.value
        if isinstance(value, ast.Attribute) and _is_solver_ref(value.value):
            attr = str(value.attr)
            if attr in _RUNTIME_STATE_FIELDS:
                return attr
    return None


def _check_runtime_bypass_writes(
    tree: ast.AST,
    path: Path,
    diags: List[DoctorDiagnostic],
    *,
    strict: bool,
) -> None:
    if not strict:
        return
    hits: List[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                attr = _extract_runtime_state_field_from_target(target)
                if attr is not None:
                    hits.append((int(getattr(target, "lineno", 0) or 0), attr))
        elif isinstance(node, ast.AugAssign):
            attr = _extract_runtime_state_field_from_target(node.target)
            if attr is not None:
                hits.append((int(getattr(node.target, "lineno", 0) or 0), attr))
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "setattr" and len(node.args) >= 2:
                obj = node.args[0]
                key = node.args[1]
                if _is_solver_ref(obj) and isinstance(key, ast.Constant) and isinstance(key.value, str):
                    attr = str(key.value).strip()
                    if attr in _RUNTIME_STATE_FIELDS:
                        hits.append((int(getattr(node, "lineno", 0) or 0), attr))
    if not hits:
        return
    uniq: List[str] = []
    seen = set()
    for line, attr in hits:
        key = (line, attr)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(f"{attr}@L{line}")
    _add(
        diags,
        "error",
        "runtime-bypass-write",
        "Direct solver runtime-state writes detected; route through Runtime APIs "
        "(solver.runtime.*, write_population_snapshot, runtime context projection): "
        + ", ".join(uniq[:10])
        + (" ..." if len(uniq) > 10 else ""),
        path,
    )


def _extract_solver_field_from_target(target: ast.AST) -> str | None:
    # solver.population = ...
    if isinstance(target, ast.Attribute) and _is_solver_ref(target.value):
        attr = str(target.attr)
        if attr in _PLUGIN_STATE_FIELDS:
            return attr
    # solver.population[idx] = ...
    if isinstance(target, ast.Subscript):
        value = target.value
        if isinstance(value, ast.Attribute) and _is_solver_ref(value.value):
            attr = str(value.attr)
            if attr in _PLUGIN_STATE_FIELDS:
                return attr
    return None


def _check_plugin_solver_state_access(tree: ast.AST, path: Path, diags: List[DoctorDiagnostic]) -> None:
    reads: List[tuple[int, str]] = []
    writes: List[tuple[int, str]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                attr = _extract_solver_field_from_target(target)
                if attr is not None:
                    writes.append((int(getattr(target, "lineno", 0) or 0), attr))
        elif isinstance(node, ast.AugAssign):
            attr = _extract_solver_field_from_target(node.target)
            if attr is not None:
                writes.append((int(getattr(node.target, "lineno", 0) or 0), attr))
        elif isinstance(node, ast.Call):
            # setattr(solver, "population", ...)
            func = node.func
            if isinstance(func, ast.Name) and func.id == "setattr" and len(node.args) >= 2:
                obj = node.args[0]
                key = node.args[1]
                if _is_solver_ref(obj) and isinstance(key, ast.Constant) and isinstance(key.value, str):
                    attr = str(key.value).strip()
                    if attr in _PLUGIN_STATE_FIELDS:
                        writes.append((int(getattr(node, "lineno", 0) or 0), attr))
            # getattr(solver, "population")
            if isinstance(func, ast.Name) and func.id == "getattr" and len(node.args) >= 2:
                obj = node.args[0]
                key = node.args[1]
                if _is_solver_ref(obj) and isinstance(key, ast.Constant) and isinstance(key.value, str):
                    attr = str(key.value).strip()
                    if attr in _PLUGIN_STATE_FIELDS:
                        reads.append((int(getattr(node, "lineno", 0) or 0), attr))
        elif isinstance(node, ast.Attribute):
            if _is_solver_ref(node.value):
                attr = str(node.attr)
                if attr in _PLUGIN_STATE_FIELDS:
                    reads.append((int(getattr(node, "lineno", 0) or 0), attr))

    if not reads and not writes:
        return

    def _uniq(items: List[tuple[int, str]]) -> List[str]:
        seen = set()
        out: List[str] = []
        for line, attr in items:
            key = (line, attr)
            if key in seen:
                continue
            seen.add(key)
            out.append(f"{attr}@L{line}")
        return out

    read_list = _uniq(reads)
    write_list = _uniq(writes)
    parts: List[str] = []
    if read_list:
        parts.append("reads: " + ", ".join(read_list[:8]) + (" ..." if len(read_list) > 8 else ""))
    if write_list:
        parts.append("writes: " + ", ".join(write_list[:8]) + (" ..." if len(write_list) > 8 else ""))

    _add(
        diags,
        "error",
        "plugin-direct-solver-state-access",
        "Plugins must not directly access solver population/objectives/constraint_violations under --strict; "
        "use resolve_population_snapshot()/commit_population_snapshot(). "
        + " | ".join(parts),
        path,
    )


def _extract_solver_control_write_target(target: ast.AST) -> tuple[str, str] | None:
    if isinstance(target, ast.Attribute):
        attr = str(target.attr)
        if attr not in _SOLVER_CONTROL_FIELDS:
            return None
        obj = target.value
        if isinstance(obj, ast.Name) and obj.id in _SOLVER_LIKE_VAR_NAMES:
            return obj.id, attr
        if isinstance(obj, ast.Attribute) and isinstance(obj.value, ast.Name) and obj.value.id == "self":
            if "solver" in str(obj.attr).lower():
                return f"self.{obj.attr}", attr
    return None


def _check_examples_suites_solver_control_writes(
    root: Path,
    diags: List[DoctorDiagnostic],
    *,
    strict: bool,
) -> None:
    level = "error" if strict else "warn"
    for rel_dir in _EXAMPLE_SUITE_CHECK_DIRS:
        folder = root / rel_dir
        if not folder.is_dir():
            continue
        for py_file in folder.rglob("*.py"):
            if py_file.name.startswith("__"):
                continue
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8", errors="ignore"), filename=str(py_file))
            except Exception:
                continue

            hits: List[tuple[int, str, str]] = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        match = _extract_solver_control_write_target(target)
                        if match is not None:
                            obj_name, field = match
                            hits.append((int(getattr(target, "lineno", 0) or 0), obj_name, field))
                elif isinstance(node, ast.AugAssign):
                    match = _extract_solver_control_write_target(node.target)
                    if match is not None:
                        obj_name, field = match
                        hits.append((int(getattr(node.target, "lineno", 0) or 0), obj_name, field))
                elif isinstance(node, ast.Call):
                    func = node.func
                    if isinstance(func, ast.Name) and func.id == "setattr" and len(node.args) >= 2:
                        obj = node.args[0]
                        key = node.args[1]
                        if isinstance(obj, ast.Name) and obj.id in _SOLVER_LIKE_VAR_NAMES:
                            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                                field = str(key.value).strip()
                                if field in _SOLVER_CONTROL_FIELDS:
                                    hits.append((int(getattr(node, "lineno", 0) or 0), obj.id, field))

            if not hits:
                continue

            uniq: List[str] = []
            seen = set()
            for line, obj_name, field in hits:
                key = (line, obj_name, field)
                if key in seen:
                    continue
                seen.add(key)
                uniq.append(f"{obj_name}.{field}@L{line}")
            _add(
                diags,
                level,
                "examples-suites-direct-solver-control-write",
                (
                    "Examples/suites must use solver control-plane methods "
                    "(set_adapter/set_bias_module/set_enable_bias/set_max_steps/set_solver_hyperparams); "
                    "direct assignments are forbidden: "
                    + ", ".join(uniq[:10])
                    + (" ..." if len(uniq) > 10 else "")
                ),
                py_file,
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
    _check_adapter_layer_purity(root, diags, strict=bool(strict))
    _check_examples_suites_solver_control_writes(root, diags, strict=bool(strict))
    return DoctorReport(project_root=root, diagnostics=tuple(diags))


def format_doctor_report(report: DoctorReport) -> str:
    lines: List[str] = []
    lines.append(f"Project doctor: {report.project_root}")
    lines.append(
        f"summary: errors={report.error_count} warnings={report.warn_count} infos={report.info_count}"
    )
    for diag in report.diagnostics:
        prefix = {"error": "[ERROR]", "warn": "[WARN]", "info": "[INFO]"}.get(diag.level, "[INFO]")
        location = f" ({diag.path})" if diag.path else ""
        lines.append(f"{prefix} {diag.code}: {diag.message}{location}")
    return "\n".join(lines)


def iter_diagnostics_by_level(
    diagnostics: Iterable[DoctorDiagnostic],
    level: str,
) -> List[DoctorDiagnostic]:
    return [d for d in diagnostics if d.level == level]
