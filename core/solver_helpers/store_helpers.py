"""Store helper utilities for SolverBase."""

from __future__ import annotations

from typing import Any, Mapping, Optional

from blackbase.context import ContextStore, SnapshotStore, create_context_store, create_snapshot_store


def _report_soft_error(report_fn: Any, **payload: Any) -> None:
    if callable(report_fn):
        report_fn(**payload)


def build_context_store_or_memory(
    config: Optional[Mapping[str, Any]] = None,
    **kwargs: Any,
) -> ContextStore:
    """Build context store with memory fallback on backend failure."""
    cfg = dict(config or {})
    cfg.update({k: v for k, v in kwargs.items() if v is not None})
    report_fn = cfg.pop("report_soft_error_fn", None)
    logger = cfg.pop("logger", None)
    backend = str(cfg.pop("backend", "memory") or "memory")
    try:
        return create_context_store(backend=backend, **cfg)
    except Exception as exc:
        _report_soft_error(
            report_fn,
            component="SolverBase",
            event="context_store_build_fallback",
            exc=exc,
            logger=logger,
            context_store=None,
            strict=False,
        )
        return create_context_store(backend="memory")


def build_snapshot_store_or_memory(
    config: Optional[Mapping[str, Any]] = None,
    **kwargs: Any,
) -> SnapshotStore:
    """Build snapshot store with memory fallback on backend failure."""
    cfg = dict(config or {})
    cfg.update({k: v for k, v in kwargs.items() if v is not None})
    report_fn = cfg.pop("report_soft_error_fn", None)
    logger = cfg.pop("logger", None)
    context_store = cfg.pop("context_store", None)
    backend = str(cfg.pop("backend", "memory") or "memory")
    try:
        return create_snapshot_store(backend=backend, **cfg)
    except Exception as exc:
        _report_soft_error(
            report_fn,
            component="SolverBase",
            event="snapshot_store_build_fallback",
            exc=exc,
            logger=logger,
            context_store=context_store,
            strict=False,
        )
        return create_snapshot_store(backend="memory")


__all__ = [
    "build_context_store_or_memory",
    "build_snapshot_store_or_memory",
]
