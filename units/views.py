"""Detached algorithm views for comparison; never a second writable owner."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from types import MappingProxyType
from typing import Any, Mapping

import numpy as np

from .contracts import UnitSchema
from .wire import detach_codec_payload
from .features import FeatureUnit


def _freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)
    return value


@dataclass(frozen=True)
class UnitView(FeatureUnit):
    """An instance-qualified, immutable codec view of one Unit revision."""

    owner_path: tuple[str, ...]
    unit_id: str
    schema: UnitSchema
    revision: str
    payload: Mapping[str, Any]

    def __post_init__(self):
        if isinstance(self.owner_path, str):
            raise TypeError("owner_path must be a sequence of instance names")
        path = tuple(self.owner_path)
        if not path or any(not isinstance(p, str) or not p.strip() for p in path):
            raise ValueError("Unit view requires a nonempty instance owner_path")
        if not isinstance(self.schema, UnitSchema):
            raise TypeError("Unit view requires a UnitSchema")
        if not isinstance(self.unit_id, str) or not self.unit_id.strip():
            raise ValueError("Unit view requires a stable unit_id")
        if not isinstance(self.revision, str) or not self.revision.strip():
            raise ValueError("Unit view requires an explicit revision")
        object.__setattr__(self, "owner_path", path)
        object.__setattr__(self, "payload", _freeze(detach_codec_payload(self.payload)))

    @property
    def identity(self):
        return self.owner_path, self.unit_id, self.schema

    @classmethod
    def capture(cls, unit, binding, *, owner_path):
        saved = binding.dump(unit)
        revision = hashlib.sha256(json.dumps(saved, sort_keys=True).encode()).hexdigest()
        return cls(owner_path, unit.unit_id, binding.schema, revision, saved["payload"])


@dataclass(frozen=True)
class PopulationView(UnitView):
    """Population capability with aligned membership identity, owned by an Adapter."""

    population: Any
    candidate_tokens: tuple[str | None, ...]

    def pairwise_distances(self, *, cache=True):
        from .population_features import POPULATION_DISTANCES
        return self.feature(POPULATION_DISTANCES, cache=cache)

    def __post_init__(self):
        super().__post_init__()
        values = np.asarray(self.population, dtype=float)
        if values.ndim != 2 or not np.all(np.isfinite(values)):
            raise ValueError("Population preference view requires a finite matrix")
        tokens = tuple(self.candidate_tokens) or (None,) * len(values)
        known = tuple(t for t in tokens if t is not None)
        if len(tokens) != len(values) or len(set(known)) != len(known):
            raise ValueError("Population preference view requires unique aligned tokens")
        if any(not isinstance(t, str) or not t for t in known):
            raise ValueError("Population preference view requires nonempty candidate tokens")
        # Immutable bytes backing prevents callers from re-enabling array writes.
        detached = np.frombuffer(values.tobytes(), dtype=float).reshape(values.shape)
        object.__setattr__(self, "population", detached)
        object.__setattr__(self, "candidate_tokens", tokens)

    @property
    def membership_identity_complete(self):
        """Draft initialization members have no fabricated candidate identity."""
        return all(token is not None for token in self.candidate_tokens)

    @classmethod
    def capture(cls, unit, binding, *, owner_path):
        base = UnitView.capture(unit, binding, owner_path=owner_path)
        if "population" not in binding.schema.required_fields:
            raise TypeError("Unit does not declare the population capability")
        values = unit.population
        if values is None:
            values = np.empty((0, 0))
        return cls(base.owner_path, base.unit_id, base.schema, base.revision,
                   binding.dump(unit)["payload"], values, unit.candidate_tokens)
