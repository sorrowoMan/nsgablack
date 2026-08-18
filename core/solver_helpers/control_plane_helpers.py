"""Control-plane helper utilities for SolverBase."""

from __future__ import annotations

import hashlib
import json
from dataclasses import fields as dataclass_fields, is_dataclass
from typing import Any, Dict, Mapping, Optional

import numpy as np
from blackbase.context import (
    RuntimeContextProjection,
    detach_context_value,
)

from blackbase.context.context_keys import (
    KEY_ADAPTER_BEST_X,
    KEY_BEST_CANDIDATE_REF,
    KEY_BEST_OBJECTIVE,
    KEY_BEST_X,
    KEY_EVALUATION_COUNT,
    KEY_GENERATION,
    KEY_PARETO_OBJECTIVES,
    KEY_PARETO_SOLUTIONS,
    KEY_RUNTIME_PROJECTION_AUDIT,
)


_SOLVER_RUNTIME_PROJECTION_RESERVED_KEYS = frozenset(
    (
        KEY_GENERATION,
        KEY_EVALUATION_COUNT,
        KEY_BEST_X,
        KEY_BEST_CANDIDATE_REF,
        KEY_BEST_OBJECTIVE,
        KEY_RUNTIME_PROJECTION_AUDIT,
    )
)

_RUNTIME_PROJECTION_AUDIT_MAX_SAMPLES = 16
_RUNTIME_PROJECTION_AUDIT_KEY_MAX_BYTES = 96
_RUNTIME_PROJECTION_SOURCE_MAX_BYTES = 128
_RUNTIME_PROJECTION_ERROR_MAX_BYTES = 384
_RUNTIME_PROJECTION_REPORT_MAX_SAMPLES = 8
_RUNTIME_PROJECTION_REPORT_MAX_BYTES = 512
_RUNTIME_PROJECTION_AUDIT_MAX_BYTES = 4_096


def _update_stable_digest(digest: Any, *parts: Any) -> None:
    """Add length-prefixed values to a process-independent digest."""

    for part in parts:
        payload = str(part).encode("utf-8", errors="replace")
        digest.update(len(payload).to_bytes(8, byteorder="big", signed=False))
        digest.update(payload)


def _bounded_runtime_projection_text(
    value: Any,
    *,
    max_bytes: int,
) -> tuple[str, bool, str]:
    """Return bounded UTF-8 text plus a stable digest of the full value."""

    try:
        text = str(value)
    except Exception as exc:
        text = f"<unprintable {type(value).__name__}: {type(exc).__name__}>"
    payload = text.encode("utf-8", errors="replace")
    full_digest = hashlib.sha256(payload).hexdigest()
    limit = max(0, int(max_bytes))
    if len(payload) <= limit:
        return text, False, full_digest

    suffix = f"…#{full_digest[:16]}".encode("utf-8")
    if limit <= len(suffix):
        bounded = suffix[-limit:] if limit else b""
    else:
        prefix = payload[: limit - len(suffix)].decode(
            "utf-8",
            errors="ignore",
        )
        bounded = prefix.encode("utf-8") + suffix
    return bounded.decode("utf-8", errors="ignore"), True, full_digest


def _runtime_projection_error_payload(exc: Exception) -> Dict[str, Any]:
    message, truncated, message_hash = _bounded_runtime_projection_text(
        exc,
        max_bytes=_RUNTIME_PROJECTION_ERROR_MAX_BYTES,
    )
    error_type, type_truncated, _ = _bounded_runtime_projection_text(
        type(exc).__name__,
        max_bytes=64,
    )
    return {
        "type": error_type,
        "message": message,
        "message_hash": message_hash,
        "message_truncated": bool(truncated or type_truncated),
    }


def _bounded_runtime_projection_key(key: str) -> tuple[str, bool, str]:
    return _bounded_runtime_projection_text(
        key,
        max_bytes=_RUNTIME_PROJECTION_AUDIT_KEY_MAX_BYTES,
    )


