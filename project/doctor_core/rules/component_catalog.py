"""Component inventory and catalog registration checks used by project doctor."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable, List

from ..model import DoctorDiagnostic


def collect_solver_components(solver: object) -> List[tuple[str, object]]:
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


def collect_bias_instances(solver: object) -> List[tuple[str, object]]:
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


def _component_import_path(obj: object) -> str:
    cls = getattr(obj, "__class__", None)
    if cls is None:
        return ""
    module = str(getattr(cls, "__module__", "") or "").strip()
    name = str(getattr(cls, "__name__", "") or "").strip()
    if not module or not name:
        return ""
    return f"{module}:{name}"


def check_process_like_bias_usage(
    *,
    solver: object,
    build_file: Path,
    diags: List[DoctorDiagnostic],
    strict: bool,
    add: Callable[[List[DoctorDiagnostic], str, str, str, Path | None], None],
    process_like_bias_module_prefixes: Iterable[str],
) -> None:
    prefixes = tuple(str(item) for item in process_like_bias_module_prefixes)
    hits: List[str] = []
    for bias_name, bias_obj in collect_bias_instances(solver):
        cls_name = bias_obj.__class__.__name__
        cls_module = str(getattr(bias_obj.__class__, "__module__", ""))
        if not any(cls_module.startswith(prefix) for prefix in prefixes):
            continue
        hits.append(f"{bias_name}({cls_module}:{cls_name})")

    if not hits:
        return

    preview = ", ".join(hits[:8])
    suffix = " ..." if len(hits) > 8 else ""
    add(
        diags,
        "error" if strict else "warn",
        "algorithm-as-bias",
        (
            "Process-level algorithm classes are attached as bias; move them to adapter/strategy layer: "
            f"{preview}{suffix}"
        ),
        build_file,
    )


def check_component_catalog_registration(
    *,
    root: Path,
    solver: object,
    build_file: Path,
    diags: List[DoctorDiagnostic],
    strict: bool,
    add: Callable[[List[DoctorDiagnostic], str, str, str, Path | None], None],
    get_catalog_entries: Callable[[], Iterable[object]],
    load_project_entries: Callable[[Path], Iterable[object]],
) -> None:
    try:
        framework_entries = list(get_catalog_entries())
    except Exception as exc:
        add(diags, "warn", "catalog-check-failed", f"Global catalog load failed: {exc}", build_file)
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
    for comp_name, comp_obj in collect_solver_components(solver) + collect_bias_instances(solver):
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
        add(
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
        add(
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
