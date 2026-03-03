"""
Algorithmic bias library (scalar preference biases only).

Process-level algorithm mechanisms should be implemented as adapters
under ``nsgablack.adapters``.
"""

from .diversity import (
    DiversityBias,
    AdaptiveDiversityBias,
    NicheDiversityBias,
    CrowdingDistanceBias,
    SharingFunctionBias,
)
from .convergence import (
    ConvergenceBias,
    AdaptiveConvergenceBias,
    PrecisionBias,
    LateStageConvergenceBias,
    MultiStageConvergenceBias,
)
from .pso import ParticleSwarmBias, AdaptivePSOBias
from .cma_es import CMAESBias, AdaptiveCMAESBias
from .tabu_search import TabuSearchBias
from .levy_flight import LevyFlightBias
from .signal_driven import RobustnessBias, UncertaintyExplorationBias

__all__ = [
    "DiversityBias",
    "AdaptiveDiversityBias",
    "NicheDiversityBias",
    "CrowdingDistanceBias",
    "SharingFunctionBias",
    "ConvergenceBias",
    "AdaptiveConvergenceBias",
    "PrecisionBias",
    "LateStageConvergenceBias",
    "MultiStageConvergenceBias",
    "ParticleSwarmBias",
    "AdaptivePSOBias",
    "CMAESBias",
    "AdaptiveCMAESBias",
    "TabuSearchBias",
    "LevyFlightBias",
    "RobustnessBias",
    "UncertaintyExplorationBias",
]
