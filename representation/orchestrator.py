"""Unified orchestration controller for representation pipeline operators.

This module keeps strategy orchestration in `representation/` layer, so solver
or adapters do not need to embed operator-routing logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence, Tuple

import numpy as np

from .base import RepresentationComponentContract
from ..core.state.context_keys import KEY_GENERATION, KEY_PHASE, KEY_STRATEGY_ID, KEY_VNS_K


def _call_operator(operator: Any, method: str, x: Any, context: Optional[dict]) -> Any:
    fn = getattr(operator, method, None)
    if not callable(fn):
        raise TypeError(f"Operator {type(operator).__name__} has no callable {method}()")
    return fn(x, context)


@dataclass
class OrchestrationPolicy(RepresentationComponentContract):
    """Policy descriptor for orchestrating representation operators.

    mode:
      - serial: apply operators in order
      - switch: choose operator by index key from context
      - router: choose operator by route key from context
      - dynamic: choose stage operator by generation threshold
    """

    mode: str = "serial"
    operators: Sequence[Any] = field(default_factory=tuple)
    routes: Mapping[str, Any] = field(default_factory=dict)
    stages: Sequence[Tuple[int, Any]] = field(default_factory=tuple)
    selector_key: str = KEY_STRATEGY_ID
    index_key: str = KEY_VNS_K
    default_operator: Optional[Any] = None
    strict: bool = True
    context_requires = (KEY_VNS_K, KEY_STRATEGY_ID, KEY_PHASE, KEY_GENERATION)
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "Unified representation orchestration policy for serial/switch/router/dynamic modes.",
    )

    def __post_init__(self) -> None:
        self.mode = str(self.mode or "serial").strip().lower()
        self._routes = {str(k): v for k, v in dict(self.routes or {}).items()}
        self._stages = sorted([(int(s), op) for s, op in tuple(self.stages or ())], key=lambda x: x[0])


@dataclass
class PipelineOrchestrator(RepresentationComponentContract):
    """Representation-layer unified controller for mutate/repair orchestration."""

    mutate_policy: Optional[OrchestrationPolicy] = None
    repair_policy: Optional[OrchestrationPolicy] = None
    mutator: Optional[Any] = None
    repair_operator: Optional[Any] = None
    strict: bool = True

    context_key: str = KEY_PHASE
    k_key: str = KEY_VNS_K
    selector_key: str = KEY_STRATEGY_ID

    context_requires = (KEY_VNS_K, KEY_STRATEGY_ID, KEY_PHASE, KEY_GENERATION)
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "Unifies ContextSwitch/Router/Serial/Dynamic orchestration into one representation controller.",
    )

    def mutate(self, x: np.ndarray, context: Optional[dict] = None) -> np.ndarray:
        out = self._run_policy(self.mutate_policy, x, context, method="mutate", fallback=self.mutator)
        return np.asarray(out, dtype=float)

    def repair(self, x: Any, context: Optional[dict] = None) -> Any:
        return self._run_policy(self.repair_policy, x, context, method="repair", fallback=self.repair_operator)

    def _run_policy(
        self,
        policy: Optional[OrchestrationPolicy],
        x: Any,
        context: Optional[dict],
        *,
        method: str,
        fallback: Optional[Any],
    ) -> Any:
        if policy is None:
            if fallback is None:
                return x
            return _call_operator(fallback, method, x, context)

        mode = str(policy.mode or "serial").strip().lower()
        local_strict = bool(policy.strict if policy.strict is not None else self.strict)

        if mode == "serial":
            out = x
            for op in tuple(policy.operators or ()):  # type: ignore[arg-type]
                try:
                    out = _call_operator(op, method, out, context)
                except Exception:
                    if local_strict:
                        raise
                    return out
            return out

        if mode == "switch":
            ops = tuple(policy.operators or ())
            if not ops:
                return x
            idx = 0
            if isinstance(context, dict):
                try:
                    idx = int(context.get(policy.index_key, 0))
                except Exception:
                    idx = 0
            idx = max(0, min(idx, len(ops) - 1))
            return _call_operator(ops[idx], method, x, context)

        if mode == "router":
            selector = None
            if isinstance(context, dict):
                selector = context.get(policy.selector_key)
            if selector is not None:
                op = policy._routes.get(str(selector))
                if op is not None:
                    return _call_operator(op, method, x, context)
            if policy.default_operator is not None:
                return _call_operator(policy.default_operator, method, x, context)
            if local_strict:
                raise KeyError(
                    f"PipelineOrchestrator route not found: selector_key={policy.selector_key!r}, value={selector!r}"
                )
            return x

        if mode == "dynamic":
            gen = 0
            if isinstance(context, dict):
                try:
                    gen = int(context.get(KEY_GENERATION, 0))
                except Exception:
                    gen = 0
            chosen = None
            for start, op in policy._stages:
                if gen >= int(start):
                    chosen = op
                else:
                    break
            if chosen is not None:
                return _call_operator(chosen, method, x, context)
            if policy.default_operator is not None:
                return _call_operator(policy.default_operator, method, x, context)
            return x

        raise ValueError(f"unsupported orchestration mode: {mode}")
