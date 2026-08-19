"""Thin nsgablack topology adapter for blackbase runtime projection aggregation."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from blackbase.context import (
    RuntimeProjectionAggregation,
    RuntimeProjectionComponent,
    aggregate_runtime_projections,
)


def aggregate_adapter_runtime_projections(
    control: Any,
    *,
    owner_source: str,
    own_fields: Mapping[Any, Any] | None = None,
    children: Sequence[tuple[str, Any]] = (),
) -> RuntimeProjectionAggregation:
    """Declare Adapter topology and delegate all aggregation mechanics to blackbase."""

    initial_fields = own_fields.items() if own_fields is not None else ()
    fields = {
        str(key): value
        for key, value in initial_fields
        if key is not None and value is not None
    }
    components = []
    for source, adapter in children:
        getter = getattr(adapter, "get_runtime_context_projection", None)
        components.append(
            RuntimeProjectionComponent(
                component=str(source),
                projector=getter if callable(getter) else None,
            )
        )
    return aggregate_runtime_projections(
        control,
        tuple(components),
        fields=fields,
        field_sources={key: str(owner_source) for key in fields},
    )


__all__ = ["aggregate_adapter_runtime_projections"]
