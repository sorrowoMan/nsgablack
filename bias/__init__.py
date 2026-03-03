from __future__ import annotations

"""
Bias package public API.

Only scalar preference biases are exported from this package.
Process-level algorithm mechanisms should be integrated as adapters
under ``nsgablack.adapters``.
"""

from .core.base import BiasBase, AlgorithmicBias, DomainBias, OptimizationContext, create_bias
from .core.manager import UniversalBiasManager, AlgorithmicBiasManager, DomainBiasManager
from .core.registry import (
    BiasRegistry,
    get_bias_registry,
    register_algorithmic_bias,
    register_domain_bias,
    register_bias_factory,
)

from .algorithmic import (
    DiversityBias,
    AdaptiveDiversityBias,
    NicheDiversityBias,
    CrowdingDistanceBias,
    SharingFunctionBias,
    ConvergenceBias,
    AdaptiveConvergenceBias,
    PrecisionBias,
    LateStageConvergenceBias,
    MultiStageConvergenceBias,
    ParticleSwarmBias,
    AdaptivePSOBias,
    CMAESBias,
    AdaptiveCMAESBias,
    TabuSearchBias,
    LevyFlightBias,
    RobustnessBias,
    UncertaintyExplorationBias,
)
from .domain import (
    ConstraintBias,
    FeasibilityBias,
    PreferenceBias,
    RuleBasedBias,
    CallableBias,
    DynamicPenaltyBias,
    StructurePriorBias,
    RiskBias,
)

__version__ = "2.1.0"
NEW_STRUCTURE_AVAILABLE = True

try:
    from .bias_module import (
        BiasModule,
        create_bias_module,
        from_universal_manager,
        proximity_reward,
        improvement_reward,
    )
except Exception:  # pragma: no cover
    BiasModule = None
    create_bias_module = None
    from_universal_manager = None
    proximity_reward = None
    improvement_reward = None

__all__ = [
    "BiasBase",
    "AlgorithmicBias",
    "DomainBias",
    "OptimizationContext",
    "create_bias",
    "UniversalBiasManager",
    "AlgorithmicBiasManager",
    "DomainBiasManager",
    "BiasRegistry",
    "get_bias_registry",
    "register_algorithmic_bias",
    "register_domain_bias",
    "register_bias_factory",
    "BiasModule",
    "create_bias_module",
    "from_universal_manager",
    "proximity_reward",
    "improvement_reward",
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
    "ConstraintBias",
    "FeasibilityBias",
    "PreferenceBias",
    "RuleBasedBias",
    "CallableBias",
    "DynamicPenaltyBias",
    "StructurePriorBias",
    "RiskBias",
]
