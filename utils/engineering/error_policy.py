"""Unified soft-error handling for runtime paths.

This module centralizes three behaviors:
1) structured warning logs (with lightweight rate limiting),
2) context metrics updates, and
3) optional strict-mode escalation.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from ..context.context_keys import KEY_METRICS, KEY_METRICS_SOFT_ERROR_COUNT, KEY_METRICS_SOFT_ERROR_LAST

_SOFT_ERROR_LAST_EMIT_AT: Dict[str, float] = {}


def _safe_context_store_update(
    context_store: Any,
    *,
    component: str,
    event: str,
    error_type: str,
    message: str,
) -> None:
    if context_store is None:
        return
    try:
        metrics = context_store.get(KEY_METRICS)
    except Exception:
        return
    if not isinstance(metrics, dict):
        metrics = {}
    count_map = metrics.get(KEY_METRICS_SOFT_ERROR_COUNT)
    if not isinstance(count_map, dict):
        count_map = {}
    bucket = f"{component}.{event}"
    count_map[bucket] = int(count_map.get(bucket, 0) or 0) + 1
    metrics[KEY_METRICS_SOFT_ERROR_COUNT] = count_map
    metrics[KEY_METRICS_SOFT_ERROR_LAST] = {
        "component": str(component),
        "event": str(event),
        "error_type": str(error_type),
        "message": str(message),
        "ts": float(time.time()),
    }
    try:
        context_store.set(KEY_METRICS, metrics)
    except Exception:
        return


def report_soft_error(
    *,
    component: str,
    event: str,
    exc: Exception,
    logger: Optional[logging.Logger] = None,
    context_store: Any = None,
    strict: bool = False,
    level: str = "warning",
    min_interval_seconds: float = 30.0,
) -> None:
    """Record a soft error with logging + metrics, or raise in strict mode."""
    if strict:
        raise exc

    log = logger or logging.getLogger(str(component))
    error_type = exc.__class__.__name__
    message = str(exc)
    emit_key = f"{component}|{event}|{error_type}"
    now = time.time()
    last = _SOFT_ERROR_LAST_EMIT_AT.get(emit_key, 0.0)
    should_emit = (now - last) >= max(0.0, float(min_interval_seconds))
    if should_emit:
        _SOFT_ERROR_LAST_EMIT_AT[emit_key] = now
        text = f"[soft-error] {component}.{event}: {error_type}: {message}"
        if level == "debug":
            log.debug(text)
        elif level == "info":
            log.info(text)
        elif level == "error":
            log.error(text)
        else:
            log.warning(text)

    _safe_context_store_update(
        context_store,
        component=str(component),
        event=str(event),
        error_type=str(error_type),
        message=str(message),
    )

