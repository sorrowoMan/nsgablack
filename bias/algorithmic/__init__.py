"""
Algorithmic bias library.

This module contains bias implementations that control search strategies
and optimization behavior at the algorithmic level.
"""

from .diversity import (
    DiversityBias,
    AdaptiveDiversityBias,
    NicheDiversityBias,
    CrowdingDistanceBias,
    SharingFunctionBias
)

from .convergence import (
    ConvergenceBias,
    AdaptiveConvergenceBias,
    PrecisionBias,
    LateStageConvergenceBias,
    MultiStageConvergenceBias
)

from .simulated_annealing import (
    SimulatedAnnealingBias,
    AdaptiveSABias,
    MultiObjectiveSABias
)

from .nsga2 import (
    NSGA2Bias,
    AdaptiveNSGA2Bias,
    DiversityPreservingNSGA2Bias
)

from .differential_evolution import (
    DifferentialEvolutionBias,
    AdaptiveDEBias,
    MultiObjectiveDEBias
)

from .pattern_search import (
    PatternSearchBias,
    AdaptivePatternSearchBias,
    CoordinateDescentBias
)

from .gradient_descent import (
    GradientDescentBias,
    MomentumGradientDescentBias,
    AdaptiveGradientDescentBias,
    AdamGradientBias
)

from .pso import (
    ParticleSwarmBias,
    AdaptivePSOBias
)

from .cma_es import (
    CMAESBias,
    AdaptiveCMAESBias
)

from .tabu_search import (
    TabuSearchBias
)

from .levy_flight import (
    LevyFlightBias
)

from .moead import (
    MOEADDecompositionBias,
    AdaptiveMOEADBias
)

from .nsga3 import (
    NSGA3ReferencePointBias,
    AdaptiveNSGA3Bias
)

from .spea2 import (
    SPEA2StrengthBias,
    AdaptiveSPEA2Bias,
    HybridSPEA2NSGA2Bias
)

from .signal_driven import (
    RobustnessBias,
)

__all__ = [
    # Diversity biases
    'DiversityBias',
    'AdaptiveDiversityBias',
    'NicheDiversityBias',
    'CrowdingDistanceBias',
    'SharingFunctionBias',

    # Convergence biases
    'ConvergenceBias',
    'AdaptiveConvergenceBias',
    'PrecisionBias',
    'LateStageConvergenceBias',
    'MultiStageConvergenceBias',

    # Simulated annealing biases
    'SimulatedAnnealingBias',
    'AdaptiveSABias',
    'MultiObjectiveSABias',

    # NSGA-II biases
    'NSGA2Bias',
    'AdaptiveNSGA2Bias',
    'DiversityPreservingNSGA2Bias',

    # Differential evolution biases
    'DifferentialEvolutionBias',
    'AdaptiveDEBias',
    'MultiObjectiveDEBias',

    # Pattern search biases
    'PatternSearchBias',
    'AdaptivePatternSearchBias',
    'CoordinateDescentBias',

    # Gradient descent biases
    'GradientDescentBias',
    'MomentumGradientDescentBias',
    'AdaptiveGradientDescentBias',
    'AdamGradientBias',

    # PSO biases
    'ParticleSwarmBias',
    'AdaptivePSOBias',

    # CMA-ES biases
    'CMAESBias',
    'AdaptiveCMAESBias',

    # Tabu search bias
    'TabuSearchBias',

    # Levy flight bias
    'LevyFlightBias',

    # MOEA/D biases
    'MOEADDecompositionBias',
    'AdaptiveMOEADBias',

    # NSGA-III biases
    'NSGA3ReferencePointBias',
    'AdaptiveNSGA3Bias',

    # SPEA2 biases
    'SPEA2StrengthBias',
    'AdaptiveSPEA2Bias',
    'HybridSPEA2NSGA2Bias',

    # Robustness biases
    'RobustnessBias',
]
