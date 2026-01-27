"""
Unified import utilities for nsgablack
This module provides clean, consistent imports throughout the codebase.
"""

import sys
import os
from typing import Optional, Any, Dict, List
import warnings


class ImportManager:
    """
    Manages imports across the nsgablack package.
    Provides consistent error handling and optional dependency management.
    """

    def __init__(self):
        self._import_cache: Dict[str, Any] = {}
        self._failed_imports: Dict[str, str] = {}
        self._optional_dependencies: Dict[str, List[str]] = {
            'visualization': ['matplotlib', 'plotly'],
            'machine_learning': ['scikit-learn', 'tensorflow', 'torch'],
            'parallel': ['joblib', 'ray', 'dask'],
            'bayesian': ['scikit-optimize', 'gpy'],
            'acceleration': ['numba', 'cython']
        }

    def safe_import(self, module_path: str,
                   attribute: Optional[str] = None,
                   fallback: Optional[Any] = None,
                   silent: bool = False) -> Any:
        """
        Safely import a module or attribute.

        Args:
            module_path: Path to module (e.g., 'numpy.linalg')
            attribute: Attribute to import from module (optional)
            fallback: Value to return if import fails
            silent: Whether to suppress warnings

        Returns:
            Imported module/attribute or fallback value
        """
        cache_key = f"{module_path}.{attribute}" if attribute else module_path

        # Check cache first
        if cache_key in self._import_cache:
            return self._import_cache[cache_key]

        if cache_key in self._failed_imports:
            if not silent:
                warnings.warn(f"Import {cache_key} previously failed: {self._failed_imports[cache_key]}")
            return fallback

        try:
            if attribute:
                module = __import__(module_path, fromlist=[attribute])
                result = getattr(module, attribute)
            else:
                result = __import__(module_path)

            self._import_cache[cache_key] = result
            return result

        except ImportError as e:
            self._failed_imports[cache_key] = str(e)
            if not silent and fallback is None:
                warnings.warn(f"Failed to import {cache_key}: {e}")
            return fallback

    def check_optional_dependency(self, feature: str) -> bool:
        """
        Check if optional dependencies for a feature are available.

        Args:
            feature: Feature name (e.g., 'visualization', 'machine_learning')

        Returns:
            True if dependencies are available
        """
        if feature not in self._optional_dependencies:
            return False

        for dep in self._optional_dependencies[feature]:
            if self.safe_import(dep) is None:
                return False
        return True

    def get_import_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status of all imports and optional features.

        Returns:
            Dictionary with import status information
        """
        status = {
            'successful_imports': list(self._import_cache.keys()),
            'failed_imports': self._failed_imports,
            'available_features': {}
        }

        for feature, deps in self._optional_dependencies.items():
            available = all(
                self.safe_import(dep) is not None
                for dep in deps
            )
            status['available_features'][feature] = {
                'available': available,
                'dependencies': deps
            }

        return status


# Global import manager instance
_import_manager = ImportManager()


# Convenience functions for common imports
def safe_import(module_path: str, attribute: Optional[str] = None,
                fallback: Optional[Any] = None) -> Any:
    """Safely import a module or attribute."""
    return _import_manager.safe_import(module_path, attribute, fallback)


def check_optional_dependency(feature: str) -> bool:
    """Check if optional dependencies for a feature are available."""
    return _import_manager.check_optional_dependency(feature)


def get_import_status() -> Dict[str, Dict[str, Any]]:
    """Get status of all imports and optional features."""
    return _import_manager.get_import_status()


# Common imports with fallbacks
def import_numpy():
    """Import numpy with fallback."""
    return safe_import('numpy')


def import_matplotlib():
    """Import matplotlib with fallback."""
    return safe_import('matplotlib')


def import_sklearn():
    """Import scikit-learn with fallback."""
    return safe_import('sklearn')


def import_numba():
    """Import numba with fallback."""
    return safe_import('numba')


def import_joblib():
    """Import joblib with fallback."""
    return safe_import('joblib')


def import_plotly():
    """Import plotly with fallback."""
    return safe_import('plotly')


# Standardized module imports
def import_core():
    """Import core modules."""
    from ..core.base import BlackBoxProblem
    from ..core.solver import BlackBoxSolverNSGAII
    from ..core.problems import (
        ZDT1BlackBox, ZDT3BlackBox, DTLZ2BlackBox,
        SphereBlackBox, ExpensiveSimulationBlackBox
    )
    return {
        'BlackBoxProblem': BlackBoxProblem,
        'BlackBoxSolverNSGAII': BlackBoxSolverNSGAII,
        'ZDT1BlackBox': ZDT1BlackBox,
        'ZDT3BlackBox': ZDT3BlackBox,
        'DTLZ2BlackBox': DTLZ2BlackBox,
        'SphereBlackBox': SphereBlackBox,
        'ExpensiveSimulationBlackBox': ExpensiveSimulationBlackBox
    }


def import_bias():
    """Import bias system modules."""
    bias_modules: Dict[str, Any] = {}

    try:
        from .. import bias as bias_pkg
    except ImportError:
        return bias_modules

    core_names = [
        'BiasBase',
        'AlgorithmicBias',
        'DomainBias',
        'OptimizationContext',
        'BiasModule',
        'DiversityBias',
        'ConvergenceBias',
        'PrecisionBias',
        'ConstraintBias',
        'PreferenceBias',
    ]
    for name in core_names:
        if hasattr(bias_pkg, name):
            bias_modules[name] = getattr(bias_pkg, name)

    try:
        from ..bias.library import BiasFactory, BiasComposer
        bias_modules['BiasFactory'] = BiasFactory
        bias_modules['BiasComposer'] = BiasComposer
    except ImportError:
        pass

    return bias_modules


def import_solvers():
    """Import solver modules."""
    from ..solvers.nsga2 import BlackBoxSolverNSGAII as SolverNSGA2
    from ..solvers.monte_carlo import MonteCarloOptimizer
    from ..solvers.bayesian_optimizer import BayesianOptimizer

    return {
        'SolverNSGA2': SolverNSGA2,
        'MonteCarloOptimizer': MonteCarloOptimizer,
        'BayesianOptimizer': BayesianOptimizer
    }


def import_utils():
    """Import utility modules."""
    from ..utils.viz import SolverVisualizationMixin
    from ..utils.parallel import ParallelEvaluator

    return {
        'SolverVisualizationMixin': SolverVisualizationMixin,
        'ParallelEvaluator': ParallelEvaluator
    }


# Error handling utilities
class ImportWarning(UserWarning):
    """Warning for import issues."""
    pass


class MissingDependencyError(ImportError):
    """Error raised when required dependencies are missing."""

    def __init__(self, dependency: str, feature: str = None):
        self.dependency = dependency
        self.feature = feature
        message = f"Missing required dependency: {dependency}"
        if feature:
            message += f" for feature: {feature}"
        super().__init__(message)


# Environment detection
def is_jupyter_notebook() -> bool:
    """Check if running in Jupyter notebook."""
    try:
        from IPython import get_ipython
        if 'IPKernelApp' in get_ipython().config:
            return True
    except ImportError:
        pass
    return False


def is_headless() -> bool:
    """Check if running in headless environment."""
    import os
    return (
        os.environ.get('DISPLAY') is None and
        os.environ.get('SSH_TTY') is None and
        not is_jupyter_notebook()
    )


# Path utilities
def get_package_root() -> str:
    """Get the root directory of the nsgablack package."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def add_to_path(path: str) -> None:
    """Add a path to sys.path if not already present."""
    if path not in sys.path:
        sys.path.insert(0, path)
