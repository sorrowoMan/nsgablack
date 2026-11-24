"""Explicit data codecs for the pipeline and its declared operator owners.

Never copy an operator object, a kernel, a lock, or arbitrary __dict__ graphs.
Shared operators are captured once, with their slot aliases retained.
"""
import copy
from collections.abc import Mapping

import numpy as np
from blackbase.context.redis_codec import canonical_safe_value_bytes


class PipelineStateMixin:
    def _state_owners(self):
        slots = [("initializer", self._initializer), ("mutator", self._mutator),
                 ("repair", self._repair), ("encoder", self._encoder),
                 ("decoder", self._decoder), ("crossover", self.crossover)]
        slots += [(f"initializers/{i}", item[0]) for i, item in enumerate(self.initializers)]
        slots += [(f"mutation_operators/{name}", value) for name, value in sorted(self._mutation_operators.items())]
        owners, aliases, seen = {}, {}, {}
        for slot, component in slots:
            if component is None:
                continue
            owner = seen.setdefault(id(component), slot)
            aliases[slot] = owner
            owners[owner] = component
        return owners, aliases

    @property
    def checkpoint_required(self):
        owners, _ = self._state_owners()
        return bool(self.initializers) or any(callable(getattr(c, "get_state", None))
                                              for c in owners.values())

    def checkpoint_identity(self):
        owners, aliases = self._state_owners()
        descriptions = {}
        for owner, component in owners.items():
            identity = getattr(component, "checkpoint_identity", None)
            descriptions[owner] = {
                "type": f"{type(component).__module__}.{type(component).__qualname__}",
                "identity": dict(identity()) if callable(identity) else None,
            }
        return {"schema": "nsgablack.pipeline_identity/v1", "aliases": aliases,
                "operators": descriptions, "initialization_weights": [float(x[1]) for x in self.initializers],
                "max_init_attempts": self.max_init_attempts, "validate_constraints": self.validate_constraints,
                "protect_input": self.protect_input, "copy_context": self.copy_context,
                "transactional": self.transactional, "threadsafe": self.threadsafe}

    def get_state(self):
        owners, _ = self._state_owners()
        states = {}
        for owner, component in owners.items():
            getter, setter = getattr(component, "get_state", None), getattr(component, "set_state", None)
            if callable(getter) != callable(setter):
                raise TypeError(f"pipeline operator {owner} requires both get_state and set_state")
            if callable(getter):
                state = getter()
                if not isinstance(state, Mapping):
                    raise TypeError(f"pipeline operator {owner} state must be a Mapping")
                states[owner] = copy.deepcopy(dict(state))
            elif getattr(component, "stateless", None) is False:
                raise TypeError(f"stateful pipeline operator {owner} has no explicit state codec")
        return {"schema": "nsgablack.pipeline_state/v1", "identity": self.checkpoint_identity(),
                "random_seed": self._random_seed, "rng": copy.deepcopy(self._rng.bit_generator.state),
                "operators": states}

    def set_state(self, state):
        if not isinstance(state, Mapping) or state.get("schema") != "nsgablack.pipeline_state/v1":
            raise ValueError("unsupported pipeline state schema")
        if canonical_safe_value_bytes(state.get("identity")) != canonical_safe_value_bytes(self.checkpoint_identity()):
            raise ValueError("pipeline component configuration or alias layout mismatch")
        owners, _ = self._state_owners()
        before = self.get_state()
        incoming = state.get("operators")
        if not isinstance(incoming, Mapping) or set(incoming) != set(before["operators"]):
            raise ValueError("pipeline operator state set mismatch")
        rng = np.random.default_rng()
        rng.bit_generator.state = copy.deepcopy(state["rng"])
        attempted = []
        try:
            for owner, value in incoming.items():
                if not isinstance(value, Mapping):
                    raise TypeError(f"pipeline operator {owner} state must be a Mapping")
                attempted.append(owner)
                owners[owner].set_state(copy.deepcopy(dict(value)))
        except BaseException:
            for owner in reversed(attempted):
                owners[owner].set_state(copy.deepcopy(before["operators"][owner]))
            raise
        self._rng = rng
        self._random_seed = state.get("random_seed")
