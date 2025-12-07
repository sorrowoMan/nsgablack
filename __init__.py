import matplotlib
matplotlib.use("Agg")

from .core import (
    BlackBoxProblem,
    BlackBoxSolverNSGAII,
    AdvancedEliteRetention,
    DiversityAwareInitializerBlackBox,
    SphereBlackBox,
    ZDT1BlackBox,
    ExpensiveSimulationBlackBox,
    NeuralNetworkHyperparameterOptimization,
    EngineeringDesignOptimization,
    BusinessPortfolioOptimization,
    evaluate_convergence_svm,
    evaluate_convergence_cluster,
    log_and_maybe_evaluate_convergence,
)
from .utils import CallableSingleObjectiveProblem, run_headless_single_objective
from .ml import ModelManager
from .solvers import (
    SurrogateAssistedNSGAII,
    run_surrogate_assisted,
    StochasticProblem,
    DistributionSpec,
    MonteCarloEvaluator,
    MonteCarloOptimizer,
    SurrogateMonteCarloOptimizer,
    optimize_with_monte_carlo,
    optimize_with_surrogate_mc,
)

__all__ = [
    'BlackBoxProblem',
    'AdvancedEliteRetention',
    'DiversityAwareInitializerBlackBox',
    'BlackBoxSolverNSGAII',
    'CallableSingleObjectiveProblem',
    'run_headless_single_objective',
    'SphereBlackBox',
    'ZDT1BlackBox',
    'ExpensiveSimulationBlackBox',
    'NeuralNetworkHyperparameterOptimization',
    'EngineeringDesignOptimization',
    'BusinessPortfolioOptimization',
    '_get_default_convergence_log_path',
    '_append_converged_solution',
    '_load_converged_solutions',
    'evaluate_convergence_svm',
    'evaluate_convergence_cluster',
    'log_and_maybe_evaluate_convergence',
    'ModelManager',
    'SurrogateAssistedNSGAII',
    'run_surrogate_assisted',
    'StochasticProblem',
    'DistributionSpec',
    'MonteCarloEvaluator',
    'MonteCarloOptimizer',
    'SurrogateMonteCarloOptimizer',
    'optimize_with_monte_carlo',
    'optimize_with_surrogate_mc',
]
