"""Thin nsgablack topology adapter for blackbase runtime projection aggregation."""

from __future__ import annotations

from typing import Any, Mapping, Sequence
from dataclasses import replace

from blackbase.context import (
    RuntimeProjectionAggregation,
    RuntimeProjectionComponent,
    RuntimeContextProjection,
    aggregate_runtime_projections,
)


def aggregate_adapter_runtime_projections(
    control: Any,
    *,
    owner_source: str,
    own_fields: Mapping[Any, Any] | None = None,
    children: Sequence[tuple[str, Any]] = (),
    scoped_keys: Sequence[str] = (),
    namespace_key: str | None = None,
) -> RuntimeProjectionAggregation:
    """Declare Adapter topology and delegate all aggregation mechanics to blackbase."""

    initial_fields = own_fields.items() if own_fields is not None else ()
    fields = {
        str(key): value
        for key, value in initial_fields
        if key is not None and value is not None
    }
    components = []
    scoped: dict[str, Any] = {}
    def scope_projector(getter, source):
        def project(control):
            value = getter(control)
            if not isinstance(value, Mapping):
                return value  # substrate reports invalid results
            if namespace_key is not None:
                scoped[source] = dict(value)
            visible = {key: item for key, item in value.items() if key not in scoped_keys}
            if isinstance(value, RuntimeContextProjection):
                return replace(value, fields=visible, field_sources={
                    key: source for key, source in value.field_sources.items() if key in visible
                })
            return visible
        return project
    for source, adapter in children:
        getter = getattr(adapter, "get_runtime_context_projection", None)
        components.append(
            RuntimeProjectionComponent(
                component=str(source),
                projector=(scope_projector(getter, str(source)) if callable(getter) else None),
            )
        )
    result = aggregate_runtime_projections(
        control,
        tuple(components),
        fields=fields,
        field_sources={key: str(owner_source) for key in fields},
    )
    if namespace_key is not None:
        result = RuntimeProjectionAggregation(replace(
            result.projection,
            fields={**result.projection.fields, namespace_key: scoped},
            field_sources={**result.field_sources, namespace_key: str(owner_source)},
        ))
    return result


__all__ = ["aggregate_adapter_runtime_projections"]
