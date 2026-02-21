"""Base classes for surrogate control biases."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class SurrogateBiasContext:
    """Context passed to surrogate control biases."""

    generation: int
    max_generations: int
    population: Optional[Any]
    surrogate_manager: Any
    surrogate_ready: bool
    n_training_samples: int
    model_quality: Dict[str, float]
    real_eval_count: int
    surrogate_eval_count: int
    prefilter: Dict[str, Any]
    score_bias: Dict[str, Any]
    surrogate_eval: Dict[str, Any]
    constraint_eval: Dict[str, Any]
    extras: Dict[str, Any] = field(default_factory=dict)

    @property
    def progress(self) -> float:
        if self.max_generations <= 0:
            return 0.0
        return float(self.generation) / float(self.max_generations)

    def get(self, key: str, default: Any = None) -> Any:
        if hasattr(self, key):
            return getattr(self, key)
        return self.extras.get(key, default)


class SurrogateControlBias:
    """Base class for surrogate control biases."""
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "No explicit context dependency; outputs scalar bias only."



    def __init__(self, name: str = "surrogate_control_bias"):
        self.name = name

    def should_apply(self, context: Any) -> bool:
        return True

    def apply(self, context: Any) -> Dict[str, Any]:
        return {}

    def __call__(self, context: Any) -> Dict[str, Any]:
        return self.apply(context)
