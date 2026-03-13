"""build_solver checks used by project doctor."""

from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path
from typing import Callable, List

from ..model import DoctorDiagnostic


def _load_module_from_file(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot import module from file: {file_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[call-arg]
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
) -> None:
    build_file = root / "build_solver.py"
    if not build_file.is_file():
        return

    try:
        module = _load_module_from_file("nsgablack_project_build_solver", build_file)
    except Exception as exc:
        add(diags, "error", "build-solver-import-failed", f"Cannot import build_solver.py: {exc}", build_file)
        return

    build_fn = getattr(module, "build_solver", None)
    if not callable(build_fn):
        add(diags, "error", "build-solver-missing", "build_solver.py has no callable build_solver()", build_file)
        return

    add(diags, "info", "build-solver-found", "Detected build_solver()", build_file)

    if not instantiate:
        return

    try:
        sig = inspect.signature(build_fn)
        if len(sig.parameters) == 0:
            solver = build_fn()
        else:
            solver = build_fn([])
    except Exception as exc:
        add(diags, "error", "build-solver-instantiate-failed", f"build_solver() failed: {exc}", build_file)
        return

    if solver is None:
        add(diags, "error", "build-solver-none", "build_solver() returned None", build_file)
        return

    add(diags, "info", "build-solver-instantiated", f"build_solver() returned: {solver.__class__.__name__}", build_file)
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
        from nsgablack.utils.context.context_contracts import (
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
