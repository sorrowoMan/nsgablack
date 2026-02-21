"""
Dynamic penalty bias.

This bias scales a penalty over time (e.g., increasing constraint penalty as
iterations progress), without changing the search strategy itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Sequence
import inspect
import math
import numpy as np

from ..core.base import DomainBias, OptimizationContext


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


def _call_func(func: Callable[..., Any], x: np.ndarray, context: OptimizationContext) -> Any:
    try:
        sig = inspect.signature(func)
    except (TypeError, ValueError):
        return func(x)

    params = list(sig.parameters.values())
    argc = len(params)

    if argc <= 1:
        return func(x)
    if argc == 2:
        return func(x, context)

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
    return func(x, constraints, context_dict)


@dataclass
class DynamicPenaltyBias(DomainBias):
    """
    Dynamic penalty bias with a schedule over generations.

    Typical usage: increase constraint penalties over time so early search can
    explore, then later tighten feasibility pressure.
    """
    context_requires = ("problem_data",)
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Reads context fields: problem_data; outputs scalar bias only."



    penalty_func: Callable[..., Any] = None
    schedule: str = "linear"
    start_scale: float = 0.2
    end_scale: float = 1.0
    growth_rate: float = 1.0
    max_generations: Optional[int] = None
    step_generation: Optional[int] = None
    min_scale: Optional[float] = None
    max_scale: Optional[float] = None

    def __init__(
        self,
        name: str = "dynamic_penalty",
        *,
        penalty_func: Callable[..., Any],
        weight: float = 1.0,
        schedule: str = "linear",
        start_scale: float = 0.2,
        end_scale: float = 1.0,
        growth_rate: float = 1.0,
        max_generations: Optional[int] = None,
        step_generation: Optional[int] = None,
        min_scale: Optional[float] = None,
        max_scale: Optional[float] = None,
        mandatory: bool = False,
    ) -> None:
        super().__init__(name=name, weight=weight, mandatory=mandatory)
        self.penalty_func = penalty_func
        self.schedule = str(schedule or "linear").lower().strip()
        self.start_scale = float(start_scale)
        self.end_scale = float(end_scale)
        self.growth_rate = float(growth_rate)
        self.max_generations = max_generations
        self.step_generation = step_generation
        self.min_scale = min_scale
        self.max_scale = max_scale

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        raw = _coerce_value(_call_func(self.penalty_func, x, context))
        scale = self._schedule_scale(context)
        return float(raw) * float(scale)

    def _schedule_scale(self, context: OptimizationContext) -> float:
        gen = float(getattr(context, "generation", 0))
        max_g = self._resolve_max_generations(context)

        if self.schedule == "step":
            step = float(self.step_generation if self.step_generation is not None else max_g or 0.0)
            scale = self.end_scale if gen >= step else self.start_scale
        elif self.schedule == "exp":
            if max_g and max_g > 0:
                t = min(gen / max_g, 1.0)
            else:
                t = gen
            scale = self.start_scale * math.exp(self.growth_rate * t)
        elif self.schedule == "sigmoid":
            if max_g and max_g > 0:
                t = min(gen / max_g, 1.0)
            else:
                t = gen / max(1.0, gen + 1.0)
            k = max(1e-6, self.growth_rate)
            s = 1.0 / (1.0 + math.exp(-k * (t - 0.5)))
            scale = self.start_scale + (self.end_scale - self.start_scale) * s
        else:
            if max_g and max_g > 0:
                t = min(gen / max_g, 1.0)
            else:
                t = gen / max(1.0, gen + 1.0)
            scale = self.start_scale + (self.end_scale - self.start_scale) * t

        if self.min_scale is not None:
            scale = max(float(self.min_scale), scale)
        if self.max_scale is not None:
            scale = min(float(self.max_scale), scale)
        return float(scale)

    def _resolve_max_generations(self, context: OptimizationContext) -> Optional[int]:
        if self.max_generations is not None:
            return int(self.max_generations)
        try:
            metrics = getattr(context, "metrics", {}) or {}
            if "max_generations" in metrics:
                return int(metrics["max_generations"])
        except Exception:
            pass
        try:
            pdata = getattr(context, "problem_data", {}) or {}
            if "max_generations" in pdata:
                return int(pdata["max_generations"])
        except Exception:
            pass
        return None
