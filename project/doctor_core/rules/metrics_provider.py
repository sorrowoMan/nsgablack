"""Metrics provider/consumer contract checks used by project doctor."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, List, Sequence

from ..model import DoctorDiagnostic


def _iter_metric_requires(name: str, obj: object, contract: object | None) -> List[str]:
    del name
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


def _is_valid_metrics_fallback_value(value: str, *, allowed_metrics_fallback_values: Sequence[str]) -> bool:
    return str(value).strip().lower() in set(allowed_metrics_fallback_values)


def _has_metrics_fallback(obj: object, _contract: object | None) -> bool:
    # Fallback must be explicit in component config/contract policy.
    # Avoid notes/description keyword heuristics.
    policy = str(getattr(obj, "missing_metrics_policy", "") or "").strip().lower()
    if policy in {"warn", "ignore", "none", "off"}:
        return True
    fallback = _read_metrics_fallback_value(obj) or ""
    return fallback in {"safe_zero", "problem_data", "default", "warn", "ignore"}


def check_metrics_provider_alignment(
    *,
    solver: object,
    build_file: Path,
    diags: List[DoctorDiagnostic],
    strict: bool,
    add: Callable[[List[DoctorDiagnostic], str, str, str, Path | None], None],
    get_component_contract: Callable[[object], object | None],
    collect_solver_components: Callable[[object], List[tuple[str, object]]],
    allowed_metrics_fallback_values: Sequence[str],
) -> None:
    providers_by_metric: dict[str, set[str]] = {}
    wildcard_metrics_providers: set[str] = set()
    consumers: List[tuple[str, str, bool]] = []
    checked_fallback_obj_ids: set[int] = set()

    components = collect_solver_components(solver)
    for comp_name, comp_obj in components:
        marker_id = id(comp_obj)
        if marker_id not in checked_fallback_obj_ids:
            checked_fallback_obj_ids.add(marker_id)
            fallback = _read_metrics_fallback_value(comp_obj)
            if fallback is not None and not _is_valid_metrics_fallback_value(
                fallback, allowed_metrics_fallback_values=allowed_metrics_fallback_values
            ):
                allowed = ", ".join(sorted({str(v).strip().lower() for v in allowed_metrics_fallback_values if str(v).strip()}))
                add(
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
    add(
        diags,
        "error" if strict else "warn",
        "metrics-provider-missing",
        "requires_metrics has no provider/fallback in current assembly: " + preview + suffix,
        build_file,
    )
