"""Explicit, detached Unit dependencies for candidate operators."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Any
import inspect

from .contracts import UnitSchema
from .features import UnitFeature, FeatureContractError, _snapshot


@dataclass(frozen=True)
class UnitInputs:
    unit_id: str
    schema: UnitSchema
    revision: str
    fields: Mapping[str, Any]
    features: Mapping[str, Any]

    def __post_init__(self):
        _, values = _snapshot({"fields": self.fields, "features": self.features})
        object.__setattr__(self, "fields", values["fields"])
        object.__setattr__(self, "features", values["features"])


@dataclass(frozen=True)
class UnitInputSpec:
    """A mutator declares only the fields/features it actually consumes.

    schema is an optional exact requirement; field-only declarations can be
    reused across richer Unit types. Feedback fields require an explicit view.
    """
    fields: tuple[str, ...] = ()
    features: tuple[UnitFeature, ...] = ()
    feedback_view: str = "none"
    schema: UnitSchema | None = None

    def __post_init__(self):
        if isinstance(self.fields, str):
            raise TypeError("Unit input fields must be a sequence of names")
        names, features = tuple(self.fields), tuple(self.features)
        if (any(not isinstance(n, str) or not n for n in names) or len(set(names)) != len(names)
                or any(not isinstance(f, UnitFeature) for f in features)):
            raise ValueError("Unit inputs require unique field names and UnitFeature declarations")
        if len({f.name for f in features}) != len(features) or not (names or features):
            raise ValueError("Unit inputs require nonempty dependencies and unique feature names")
        if self.feedback_view not in {"none", "raw", "selection"} or (not names and self.feedback_view != "none"):
            raise ValueError("Unit input feedback view must describe its direct fields")
        if self.schema is not None and not isinstance(self.schema, UnitSchema):
            raise TypeError("Unit input schema must be a UnitSchema")
        object.__setattr__(self, "fields", names)
        object.__setattr__(self, "features", features)

    def _field_spec(self):
        return UnitFeature("operator.inputs", self.fields, lambda values: values,
                           feedback_view=self.feedback_view)

    def validate_for(self, unit):
        if unit is None:
            raise FeatureContractError("Unit-aware mutation requires an explicit owning Unit")
        if self.schema is not None and unit.schema != self.schema:
            raise FeatureContractError("Unit operator schema does not match its owner")
        if self.fields:
            self._field_spec().validate_for(unit)
        for feature in self.features:
            feature.validate_for(unit)

    def capture(self, unit):
        self.validate_for(unit)
        if self.fields:
            unit.validate_feature_inputs(self._field_spec())
        dependencies = set(self.fields).union(*(set(f.depends_on) for f in self.features))
        def source():
            return _snapshot({"unit_id": unit.unit_id, "schema": unit.schema.as_dict(),
                              "fields": {name: getattr(unit, name) for name in dependencies}})
        revision, original = source()
        features = {f.name: unit.feature(f) for f in self.features}
        if source()[0] != revision:
            raise FeatureContractError("Unit changed while capturing operator inputs")
        return UnitInputs(unit.unit_id, unit.schema, revision,
                          {name: original["fields"][name] for name in self.fields}, features)

    def validate_input(self, value):
        if not isinstance(value, UnitInputs):
            raise FeatureContractError("Unit-aware mutation requires UnitInputs")
        if (set(value.fields) != set(self.fields) or set(value.features) != {f.name for f in self.features}
                or (self.schema is not None and value.schema != self.schema)):
            raise FeatureContractError("UnitInputs do not match the operator's declared dependencies")


def mutation_unit_spec(operator):
    """Validate declarations without evaluating a feature or running an operator."""
    spec = getattr(operator, "unit_inputs", None)
    if spec is not None:
        if not isinstance(spec, UnitInputSpec):
            raise TypeError("mutator.unit_inputs must be UnitInputSpec")
        method = getattr(operator, "mutate", None)
        if not callable(method):
            raise TypeError("Unit-aware mutator must implement mutate(candidate, context, *, unit)")
        try:
            inspect.signature(method).bind(object(), {}, unit=object())
        except (TypeError, ValueError) as exc:
            raise TypeError("Unit-aware mutate must accept (candidate, context, *, unit)") from exc
    return spec


__all__ = ["UnitInputSpec", "UnitInputs"]
