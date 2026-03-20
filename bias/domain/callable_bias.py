"""
Callable domain bias wrappers.

These biases exist to make "quick rules" first-class in the new bias system,
without resurrecting the old `add_penalty` / `add_reward` API.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Sequence
import inspect
import numpy as np
from nsgablack.catalog import CatalogEntry
from ..core.base import DomainBias, OptimizationContext


@dataclass
class CallableBias(DomainBias):
    """
    Wrap a user function as a DomainBias.

    - mode="penalty": positive values increase the objective (worse)
    - mode="reward": positive values decrease the objective (better)

    The wrapped callable may have one of the following signatures:
    - func(x) -> float | dict
    - func(x, context: OptimizationContext) -> float | dict
    - func(x, constraints: Sequence[dict], context_dict: dict) -> float | dict

    If a dict is returned, it will try to read keys: "penalty"/"reward"/"value".
    """
    context_requires = ("problem_data",)
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Reads context fields: problem_data; outputs scalar bias only."



    func: Callable[..., Any] = None
    mode: str = "penalty"

    def __init__(
        self,
        name: str,
        func: Callable[..., Any],
        weight: float = 1.0,
        *,
        mode: str = "penalty",
        mandatory: bool = False,
    ):
        super().__init__(name=name, weight=weight, mandatory=mandatory)
        self.func = func
        self.mode = mode

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        value = self._call_func(x, context)
        value = self._coerce_value(value)

        if self.mode == "reward":
            return -float(value)
        return float(value)

    def _call_func(self, x: np.ndarray, context: OptimizationContext) -> Any:
        try:
            sig = inspect.signature(self.func)
        except (TypeError, ValueError):
            return self.func(x)

        params = list(sig.parameters.values())
        argc = len(params)

        if argc <= 1:
            return self.func(x)
        if argc == 2:
            return self.func(x, context)

        constraints = []
        try:
            constraints = context.problem_data.get("constraints", [])  # type: ignore[attr-defined]
        except Exception:
            constraints = []

        context_dict: Dict[str, Any] = {
            "generation": getattr(context, "generation", 0),
            "metrics": getattr(context, "metrics", {}),
            "history": getattr(context, "history", []),
            "problem_data": getattr(context, "problem_data", {}),
            "constraints": constraints,
        }
        return self.func(x, constraints, context_dict)

    @staticmethod
    def _coerce_value(value: Any) -> float:
        if value is None:
            return 0.0
        if isinstance(value, (int, float, np.floating)):
            return float(value)
        if isinstance(value, dict):
            for key in ("penalty", "reward", "value"):
                if key in value:
                    try:
                        return float(value[key])
                    except Exception:
                        return 0.0
            return 0.0
        try:
            return float(value)
        except Exception:
            return 0.0
CATALOG_ENTRIES = [
    CatalogEntry(
        key="bias.callable",
        title="CallableBias",
        kind="bias",
        import_path="nsgablack.bias.domain.callable_bias:CallableBias",
        tags=("bias", "domain", "callable"),
        summary="Domain bias wrapper for user callables.",
    )
]
