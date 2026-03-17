"""
Context-aware mutator helpers.

These helpers allow algorithm adapters (e.g. VNS) to control operator behavior
via the shared `context` dict without hard-coding representation details into
the adapter itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from .base import RepresentationComponentContract
from ..core.state.context_keys import KEY_PHASE, KEY_STRATEGY_ID, KEY_VNS_K


def _call_mutate(mutator: Any, x: np.ndarray, context: Optional[dict]) -> np.ndarray:
    fn = getattr(mutator, "mutate", None)
    if not callable(fn):
        raise TypeError(f"Mutator {type(mutator).__name__} has no callable mutate()")
    return np.asarray(fn(np.asarray(x), context), dtype=float)


@dataclass
class ContextSelectMutator(RepresentationComponentContract):
    """Select a mutator based on a context key (e.g. VNS neighborhood index).

    Typical usage:
      - Adapter writes `context["vns_k"] = k`
    - Pipeline uses `ContextSelectMutator(mutators=[...], k_key="vns_k")`
    """

    mutators: List[Any]
    k_key: str = KEY_VNS_K
    context_requires = (KEY_VNS_K,)
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "Reads neighborhood index from context and dispatches to the matching mutator.",
    )

    def mutate(self, x: np.ndarray, context: Optional[dict] = None) -> np.ndarray:
        if not self.mutators:
            return np.asarray(x)

        k = 0
        if context is not None:
            try:
                k = int(context.get(self.k_key, 0))
            except Exception:
                k = 0

        idx = max(0, min(k, len(self.mutators) - 1))
        return _call_mutate(self.mutators[idx], np.asarray(x), context)


@dataclass
class SerialMutator(RepresentationComponentContract):
    """Apply multiple mutators sequentially (m1 -> m2 -> ...)."""

    mutators: Sequence[Any]
    strict: bool = True
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "Serial mutator composes multiple mutate() operators in order.",
    )

    def mutate(self, x: np.ndarray, context: Optional[dict] = None) -> np.ndarray:
        out = np.asarray(x, dtype=float)
        if not self.mutators:
            return out
        for mutator in self.mutators:
            try:
                out = _call_mutate(mutator, out, context)
            except Exception:
                if self.strict:
                    raise
                return out
        return out


@dataclass
class ContextDispatchMutator(RepresentationComponentContract):
    """Route to different mutators by context key (e.g. strategy/phase)."""

    routes: Dict[str, Any] = field(default_factory=dict)
    selector_key: str = KEY_STRATEGY_ID
    default_mutator: Optional[Any] = None
    strict: bool = True
    context_requires = (KEY_STRATEGY_ID, KEY_PHASE)
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "Reads a selector key from context and dispatches mutator by route name.",
    )

    def mutate(self, x: np.ndarray, context: Optional[dict] = None) -> np.ndarray:
        selector = None
        if context is not None:
            selector = context.get(self.selector_key)

        if selector is not None:
            key = str(selector)
            mutator = self.routes.get(key)
            if mutator is not None:
                return _call_mutate(mutator, np.asarray(x), context)

        if self.default_mutator is not None:
            return _call_mutate(self.default_mutator, np.asarray(x), context)

        if self.strict:
            raise KeyError(
                f"ContextDispatchMutator route not found: selector_key={self.selector_key!r}, value={selector!r}"
            )
        return np.asarray(x, dtype=float)
