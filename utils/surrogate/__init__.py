"""
Surrogate utilities (optional capability layer).

This package intentionally lives under `utils/`:
- It is not part of the solver "base" architecture.
- It exists to support optional plugins (e.g. SurrogateEvaluationPlugin).
"""

from .trainer import SurrogateTrainer, ModelType
from .vector_surrogate import VectorSurrogate
from .manager import SurrogateManager
from .strategies import UncertaintySampling, AdaptiveStrategy

__all__ = [
    "SurrogateTrainer",
    "ModelType",
    "VectorSurrogate",
    "SurrogateManager",
    "UncertaintySampling",
    "AdaptiveStrategy",
]

