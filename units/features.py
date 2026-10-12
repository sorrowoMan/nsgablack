"""Derived Unit data with explicit dependencies; never search state or services."""
from __future__ import annotations

from dataclasses import dataclass, fields
import hashlib
import json
from types import MappingProxyType
from typing import Callable, ClassVar, Mapping

import numpy as np
from blackbase.types import UnknownState


class FeatureContractError(ValueError):
    """A feature's declared inputs cannot support a valid value."""


def _readonly(value):
    if isinstance(value, np.ndarray):
        return np.frombuffer(value.tobytes(), dtype=value.dtype).reshape(value.shape)
    if isinstance(value, Mapping):
        return MappingProxyType({k: _readonly(v) for k, v in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(_readonly(v) for v in value)
    if isinstance(value, UnknownState):
        return UnknownState.from_protocol_payload(value.as_dict())
    return value


def _snapshot(value):
    # Reuse the closed Unit data codec, without copying an owner or its services.
    from ..representation.structure_builders import encode_unit_value, decode_unit_value
    encoded = encode_unit_value(value)
    digest = hashlib.sha256(json.dumps(encoded, sort_keys=True).encode()).hexdigest()
    return digest, _readonly(decode_unit_value(encoded))


def _signature(value):
    from ..representation.structure_builders import encode_unit_value
    return hashlib.sha256(json.dumps(encode_unit_value(value), sort_keys=True).encode()).hexdigest()


@dataclass(frozen=True)
class UnitFeature:
    """Pure computation over named Unit fields, optionally incrementally maintained.

    update(inputs, previous_inputs, previous_value) must equal compute(inputs).
    Missing dependencies are errors; an uncomputed value is never a numeric zero.
    """

    name: str
    depends_on: tuple[str, ...]
    compute: Callable
    feedback_view: str = "none"
    update: Callable | None = None

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name.strip():
            raise FeatureContractError("Feature requires a nonempty name")
        if isinstance(self.depends_on, str):
            raise FeatureContractError("Feature dependencies must be field names")
        names = tuple(self.depends_on)
        if not names or any(not isinstance(n, str) or not n for n in names) or len(set(names)) != len(names):
            raise FeatureContractError("Feature requires unique, explicit dependencies")
        if not callable(self.compute) or (self.update is not None and not callable(self.update)):
            raise FeatureContractError("Feature compute/update must be callable")
        if self.feedback_view not in {"none", "raw", "selection"}:
            raise FeatureContractError("Feature feedback_view must be none, raw or selection")
        object.__setattr__(self, "depends_on", names)

    def validate_for(self, unit):
        declared = {f.name for f in fields(unit)}
        missing = set(self.depends_on) - declared
        if missing:
            raise FeatureContractError(f"Feature {self.name} has undeclared Unit fields: {sorted(missing)}")
        views = getattr(unit, "feature_feedback_fields", {})
        used = {views[n] for n in self.depends_on if n in views}
        expected = set() if self.feedback_view == "none" else {self.feedback_view}
        if used != expected:
            raise FeatureContractError(f"Feature {self.name} feedback view disagrees with its dependencies")


class FeatureUnit:
    """Optional derived features owned by this exact Unit instance.

    Cache entries are deliberately not dataclass fields or checkpoint state.
    Reads compare dependency content, including legacy in-place array edits.
    Owners serialize mutations with reads; this is not a concurrent-write lock.
    """

    feature_feedback_fields: ClassVar[Mapping[str, str]] = MappingProxyType({})

    def clear_features(self):
        object.__setattr__(self, "_unit_feature_cache", {})

    def validate_feature_inputs(self, spec):
        """An owner may reject stale authoritative inputs before any cache read."""
        return None

    def feature(self, spec: UnitFeature, *, cache: bool = True):
        if not isinstance(spec, UnitFeature):
            raise FeatureContractError("Expected a UnitFeature declaration")
        spec.validate_for(self)
        self.validate_feature_inputs(spec)
        if getattr(self, "_unit_feature_computing", False):
            raise FeatureContractError("Feature computations must use declared fields, not nested features")

        def capture():
            return _snapshot({"unit_id": self.unit_id, "schema": self.schema.as_dict(),
                              "inputs": {n: getattr(self, n) for n in spec.depends_on}})

        signature, source = capture()
        entries = getattr(self, "_unit_feature_cache", None)
        if entries is None:
            self.clear_features()
            entries = self._unit_feature_cache
        previous = entries.get(spec.name) if cache else None
        if previous is not None and previous[0] is spec and previous[1] == signature:
            return previous[3]
        inputs = source["inputs"]
        object.__setattr__(self, "_unit_feature_computing", True)
        try:
            if previous is not None and previous[0] is spec and spec.update is not None:
                value = spec.update(inputs, previous[2], previous[3])
            else:
                value = spec.compute(inputs)
            _, value = _snapshot(value)
            if capture()[0] != signature:
                raise FeatureContractError(f"Feature {spec.name} dependencies changed during computation")
        finally:
            object.__setattr__(self, "_unit_feature_computing", False)
        if cache:
            entries[spec.name] = (spec, signature, inputs, value)
        return value
