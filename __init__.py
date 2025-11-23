if __name__ == "__main__" and __package__ is None:
    import os
    import sys
    import importlib.util

    # Allow running this module directly by simulating package context.
    _pkg_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.dirname(_pkg_dir))
    __package__ = os.path.basename(_pkg_dir)
    __path__ = [_pkg_dir]
    sys.modules[__package__] = sys.modules[__name__]
    __spec__ = importlib.util.spec_from_file_location(__package__, __file__, submodule_search_locations=[_pkg_dir])
import matplotlib
matplotlib.use("Agg")  # 非交互式后端，不用 Tk
from .base import BlackBoxProblem
from .elite import AdvancedEliteRetention
from .diversity import DiversityAwareInitializerBlackBox
from .solver import BlackBoxSolverNSGAII
from .headless import CallableSingleObjectiveProblem, run_headless_single_objective
from .problems import (
    SphereBlackBox,
    ZDT1BlackBox,
    ExpensiveSimulationBlackBox,
    NeuralNetworkHyperparameterOptimization,
    EngineeringDesignOptimization,
    BusinessPortfolioOptimization,
)
from .convergence import (
    _get_default_convergence_log_path,
    _append_converged_solution,
    _load_converged_solutions,
    evaluate_convergence_svm,
    evaluate_convergence_cluster,
    log_and_maybe_evaluate_convergence,
)
from .ml_models import ModelManager

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
]
