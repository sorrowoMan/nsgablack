"""Search-side construction contracts, independent of Solver and ML semantics."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Callable, Mapping

import numpy as np
from blackbase.types import UnknownState
from .wire import detach_codec_payload


@dataclass(frozen=True)
class UnitSchema:
    name: str
    version: int = 1
    required_fields: tuple[str, ...] = ()
    candidate_projection: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip() or type(self.version) is not int or self.version < 1:
            raise ValueError("Unit schema needs a name and a positive version")
        if type(self.candidate_projection) is not bool:
            raise TypeError("Unit schema candidate_projection must be boolean")
        if isinstance(self.required_fields, str):
            raise TypeError("Unit schema required_fields must be a sequence of names")
        fields = tuple(self.required_fields)
        if any(not isinstance(name, str) or not name.strip() for name in fields) or len(set(fields)) != len(fields):
            raise ValueError("Unit schema field names must be unique nonempty strings")
        object.__setattr__(self, "required_fields", fields)

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "version": self.version,
                "required_fields": list(self.required_fields),
                "candidate_projection": self.candidate_projection}


@dataclass(frozen=True)
class UnitBuildRequest:
    unit_id: str
    candidate: Any
    purpose: str = "fresh"
    parameters: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.unit_id, str) or not self.unit_id:
            raise ValueError("Unit construction requires a nonempty unit_id")
        if self.purpose not in {"fresh", "spawn", "refresh"}:
            raise ValueError("Use the codec restore path for saved Units")
        values = candidate_array(self.candidate)
        if not isinstance(self.candidate, UnknownState):
            values = np.array(values, copy=True)
            values.setflags(write=False)
            object.__setattr__(self, "candidate", values)
        object.__setattr__(self, "parameters", MappingProxyType({
            key: _detach_parameter(value) for key, value in self.parameters.items()}))


def candidate_array(candidate: Any) -> np.ndarray:
    values = candidate.as_array() if isinstance(candidate, UnknownState) else np.asarray(candidate)
    if values.ndim != 1 or values.dtype.kind not in "biuf":
        raise ValueError("Unit candidate projection must be a one-dimensional numeric state")
    return values


@dataclass(frozen=True)
class StructureBuildRequest:
    """Construct a compound structure without pretending it is one candidate."""

    unit_id: str
    parameters: Mapping[str, Any] = field(default_factory=dict)
    operation: str = "initialize"

    def __post_init__(self) -> None:
        if not isinstance(self.unit_id, str) or not self.unit_id:
            raise ValueError("Structure construction requires a stable unit_id")
        if not isinstance(self.operation, str) or not self.operation:
            raise ValueError("Structure construction requires an operation")
        object.__setattr__(self, "parameters", MappingProxyType({
            key: _detach_parameter(value) for key, value in self.parameters.items()}))


def _detach_parameter(value):
    """Detach declared data only; a builder cannot corrupt the previous Unit."""
    if isinstance(value, np.ndarray):
        out = np.array(value, copy=True)
        out.setflags(write=False)
        return out
    if isinstance(value, UnknownState):
        return value
    if isinstance(value, Mapping):
        return {key: _detach_parameter(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return type(value)(_detach_parameter(item) for item in value)
    if value is None or isinstance(value, (str, bytes, bool, int, float, np.generic)):
        return value
    raise TypeError(f"Unit construction request cannot contain runtime services: {type(value).__name__}")


@dataclass(frozen=True)
class UnitBinding:
    """Bind construction plus a codec, without owning mutable search state.

    Builders must be stateless. Random choices and IDs are supplied by the
    Adapter. A kernel runner may replace construction; restoration always uses
    the explicit codec, never a fresh stochastic pipeline invocation.
    """

    builder: Any
    runner: Callable | None = field(default=None, repr=False, compare=False)
    name: str | None = None
    operations: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        if not isinstance(getattr(self.builder, "schema", None), UnitSchema):
            raise TypeError("Unit builder must declare a UnitSchema")
        for method in ("build", "dump", "restore"):
            if not callable(getattr(self.builder, method, None)):
                raise TypeError(f"Unit builder must implement {method}()")
        if self.runner is not None and not callable(self.runner):
            raise TypeError("Unit runner must be callable")
        if self.runner is not None and (not isinstance(self.name, str) or not self.name.strip()):
            raise ValueError("Custom Unit runners require a stable binding name")
        operations = self.operations
        if operations is None:
            operations = getattr(self.builder, "supported_operations", ())
        if isinstance(operations, str):
            raise TypeError("Unit operations must be a sequence of names")
        operations = tuple(operations)
        if any(not isinstance(op, str) or not op.strip() for op in operations):
            raise ValueError("Unit operation names must be nonempty strings")
        object.__setattr__(self, "operations", tuple(sorted(set(operations))))
        self._compatible_schemas()

    @property
    def schema(self) -> UnitSchema:
        return self.builder.schema

    def _compatible_schemas(self) -> tuple[UnitSchema, ...]:
        schemas = tuple(getattr(self.builder, "compatible_schemas", ()))
        for target in schemas:
            if not isinstance(target, UnitSchema):
                raise TypeError("Compatible Unit schemas must be complete UnitSchema declarations")
            if target.candidate_projection != self.schema.candidate_projection:
                raise ValueError("Compatible Unit schemas must use the same candidate projection")
            if not set(target.required_fields).issubset(self.schema.required_fields):
                raise ValueError("Compatible Unit schema requires fields absent from the provided schema")
        return schemas

    def require(self, schema: UnitSchema, *, operations=(), builder_methods=()) -> None:
        if not isinstance(schema, UnitSchema):
            raise TypeError("Expected a required UnitSchema")
        if self.schema != schema and schema not in self._compatible_schemas():
            raise ValueError(f"Unit schema mismatch: requires {schema.name}/v{schema.version}, "
                             f"got {self.schema.name}/v{self.schema.version}")
        missing = set(operations) - set(self.operations)
        if missing:
            raise ValueError(f"Unit binding lacks required build operations: {', '.join(sorted(missing))}")
        for method in builder_methods:
            if not callable(getattr(self.builder, method, None)):
                raise TypeError(f"Unit builder must implement required method {method}()")

    def describe_requirement(self, schema: UnitSchema, *, operations=(), builder_methods=()) -> dict[str, Any]:
        self.require(schema, operations=operations, builder_methods=builder_methods)
        return {
            "requires": schema.as_dict(),
            "match": "exact" if self.schema == schema else "declared-compatible",
            "compatible_schemas": [s.as_dict() for s in self._compatible_schemas()],
            "required_operations": sorted(operations),
            "available_operations": list(self.operations),
            "required_builder_methods": sorted(builder_methods),
        }

    def describe(self) -> dict[str, Any]:
        # The actual structure/codec identity is independent of which Adapter
        # consumes it. Compatibility never authorizes checkpoint conversion.
        cls = type(self.builder)
        return {"schema": self.schema.as_dict(),
                "binding": self.name or f"{cls.__module__}.{cls.__qualname__}"}

    def validate(self, unit: Any) -> None:
        if getattr(unit, "schema", None) != self.schema:
            raise ValueError("Built Unit does not match the binding schema")
        if not isinstance(getattr(unit, "unit_id", None), str) or not unit.unit_id:
            raise ValueError("Built Unit has no stable unit_id")
        for name in self.schema.required_fields:
            if not hasattr(unit, name):
                raise ValueError(f"Built Unit lacks required field {name!r}")
        if self.schema.candidate_projection:
            if not callable(getattr(unit, "to_candidate", None)):
                raise TypeError("Unit must explicitly project to a candidate")
            candidate_array(unit.to_candidate())
        validate = getattr(unit, "validate", None)
        if callable(validate):
            validate()

    def build(self, request: UnitBuildRequest | StructureBuildRequest, context: Mapping[str, Any] | None = None) -> Any:
        expected = UnitBuildRequest if self.schema.candidate_projection else StructureBuildRequest
        if not isinstance(request, expected):
            raise TypeError(f"Unit construction requires {expected.__name__}")
        operation = request.purpose if self.schema.candidate_projection else request.operation
        if operation not in self.operations:
            raise ValueError(f"Unit binding does not declare build operation: {operation}")
        unit = (self.runner or self.builder.build)(request, dict(context or {}))
        self.validate(unit)
        if unit.unit_id != request.unit_id:
            raise ValueError("Unit builder changed the requested identity")
        if not self.schema.candidate_projection:
            return unit
        projected = unit.to_candidate()
        if not np.array_equal(candidate_array(projected), candidate_array(request.candidate), equal_nan=True):
            raise ValueError("Unit construction must preserve the candidate; use the problem repair pipeline")
        if isinstance(request.candidate, UnknownState):
            if not isinstance(projected, UnknownState) or projected.as_dict()["metadata"] != request.candidate.as_dict()["metadata"]:
                raise ValueError("Unit construction lost candidate semantic metadata")
        return unit

    def dump(self, unit: Any) -> dict[str, Any]:
        self.validate(unit)
        return {"contract": self.describe(), "unit_id": unit.unit_id,
                "payload": detach_codec_payload(self.builder.dump(unit))}

    def restore(self, saved: Mapping[str, Any]) -> Any:
        if saved.get("contract") != self.describe():
            raise ValueError("Saved Unit binding/schema differs from the configured binding")
        unit = self.builder.restore(detach_codec_payload(saved["payload"]))
        self.validate(unit)
        if "unit_id" in saved and unit.unit_id != saved["unit_id"]:
            raise ValueError("Unit codec restore changed the saved identity")
        return unit
