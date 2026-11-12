"""Explicit state ownership for an independently assembled algorithm operator.

Only values returned by the component's declared codec are detached. This
binding never traverses a component's object graph or copies runtime services.
The owning Adapter includes this state in its existing transaction/checkpoint.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np


def _detach(value, *, path="operator state", active=None):
    if value is None or type(value) in (str, bool, int, float, bytes):
        return value
    if isinstance(value, np.generic):
        return _detach(value.item(), path=path, active=active)
    if isinstance(value, np.ndarray):
        if value.dtype.kind not in "biuf":
            raise TypeError(f"{path}: only real numeric arrays are supported")
        return np.array(value, copy=True)
    if not isinstance(value, (Mapping, list, tuple)):
        raise TypeError(f"{path}: unsupported runtime object {type(value).__name__}")
    active = set() if active is None else active
    if id(value) in active:
        raise TypeError(f"{path}: cyclic codec values are unsupported")
    active.add(id(value))
    try:
        if isinstance(value, Mapping):
            if any(not isinstance(key, str) for key in value):
                raise TypeError(f"{path}: codec mapping keys must be strings")
            return {key: _detach(item, path=f"{path}.{key}", active=active)
                    for key, item in value.items()}
        items = [_detach(item, path=f"{path}[{index}]", active=active)
                 for index, item in enumerate(value)]
        return tuple(items) if isinstance(value, tuple) else items
    finally:
        active.remove(id(value))


def _same(left, right):
    if type(left) is not type(right):
        return False
    if isinstance(left, np.ndarray):
        return left.dtype == right.dtype and np.array_equal(left, right, equal_nan=True)
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(_same(left[key], right[key]) for key in left)
    if isinstance(left, (tuple, list)):
        return len(left) == len(right) and all(_same(a, b) for a, b in zip(left, right))
    return left == right


class OperatorBinding:
    """A method-bearing component with an explicit identity and safe state codec."""

    def __init__(self, component: Any, *, method: str):
        if not isinstance(method, str) or not method or not callable(getattr(component, method, None)):
            raise TypeError("OperatorBinding requires a callable declared method")
        stateless = getattr(component, "stateless", False)
        if type(stateless) is not bool:
            raise TypeError("operator.stateless must be an explicit bool")
        if not callable(getattr(component, "checkpoint_identity", None)):
            raise TypeError("operator requires checkpoint_identity()")
        if not stateless and not all(callable(getattr(component, name, None)) for name in ("get_state", "set_state")):
            raise TypeError("stateful operator requires explicit get_state()/set_state()")
        self._component, self._method, self._stateless = component, method, stateless
        self._identity = self._read_identity()
        self._read_state()

    @property
    def component(self):
        return self._component

    @property
    def stateless(self):
        return self._stateless

    @property
    def method(self):
        """Declared invocation method, inspectable without calling user code."""
        return self._method

    def _read_identity(self):
        identity = self.component.checkpoint_identity()
        if not isinstance(identity, Mapping) or not identity:
            raise TypeError("operator checkpoint_identity() must return a nonempty Mapping")
        return _detach(identity, path="operator identity")

    def _read_state(self):
        state = {} if self.stateless else self.component.get_state()
        if not isinstance(state, Mapping):
            raise TypeError("operator get_state() must return a Mapping")
        return _detach(state)

    def _header(self):
        if not _same(self._identity, self._read_identity()):
            raise ValueError("operator identity changed after binding")
        return {"schema": "nsgablack.operator_binding/v1", "method": self._method,
                "module": type(self.component).__module__, "class": type(self.component).__qualname__,
                "identity": _detach(self._identity), "stateless": self.stateless}

    def seed(self, seed: int | None) -> None:
        """Seed only an explicitly declared local RNG; do not infer ownership."""
        self._header()
        setter = getattr(self.component, "set_random_seed", None)
        if callable(setter):
            setter(seed)
        self._header()

    def get_state(self) -> Mapping[str, Any]:
        return {**self._header(), "state": self._read_state()}

    def describe(self) -> Mapping[str, Any]:
        """Detached configuration identity; excludes mutable state and RNG."""
        return self._header()

    def _validated_payload(self, state: Mapping[str, Any]):
        if not isinstance(state, Mapping):
            raise TypeError("operator binding state must be a Mapping")
        payload = _detach(state)
        header = self._header()
        if set(payload) != {*header, "state"} or not _same(
                {key: payload[key] for key in header}, header):
            raise ValueError("operator checkpoint identity does not match the bound component")
        if not isinstance(payload["state"], Mapping):
            raise TypeError("operator checkpoint payload must contain a Mapping state")
        if self.stateless:
            if payload["state"]:
                raise ValueError("stateless operator checkpoint cannot contain mutable state")
        return payload["state"]

    def validate_state(self, state: Mapping[str, Any]) -> None:
        """Validate the envelope without mutating any component state."""
        self._validated_payload(state)

    def set_state(self, state: Mapping[str, Any]) -> None:
        payload = self._validated_payload(state)
        if not self.stateless:
            self.component.set_state(payload)