def _bounded_runtime_projection_report(
    prefix: str,
    samples: list[str],
    *,
    total_count: int,
) -> str:
    visible = list(samples[:_RUNTIME_PROJECTION_REPORT_MAX_SAMPLES])
    remaining = max(0, int(total_count) - len(visible))
    detail = ", ".join(visible)
    if remaining:
        detail = f"{detail}, +{remaining} more" if detail else f"+{remaining} more"
    message, _, _ = _bounded_runtime_projection_text(
        prefix + detail,
        max_bytes=_RUNTIME_PROJECTION_REPORT_MAX_BYTES,
    )
    return message


def _estimate_runtime_projection_value_bytes(
    value: Any,
    *,
    cutoff: int,
    _seen: Optional[set[int]] = None,
) -> int:
    """Conservatively estimate a transport-oriented projection size.

    The estimator stops as soon as *cutoff* is exceeded and fails closed for
    unknown Python objects. Runtime projection is a telemetry boundary, so an
    object without an explicit lightweight representation must not enter
    Context merely because ``repr`` happens to be short.
    """

    limit = max(0, int(cutoff))
    if value is None:
        return 4
    if isinstance(value, bool):
        return 5
    if isinstance(value, (int, float)):
        return len(str(value).encode("utf-8"))
    if isinstance(value, str):
        return len(value.encode("utf-8"))
    if isinstance(value, (bytes, bytearray, memoryview)):
        return len(value)
    if isinstance(value, np.generic):
        return _estimate_runtime_projection_value_bytes(
            value.item(), cutoff=limit, _seen=_seen
        )
    if isinstance(value, np.ndarray):
        if bool(value.dtype.hasobject):
            return limit + 1
        return 64 + int(value.nbytes) + len(str(value.dtype).encode("utf-8"))

    seen = set() if _seen is None else _seen
    if is_dataclass(value) and not isinstance(value, type):
        object_id = id(value)
        if object_id in seen:
            return limit + 1
        seen.add(object_id)
        total = 2
        try:
            for field in dataclass_fields(value):
                total += len(str(field.name).encode("utf-8")) + 3
                remaining = max(0, limit - total)
                total += _estimate_runtime_projection_value_bytes(
                    getattr(value, field.name),
                    cutoff=remaining,
                    _seen=seen,
                )
                if total > limit:
                    return limit + 1
        finally:
            seen.discard(object_id)
        return total

    if isinstance(value, Mapping):
        object_id = id(value)
        if object_id in seen:
            return limit + 1
        seen.add(object_id)
        total = 2
        try:
            for key, item in value.items():
                total += len(str(key).encode("utf-8")) + 3
                remaining = max(0, limit - total)
                total += _estimate_runtime_projection_value_bytes(
                    item,
                    cutoff=remaining,
                    _seen=seen,
                )
                if total > limit:
                    return limit + 1
        finally:
            seen.discard(object_id)
        return total

    if isinstance(value, (list, tuple, set, frozenset)):
        object_id = id(value)
        if object_id in seen:
            return limit + 1
        seen.add(object_id)
        total = 2
        try:
            for item in value:
                remaining = max(0, limit - total)
                total += _estimate_runtime_projection_value_bytes(
                    item,
                    cutoff=remaining,
                    _seen=seen,
                ) + 1
                if total > limit:
                    return limit + 1
        finally:
            seen.discard(object_id)
        return total

    return limit + 1


def _runtime_projection_limits(solver: Any) -> tuple[int, int]:
    field_limit = max(
        0,
        int(
            getattr(
                solver,
                "runtime_context_projection_field_max_bytes",
                4_096,
            )
            or 0
        ),
    )
    total_limit = max(
        0,
        int(
            getattr(
                solver,
                "runtime_context_projection_total_max_bytes",
                32_768,
            )
            or 0
        ),
    )
    return field_limit, total_limit


