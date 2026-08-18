"""build_solver checks used by project doctor."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Callable, List

from blackbase.project import build_case, load_case_builder

from ..model import DoctorDiagnostic


def _load_module_from_file(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot import module from file: {file_path}")
    module = importlib.util.module_from_spec(spec)
    # Decorators such as dataclasses resolve annotations through sys.modules
    # while the module body executes.  A spec-only module is therefore not a
    # valid Python import boundary.
    previous = sys.modules.get(module_name)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)  # type: ignore[call-arg]
    except BaseException:
        if previous is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = previous
        raise
    if previous is None:
        sys.modules.pop(module_name, None)
    else:
        sys.modules[module_name] = previous
    return module


def check_build_solver(
    *,
    root: Path,
    diags: List[DoctorDiagnostic],
    instantiate: bool,
    strict: bool,
    add: Callable[[List[DoctorDiagnostic], str, str, str, Path | None], None],
    check_context_store_policy: Callable[..., None],
    check_snapshot_store_policy: Callable[..., None],
    check_snapshot_refs: Callable[..., None],
    check_component_catalog_registration: Callable[..., None],
    check_metrics_provider_alignment: Callable[..., None],
    check_process_like_bias_usage: Callable[..., None],
    check_runtime_governance_runtime_state: Callable[..., None],
) -> None:
    case_kind = _read_case_kind(root / ".case")
    target = "build_solver"
    build_file = root / "build_solver.py"
    if not build_file.is_file():
        add(
            diags,
            "error",
            "build-solver-missing",
            "Case is missing canonical build_solver.py",
            build_file,
        )
        return

    try:
        if root.parent.name == "cases":
            builder = load_case_builder(
                root.parent.parent,
                root.name,
                case_kind=case_kind,
            )
            build_fn = builder
        else:
            module = _load_module_from_file("nsgablack_project_build_solver", build_file)
            build_fn = getattr(module, target, None)
    except Exception as exc:
        add(diags, "error", "build-entry-import-failed", f"Cannot import {build_file.name}: {exc}", build_file)
        return

    if not callable(build_fn):
        add(diags, "error", "build-entry-missing", f"{build_file.name} has no callable {target}()", build_file)
        return

    add(diags, "info", "build-entry-found", f"Detected {target}()", build_file)

    if not instantiate:
        return

    try:
        solver = build_case(
            build_fn,
            resource_context={
                "scope": "optimization",
                "threads": 1,
                "namespace": f"doctor.{root.name}",
                "grant": {"threads": 1, "workers": 1},
                "metadata": {"source": "nsgablack.project.doctor"},
            },
            component_overrides={},
        )
    except Exception as exc:
        add(diags, "error", "build-entry-instantiate-failed", f"{target}() failed: {exc}", build_file)
        return

    if solver is None:
        add(diags, "error", "build-entry-none", f"{target}() returned None", build_file)
        return

    add(diags, "info", "build-entry-instantiated", f"{target}() returned: {solver.__class__.__name__}", build_file)
    binding = getattr(solver, "resource_binding_audit", {})
    if not isinstance(binding, dict) or not bool(binding.get("current", False)):
        add(
            diags,
            "error",
            "build-entry-resource-binding-stale",
            "Built Case did not retain the Doctor-injected ResourceContext grant.",
            build_file,
        )
    check_context_store_policy(
        root=root,
        solver=solver,
        build_file=build_file,
        diags=diags,
        strict=bool(strict),
    )
    check_snapshot_store_policy(
        root=root,
        solver=solver,
        build_file=build_file,
        diags=diags,
        strict=bool(strict),
    )
    check_snapshot_refs(
        solver=solver,
        build_file=build_file,
        diags=diags,
        strict=bool(strict),
    )
    check_component_catalog_registration(
        root=root,
        solver=solver,
        build_file=build_file,
        diags=diags,
        strict=bool(strict),
    )

    try:
        from nsgablack.core.state.context_contracts import (
            collect_solver_contracts,
            detect_context_conflicts,
            get_component_contract,
        )

        contracts = collect_solver_contracts(solver)
    except Exception as exc:
        add(diags, "warn", "contracts-collect-failed", f"Cannot collect context contracts: {exc}", build_file)
        return

    if not contracts:
        add(diags, "warn", "contracts-empty", "No context contracts were collected", build_file)
        return

    empty_contract_names: List[str] = []
    for name, contract in contracts:
        if not any([contract.requires, contract.provides, contract.mutates, contract.cache, contract.notes]):
            empty_contract_names.append(name)

    if empty_contract_names:
        preview = ", ".join(empty_contract_names[:6])
        suffix = "..." if len(empty_contract_names) > 6 else ""
        add(
            diags,
            "error" if strict else "warn",
            "contracts-not-explicit",
            f"Components without explicit context fields: {preview}{suffix}",
            build_file,
        )
    else:
        add(diags, "info", "contracts-ok", "Collected explicit context contract fields", build_file)

    try:
        conflicts = detect_context_conflicts(contracts)
    except Exception as exc:
        add(diags, "warn", "contracts-conflict-check-failed", f"Conflict check failed: {exc}", build_file)
        return
    if conflicts:
        preview = "; ".join(conflicts[:3])
        suffix = " ..." if len(conflicts) > 3 else ""
        add(
            diags,
            "warn",
            "contracts-conflict-risk",
            f"Potential multi-writer context keys: {preview}{suffix}",
            build_file,
        )

    try:
        check_metrics_provider_alignment(
            solver=solver,
            build_file=build_file,
            diags=diags,
            strict=bool(strict),
            get_component_contract=get_component_contract,
        )
    except Exception as exc:
        add(diags, "warn", "metrics-provider-check-failed", f"Metrics provider check failed: {exc}", build_file)

    try:
        check_process_like_bias_usage(
            solver=solver,
            build_file=build_file,
            diags=diags,
            strict=bool(strict),
        )
    except Exception as exc:
        add(diags, "warn", "algorithm-as-bias-check-failed", f"Process-level bias check failed: {exc}", build_file)

    try:
        check_runtime_governance_runtime_state(
            solver=solver,
            build_file=build_file,
            diags=diags,
            strict=bool(strict),
        )
    except Exception as exc:
        add(diags, "warn", "runtime-governance-check-failed", f"Runtime governance check failed: {exc}", build_file)


def _read_case_kind(marker_path: Path) -> str | None:
    if not marker_path.is_file():
        return None
    try:
        text = marker_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = marker_path.read_text(encoding="utf-8-sig", errors="replace")
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip().lower() != "kind":
            continue
        token = value.strip().strip('"').strip("'").lower()
        if token in {"solver", "trainer"}:
            return token
    return None
