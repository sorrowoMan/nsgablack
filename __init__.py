"""
nsgablack: A comprehensive multi-objective optimization framework
"""

__version__ = "2.1.0"
__author__ = "SorrowoMan"
__email__ = "sorrowo@foxmail.com"

import matplotlib
matplotlib.use("Agg")

# Core imports - provide clean API for users
from .core.base import BlackBoxProblem
from .core.solver import BlackBoxSolverNSGAII
from .core.problems import (
    ZDT1BlackBox, ZDT3BlackBox, DTLZ2BlackBox,
    SphereBlackBox, ExpensiveSimulationBlackBox,
    NeuralNetworkHyperparameterOptimization,
    EngineeringDesignOptimization,
    BusinessPortfolioOptimization
)

# Bias system imports
try:
    from .bias.bias_base import (
        BaseBias, AlgorithmicBias, DomainBias, OptimizationContext
    )
    from .bias.bias_library_algorithmic import (
        DiversityBias, ConvergenceBias, ExplorationBias
    )
    from .bias.bias_library_domain import (
        ConstraintBias, PreferenceBias, EngineeringDesignBias
    )
    from .bias.bias import BiasModule
    _HAS_BIAS = True
except ImportError:
    _HAS_BIAS = False

# Solver imports
from .solvers.nsga2 import BlackBoxSolverNSGAII as SolverNSGA2
from .solvers.monte_carlo import MonteCarloOptimizer, optimize_with_monte_carlo
from .solvers.surrogate import SurrogateAssistedNSGAII, run_surrogate_assisted
from .solvers.surrogate_interface import SurrogateUnifiedNSGAII

# Utility imports
from .utils.visualization import SolverVisualizationMixin
from .utils.parallel_evaluator import ParallelEvaluator
from .utils import (
    CallableSingleObjectiveProblem,
    run_headless_single_objective
)

# Machine learning imports
try:
    from .ml import ModelManager
    _HAS_ML = True
except ImportError:
    _HAS_ML = False

# Define what gets imported with "from nsgablack import *"
__all__ = [
    # Version info
    '__version__',

    # Core classes
    'BlackBoxProblem',
    'BlackBoxSolverNSGAII',
    'SolverNSGA2',

    # Problems
    'ZDT1BlackBox',
    'ZDT3BlackBox',
    'DTLZ2BlackBox',
    'SphereBlackBox',
    'ExpensiveSimulationBlackBox',
    'NeuralNetworkHyperparameterOptimization',
    'EngineeringDesignOptimization',
    'BusinessPortfolioOptimization',

    # Solvers and optimizers
    'MonteCarloOptimizer',
    'SurrogateAssistedNSGAII',
    'SurrogateUnifiedNSGAII',

    # Utils
    'SolverVisualizationMixin',
    'ParallelEvaluator',
    'CallableSingleObjectiveProblem',
    'run_headless_single_objective',
    'AdvancedEliteRetention',
    'DiversityAwareInitializerBlackBox',
    'evaluate_convergence_svm',
    'evaluate_convergence_cluster',
    'log_and_maybe_evaluate_convergence',

    # Convenience functions
    'optimize_with_monte_carlo',
    'run_surrogate_assisted'
]

# Add bias system to __all__ if available
if _HAS_BIAS:
    __all__.extend([
        'BaseBias', 'AlgorithmicBias', 'DomainBias', 'OptimizationContext',
        'DiversityBias', 'ConvergenceBias', 'ExplorationBias',
        'ConstraintBias', 'PreferenceBias', 'EngineeringDesignBias',
        'BiasModule'
    ])

# Add ML module to __all__ if available
if _HAS_ML:
    __all__.append('ModelManager')

# Package metadata
_PACKAGE_INFO = {
    'name': 'nsgablack',
    'description': 'A comprehensive multi-objective optimization framework with bias system',
    'long_description': '''
    nsgablack is a powerful multi-objective optimization framework featuring:
    - Advanced bias system for domain knowledge integration
    - Multiple optimization algorithms (NSGA-II, MOEA/D, Bayesian, etc.)
    - Machine learning guided optimization
    - Parallel computation support
    - Memory optimization
    - Comprehensive visualization tools
    ''',
    'url': 'https://github.com/yourusername/nsgablack',
    'author': 'SorrowoMan',
    'author_email': 'sorrowo@foxmail.com',
    'license': 'MIT',
    'python_requires': '>=3.8',
    'classifiers': [
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Topic :: Scientific/Engineering :: Artificial Intelligence',
        'Topic :: Scientific/Engineering :: Mathematics',
    ],
    'keywords': [
        'optimization', 'multi-objective', 'nsga-ii',
        'evolutionary-algorithms', 'bias-system', 'machine-learning'
    ]
}

def get_version():
    """Get package version."""
    return __version__

def get_package_info():
    """Get package metadata."""
    return _PACKAGE_INFO.copy()

def get_available_features():
    """Get information about available optional features."""
    return {
        'bias_system': _HAS_BIAS,
        'machine_learning': _HAS_ML,
        'parallel_computation': True,
        'visualization': True,
        'memory_optimization': True
    }