def _runtime_projection_audit_size(audit: Mapping[str, Any]) -> int:
    return len(
        json.dumps(
            audit,
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    )


def _minimal_runtime_projection_audit_error(
    exc: Exception,
    *,
    signature_hint: str = "",
) -> Dict[str, Any]:
    projection_error = _runtime_projection_error_payload(exc)
    digest = hashlib.sha256()
    _update_stable_digest(
        digest,
        "runtime_projection_audit/error/v1",
        signature_hint,
        projection_error.get("type", ""),
        projection_error.get("message_hash", ""),
    )
    field_source_digest = hashlib.sha256()
    _update_stable_digest(
        field_source_digest,
        "runtime_projection_field_sources/v1",
    )
    return {
        "status": "error",
        "current": False,
        "projection_error": projection_error,
        "component_audit": None,
        "field_limit_bytes": 0,
        "total_limit_bytes": 0,
        "accepted_bytes": 0,
        "accepted_field_count": 0,
        "field_sources_current": False,
        "field_source_error": projection_error,
        "field_source_count": 0,
        "field_source_digest": field_source_digest.hexdigest(),
        "field_source_samples": [],
        "conflict_count": 0,
        "omitted_field_count": 0,
        "reason_counts": {},
        "reserved_conflicts": [],
        "omitted_fields": [],
        "audit_sample_limit": 0,
        "audit_max_bytes": _RUNTIME_PROJECTION_AUDIT_MAX_BYTES,
        "audit_truncated": True,
        "signature": digest.hexdigest(),
    }


def _bound_runtime_projection_audit(
    audit: Mapping[str, Any],
) -> Dict[str, Any]:
    """Apply a final hard byte budget to the complete outer audit."""

    out = detach_context_value(audit, path="runtime_projection_audit_budget")
    out["audit_max_bytes"] = _RUNTIME_PROJECTION_AUDIT_MAX_BYTES
    if _runtime_projection_audit_size(out) <= _RUNTIME_PROJECTION_AUDIT_MAX_BYTES:
        return out

    out["audit_truncated"] = True
    component = out.get("component_audit")
    if isinstance(component, dict):
        component["audit_truncated"] = True
        samples = component.get("issue_samples")
        if isinstance(samples, list):
            while (
                samples
                and _runtime_projection_audit_size(out)
                > _RUNTIME_PROJECTION_AUDIT_MAX_BYTES
            ):
                samples.pop()
                component["issue_sample_count"] = len(samples)

    for sample_key, count_key in (
        ("field_source_samples", "field_source_count"),
        ("omitted_fields", "omitted_field_count"),
        ("reserved_conflicts", "conflict_count"),
    ):
        samples = out.get(sample_key)
        if isinstance(samples, list):
            while (
                samples
                and _runtime_projection_audit_size(out)
                > _RUNTIME_PROJECTION_AUDIT_MAX_BYTES
            ):
                samples.pop()
            if len(samples) < int(out.get(count_key, 0) or 0):
                out["audit_truncated"] = True

    if _runtime_projection_audit_size(out) > _RUNTIME_PROJECTION_AUDIT_MAX_BYTES:
        for error_key in ("projection_error", "field_source_error"):
            error = out.get(error_key)
            if isinstance(error, dict) and error.get("message"):
                error["message"] = "<message omitted by audit budget>"
                error["message_truncated"] = True

    if _runtime_projection_audit_size(out) > _RUNTIME_PROJECTION_AUDIT_MAX_BYTES:
        component = out.get("component_audit")
        if isinstance(component, dict):
            out["component_audit"] = {
                key: component.get(key)
                for key in (
                    "schema",
                    "status",
                    "component_count",
                    "successful_component_count",
                    "degraded_component_count",
                    "failed_component_count",
                    "invalid_component_count",
                    "unavailable_component_count",
                    "issue_count",
                    "issue_digest",
                    "field_source_count",
                    "field_source_digest",
                    "audit_digest",
                )
            }
            out["component_audit"]["issue_samples"] = []
            out["component_audit"]["issue_sample_count"] = 0
            out["component_audit"]["audit_truncated"] = True

    if _runtime_projection_audit_size(out) > _RUNTIME_PROJECTION_AUDIT_MAX_BYTES:
        raise RuntimeError("runtime projection audit exceeds its hard byte budget")
    return out


def _record_runtime_projection_audit(
    solver: Any,
    audit: Mapping[str, Any],
) -> tuple[Dict[str, Any], Optional[Exception]]:
    try:
        detached = detach_context_value(
            audit,
            path="runtime_projection_audit",
        )
    except Exception as exc:
        fallback = _minimal_runtime_projection_audit_error(
            exc,
            signature_hint=str(audit.get("signature", "")),
        )
        try:
            setattr(solver, "_runtime_projection_audit", fallback)
        except Exception:
            pass
        return fallback, exc
    try:
        setattr(solver, "_runtime_projection_audit", detached)
    except Exception as exc:
        fallback = _minimal_runtime_projection_audit_error(
            exc,
            signature_hint=str(detached.get("signature", "")),
        )
        try:
            setattr(solver, "_runtime_projection_audit", fallback)
        except Exception:
            pass
        return fallback, exc
    return detached, None


def collect_adapter_runtime_context_projection(
    solver: Any,
    *,
    report_soft_error_fn: Any = None,
    logger: Any = None,
) -> Dict[str, Any]:
    """Collect one bounded Adapter telemetry projection.

    This is the canonical consumption boundary for Adapter runtime projection.
    It never manufactures Snapshot/Artifact references: an owning Adapter or
    Plugin must publish a real lightweight ref before it can cross this edge.
    """

    adapter = getattr(solver, "adapter", None)
    projector = getattr(adapter, "get_runtime_context_projection", None)
    field_limit, total_limit = _runtime_projection_limits(solver)
    accepted: Dict[str, Any] = {}
    accepted_sizes: Dict[str, int] = {}
    conflicts: list[str] = []
    omitted: list[Dict[str, Any]] = []
    conflict_count = 0
    omitted_count = 0
    reason_counts: Dict[str, int] = {}
    accepted_bytes = 0
    audit_truncated = False
    status = "unavailable"
    projection_error: Optional[Dict[str, Any]] = None
    report_exception: Optional[Exception] = None
    report_event: Optional[str] = None
    component_audit: Optional[Dict[str, Any]] = None
    declared_field_sources: Dict[str, str] = {}
    field_source_error: Optional[Dict[str, Any]] = None
    record_digest = hashlib.sha256()

    if callable(projector):
        try:
            extra = projector(solver)
        except Exception as exc:
            status = "error"
            projection_error = _runtime_projection_error_payload(exc)
            report_exception = RuntimeError(str(projection_error["message"]))
            report_event = "adapter_runtime_context_projection"
        else:
            if not isinstance(extra, Mapping):
                status = "invalid_result"
                invalid = TypeError(
                    "adapter runtime projection must return a Mapping, got "
                    f"{type(extra).__name__}"
                )
                projection_error = _runtime_projection_error_payload(invalid)
                report_exception = TypeError(str(projection_error["message"]))
                report_event = "adapter_runtime_context_projection_invalid_result"
            else:
                if isinstance(extra, RuntimeContextProjection):
                    try:
                        component_audit = RuntimeContextProjection.as_audit(extra)
                    except Exception as exc:
                        status = "error"
                        projection_error = _runtime_projection_error_payload(exc)
                        report_exception = RuntimeError(
                            str(projection_error["message"])
                        )
                        report_event = (
                            "adapter_runtime_context_projection_component_audit"
                        )
                    else:
                        status = str(extra.status)
                        declared_field_sources = dict(extra.field_sources)
                    if status in {"degraded", "error"} and report_exception is None:
                        report_exception = RuntimeError(
                            "composite adapter runtime projection "
                            f"reported {status} component health"
                        )
                        report_event = (
                            "adapter_runtime_context_projection_" + status
                        )
                else:
                    status = "ok"

                if not isinstance(extra, RuntimeContextProjection):
                    source_getter = getattr(
                        adapter,
                        "get_runtime_context_projection_sources",
                        None,
                    )
                    if callable(source_getter):
                        try:
                            raw_sources = source_getter(solver)
                            if not isinstance(raw_sources, Mapping):
                                raise TypeError(
                                    "adapter runtime projection sources must return "
                                    "a Mapping"
                                )
                            normalized_sources: Dict[str, str] = {}
                            for raw_key, raw_source in raw_sources.items():
                                if not isinstance(raw_source, str):
                                    raise TypeError(
                                        "adapter runtime projection source values "
                                        "must be strings"
                                    )
                                normalized_sources[str(raw_key)] = raw_source
                            declared_field_sources = normalized_sources
                        except Exception as exc:
                            field_source_error = _runtime_projection_error_payload(exc)
                            if report_exception is None:
                                report_exception = RuntimeError(
                                    str(field_source_error["message"])
                                )
                                report_event = (
                                    "adapter_runtime_context_projection_sources"
                                )

                def record_conflict(key: str) -> None:
                    nonlocal conflict_count, audit_truncated
                    conflict_count += 1
                    _update_stable_digest(record_digest, "conflict", key)
                    if len(conflicts) >= _RUNTIME_PROJECTION_AUDIT_MAX_SAMPLES:
                        audit_truncated = True
                        return
                    bounded_key, truncated, _ = _bounded_runtime_projection_key(key)
                    conflicts.append(bounded_key)
                    audit_truncated = bool(audit_truncated or truncated)

                def record_omission(
                    key: str,
                    reason: str,
                    estimated_bytes: int,
                ) -> None:
                    nonlocal omitted_count, audit_truncated
                    omitted_count += 1
                    reason_counts[reason] = int(reason_counts.get(reason, 0)) + 1
                    _update_stable_digest(
                        record_digest,
                        "omitted",
                        key,
                        reason,
                        int(estimated_bytes),
                    )
                    if len(omitted) >= _RUNTIME_PROJECTION_AUDIT_MAX_SAMPLES:
                        audit_truncated = True
                        return
                    bounded_key, truncated, key_hash = (
                        _bounded_runtime_projection_key(key)
                    )
                    sample: Dict[str, Any] = {
                        "key": bounded_key,
                        "reason": reason,
                        "estimated_bytes": int(estimated_bytes),
                    }
                    if truncated:
                        sample["key_hash"] = key_hash[:16]
                        sample["key_truncated"] = True
                    omitted.append(sample)
                    audit_truncated = bool(audit_truncated or truncated)

                try:
                    for raw_key, value in extra.items():
                        key = str(raw_key)
                        if key in _SOLVER_RUNTIME_PROJECTION_RESERVED_KEYS:
                            record_conflict(key)
                            continue
                        if value is None:
                            continue

                        previous_size = accepted_sizes.pop(key, None)
                        if previous_size is not None:
                            accepted.pop(key, None)
                            accepted_bytes -= int(previous_size)

                        if key == KEY_ADAPTER_BEST_X:
                            candidate_can_inline = getattr(
                                solver,
                                "_candidate_can_inline_in_context",
                                None,
                            )
                            if callable(candidate_can_inline) and not bool(
                                candidate_can_inline(value)
                            ):
                                record_omission(
                                    key,
                                    "candidate_inline_limit",
                                    _estimate_runtime_projection_value_bytes(
                                        value,
                                        cutoff=field_limit,
                                    ),
                                )
                                continue

                        try:
                            detached_value = detach_context_value(
                                value,
                                path=f"adapter_runtime_projection[{key!r}]",
                            )
                        except TypeError:
                            record_omission(
                                key,
                                "unsupported_type",
                                _estimate_runtime_projection_value_bytes(
                                    value,
                                    cutoff=field_limit,
                                ),
                            )
                            continue

                        estimated_bytes = _estimate_runtime_projection_value_bytes(
                            detached_value,
                            cutoff=field_limit,
                        )
                        if estimated_bytes > field_limit:
                            record_omission(key, "field_limit", estimated_bytes)
                            continue

                        field_bytes = len(key.encode("utf-8")) + int(
                            estimated_bytes
                        )
                        projected_bytes = accepted_bytes + field_bytes
                        if projected_bytes > total_limit:
                            record_omission(key, "total_limit", estimated_bytes)
                            continue
                        accepted[key] = detached_value
                        accepted_sizes[key] = int(field_bytes)
                        accepted_bytes = projected_bytes
                except Exception as exc:
                    status = "error"
                    projection_error = _runtime_projection_error_payload(exc)
                    report_exception = RuntimeError(
                        str(projection_error["message"])
                    )
                    report_event = "adapter_runtime_context_projection"
                    accepted = {}
                    accepted_sizes = {}
                    conflicts = []
                    omitted = []
                    conflict_count = 0
                    omitted_count = 0
                    reason_counts = {}
                    accepted_bytes = 0
                    declared_field_sources = {}
                    audit_truncated = bool(
                        projection_error.get("message_truncated", False)
                    )
                    record_digest = hashlib.sha256()

    if projection_error is not None:
        audit_truncated = bool(
            audit_truncated or projection_error.get("message_truncated", False)
        )

    fallback_source = (
        f"adapter.{adapter.__class__.__name__}" if adapter is not None else "adapter"
    )
    field_source_digest_state = hashlib.sha256()
    _update_stable_digest(
        field_source_digest_state,
        "runtime_projection_field_sources/v1",
    )
    field_source_samples: list[Dict[str, Any]] = []
    for key in sorted(accepted):
        source = declared_field_sources.get(key, fallback_source)
        _update_stable_digest(field_source_digest_state, key, source)
        if len(field_source_samples) >= _RUNTIME_PROJECTION_AUDIT_MAX_SAMPLES:
            audit_truncated = True
            continue
        bounded_key, key_truncated, key_hash = _bounded_runtime_projection_key(key)
        bounded_source, source_truncated, source_hash = (
            _bounded_runtime_projection_text(
                source,
                max_bytes=_RUNTIME_PROJECTION_SOURCE_MAX_BYTES,
            )
        )
        sample: Dict[str, Any] = {
            "key": bounded_key,
            "source": bounded_source,
        }
        if key_truncated:
            sample["key_hash"] = key_hash[:16]
            sample["key_truncated"] = True
        if source_truncated:
            sample["source_hash"] = source_hash[:16]
            sample["source_truncated"] = True
        field_source_samples.append(sample)
        audit_truncated = bool(
            audit_truncated or key_truncated or source_truncated
        )
    field_source_digest = field_source_digest_state.hexdigest()
    if field_source_error is not None:
        audit_truncated = bool(
            audit_truncated
            or field_source_error.get("message_truncated", False)
        )

    signature_digest = hashlib.sha256()
    _update_stable_digest(
        signature_digest,
        "runtime_projection_audit/v1",
        status,
        int(field_limit),
        int(total_limit),
        int(conflict_count),
        int(omitted_count),
        record_digest.hexdigest(),
        field_source_digest,
    )
    if component_audit is not None:
        _update_stable_digest(
            signature_digest,
            component_audit.get("audit_digest", ""),
        )
    for reason, count in sorted(reason_counts.items()):
        _update_stable_digest(signature_digest, reason, int(count))
    if projection_error is not None:
        _update_stable_digest(
            signature_digest,
            projection_error.get("type", ""),
            projection_error.get("message_hash", ""),
        )
    if field_source_error is not None:
        _update_stable_digest(
            signature_digest,
            field_source_error.get("type", ""),
            field_source_error.get("message_hash", ""),
        )
    signature = signature_digest.hexdigest()

    audit = {
        "status": status,
        "current": (
            status in {"ok", "unavailable"}
            and conflict_count == 0
            and omitted_count == 0
            and field_source_error is None
        ),
        "projection_error": projection_error,
        "component_audit": component_audit,
        "field_limit_bytes": int(field_limit),
        "total_limit_bytes": int(total_limit),
        "accepted_bytes": int(accepted_bytes),
        "accepted_field_count": int(len(accepted)),
        "field_sources_current": field_source_error is None,
        "field_source_error": field_source_error,
        "field_source_count": int(len(accepted)),
        "field_source_digest": field_source_digest,
        "field_source_samples": field_source_samples,
        "conflict_count": int(conflict_count),
        "omitted_field_count": int(omitted_count),
        "reason_counts": dict(sorted(reason_counts.items())),
        "reserved_conflicts": list(conflicts),
        "omitted_fields": list(omitted),
        "audit_sample_limit": int(_RUNTIME_PROJECTION_AUDIT_MAX_SAMPLES),
        "audit_truncated": bool(
            audit_truncated
            or (
                isinstance(component_audit, Mapping)
                and component_audit.get("audit_truncated", False)
            )
        ),
        "signature": signature,
    }
    try:
        audit = _bound_runtime_projection_audit(audit)
    except Exception as exc:
        audit = _minimal_runtime_projection_audit_error(
            exc,
            signature_hint=signature,
        )
        report_exception = RuntimeError(str(exc))
        report_event = "adapter_runtime_context_projection_audit_budget"
    audit, audit_record_error = _record_runtime_projection_audit(solver, audit)
    if audit_record_error is not None:
        report_exception = RuntimeError(str(audit_record_error))
        report_event = "adapter_runtime_context_projection_audit_isolation"
    signature = str(audit.get("signature", signature))

    previous_signature = getattr(
        solver,
        "_runtime_projection_audit_report_signature",
        None,
    )
    if signature != previous_signature:
        try:
            setattr(solver, "_runtime_projection_audit_report_signature", signature)
        except Exception:
            pass
        if report_exception is not None and callable(report_soft_error_fn):
            report_soft_error_fn(
                component="SolverBase",
                event=str(report_event),
                exc=report_exception,
                logger=logger,
                context_store=getattr(solver, "context_store", None),
                strict=False,
                level="debug",
            )
        if conflict_count and callable(report_soft_error_fn):
            message = _bounded_runtime_projection_report(
                "adapter runtime projection attempted to overwrite "
                "Solver-owned fields: ",
                conflicts,
                total_count=conflict_count,
            )
            report_soft_error_fn(
                component="SolverBase",
                event="adapter_runtime_context_projection_reserved_keys",
                exc=ValueError(message),
                logger=logger,
                context_store=getattr(solver, "context_store", None),
                strict=False,
                level="debug",
            )
        if omitted_count and callable(report_soft_error_fn):
            samples = [
                f"{item['key']}[{item['reason']},~{item['estimated_bytes']}B]"
                for item in omitted
            ]
            message = _bounded_runtime_projection_report(
                "omitted oversized runtime fields: ",
                samples,
                total_count=omitted_count,
            )
            report_soft_error_fn(
                component="SolverBase",
                event="adapter_runtime_context_projection_budget",
                exc=ValueError(message),
                logger=logger,
                context_store=getattr(solver, "context_store", None),
                strict=False,
                level="debug",
            )
    return accepted


def _store_set(store: Any, key: str, value: Any) -> None:
    if store is None:
        return
    set_fn = getattr(store, "set", None)
    if callable(set_fn):
        try:
            set_fn(key, value)
        except Exception:
            return
    elif isinstance(store, dict):
        store[key] = value


def collect_runtime_context_projection(
    solver: Any,
    *,
    report_soft_error_fn: Any = None,
    logger: Any = None,
    keys: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Collect a small runtime projection from solver and adapter state."""
    if isinstance(solver, Mapping):
        key_map = dict(keys or {})
        return {dst: solver.get(src) for src, dst in key_map.items() if src in solver}

    out: Dict[str, Any] = {
        KEY_GENERATION: int(getattr(solver, "generation", 0) or 0),
        KEY_EVALUATION_COUNT: int(getattr(solver, "evaluation_count", 0) or 0),
    }
    project_incumbent = getattr(solver, "project_incumbent_context", None)
    if callable(project_incumbent):
        project_incumbent(out)
    else:
        get_incumbent = getattr(solver, "get_incumbent", None)
        incumbent = get_incumbent() if callable(get_incumbent) else None
        best_x = (
            incumbent.candidate.copy()
            if incumbent is not None
            else getattr(solver, "best_x", None)
        )
        best_objective = (
            float(incumbent.score)
            if incumbent is not None
            else getattr(solver, "best_objective", getattr(solver, "best_f", None))
        )
        can_inline = getattr(solver, "_candidate_can_inline_in_context", None)
        if best_x is not None and (
            not callable(can_inline) or bool(can_inline(best_x))
        ):
            out[KEY_BEST_X] = best_x
        best_ref = getattr(solver, "_incumbent_candidate_ref", None)
        if best_x is not None and KEY_BEST_X not in out and best_ref:
            out[KEY_BEST_CANDIDATE_REF] = str(best_ref)
        if best_objective is not None:
            out[KEY_BEST_OBJECTIVE] = best_objective

    out.update(
        collect_adapter_runtime_context_projection(
            solver,
            report_soft_error_fn=report_soft_error_fn,
            logger=logger,
        )
    )
    audit = getattr(solver, "_runtime_projection_audit", None)
    if isinstance(audit, Mapping):
        out[KEY_RUNTIME_PROJECTION_AUDIT] = detach_context_value(
            audit,
            path="runtime_projection_audit",
        )
    return out


def increment_evaluation_counter(
    solver: Any,
    delta: int = 1,
    *,
    report_soft_error_fn: Any = None,
    logger: Any = None,
) -> int:
    """Increment solver.evaluation_count and mirror it to context_store."""
    if isinstance(solver, Mapping):
        return int(solver.get(KEY_EVALUATION_COUNT, solver.get("evaluation_count", 0)) or 0) + int(delta)
    current = int(getattr(solver, "evaluation_count", 0) or 0)
    value = current + int(delta)
    setattr(solver, "evaluation_count", value)
    _store_set(getattr(solver, "context_store", None), KEY_EVALUATION_COUNT, value)
    return value


def get_best_snapshot_fields(
    solver: Any,
    *,
    report_soft_error_fn: Any = None,
    logger: Any = None,
) -> tuple[Any, Any]:
    """Return `(best_x, best_objective)` from solver/context store."""
    if isinstance(solver, Mapping):
        return solver.get(KEY_BEST_X), solver.get(KEY_BEST_OBJECTIVE)
    get_incumbent = getattr(solver, "get_incumbent", None)
    if callable(get_incumbent):
        incumbent = get_incumbent()
        if incumbent is not None:
            return incumbent.candidate.copy(), float(incumbent.score)
    return None, None


def set_generation_value(solver: Any, generation: int) -> int:
    """Set generation on solver and context_store."""
    value = int(generation)
    if isinstance(solver, dict):
        solver[KEY_GENERATION] = value
        return value
    setattr(solver, "generation", value)
    _store_set(getattr(solver, "context_store", None), KEY_GENERATION, value)
    return value


def set_pareto_snapshot_fields(
    solver: Any,
    solutions: Any = None,
    objectives: Any = None,
    *,
    report_soft_error_fn: Any = None,
    logger: Any = None,
) -> None:
    """Set Pareto fields on solver and context_store."""
    if isinstance(solver, dict):
        solver[KEY_PARETO_SOLUTIONS] = solutions
        solver[KEY_PARETO_OBJECTIVES] = objectives
        return
    setattr(solver, "pareto_solutions", solutions)
    setattr(solver, "pareto_objectives", objectives)
    store = getattr(solver, "context_store", None)
    _store_set(store, KEY_PARETO_SOLUTIONS, solutions)
    _store_set(store, KEY_PARETO_OBJECTIVES, objectives)


__all__ = [
    "collect_adapter_runtime_context_projection",
    "collect_runtime_context_projection",
    "increment_evaluation_counter",
    "get_best_snapshot_fields",
    "set_generation_value",
    "set_pareto_snapshot_fields",
]
