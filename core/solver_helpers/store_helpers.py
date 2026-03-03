"""Store construction helpers used by SolverBase."""

from __future__ import annotations

from typing import Any, Callable, Optional

from ...utils.context.context_store import ContextStore, create_context_store
from ...utils.context.snapshot_store import SnapshotStore, create_snapshot_store


def build_context_store_or_memory(
    *,
    backend: str,
    ttl_seconds: Optional[float],
    redis_url: str,
    key_prefix: str,
    report_soft_error_fn: Callable[..., Any],
    logger: Any,
) -> ContextStore:
    try:
        return create_context_store(
            backend=backend,
            ttl_seconds=ttl_seconds,
            redis_url=redis_url,
            key_prefix=key_prefix,
        )
    except Exception as exc:
        report_soft_error_fn(
            component="SolverBase",
            event="build_context_store",
            exc=exc,
            logger=logger,
            context_store=None,
            strict=False,
        )
        return create_context_store(backend="memory", ttl_seconds=ttl_seconds)


def build_snapshot_store_or_memory(
    *,
    backend: str,
    ttl_seconds: Optional[float],
    redis_url: str,
    key_prefix: str,
    base_dir: str,
    serializer: str,
    hmac_env_var: str,
    unsafe_allow_unsigned: bool,
    max_payload_bytes: int,
    context_store: Optional[ContextStore],
    report_soft_error_fn: Callable[..., Any],
    logger: Any,
) -> SnapshotStore:
    try:
        return create_snapshot_store(
            backend=backend,
            ttl_seconds=ttl_seconds,
            redis_url=redis_url,
            key_prefix=key_prefix,
            base_dir=base_dir,
            serializer=serializer,
            hmac_env_var=hmac_env_var,
            unsafe_allow_unsigned=unsafe_allow_unsigned,
            max_payload_bytes=max_payload_bytes,
        )
    except Exception as exc:
        report_soft_error_fn(
            component="SolverBase",
            event="build_snapshot_store",
            exc=exc,
            logger=logger,
            context_store=context_store,
            strict=False,
        )
        return create_snapshot_store(backend="memory", ttl_seconds=ttl_seconds)
