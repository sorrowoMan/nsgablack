"""
Base solver class for unified API across all optimization algorithms
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Tuple, Union
from pathlib import Path
import numpy as np
from dataclasses import dataclass

from .base import BlackBoxProblem
from ....utils.runtime.imports import safe_import, check_optional_dependency
from ....utils.engineering.config_loader import build_dataclass_config, ConfigError, load_config


# Optional imports
pd = safe_import('pandas')
matplotlib = safe_import('matplotlib.pyplot')
plotly = safe_import('plotly.graph_objects')


@dataclass
class SolverConfig:
    """Configuration class for solvers."""
    # Basic parameters
    max_generations: int = 100
    pop_size: int = 100
    random_seed: Optional[int] = None

    # Algorithm-specific parameters
    crossover_rate: float = 0.9
    mutation_rate: float = 0.1
    selection_pressure: float = 2.0

    # Performance parameters
    evaluation_budget: Optional[int] = None
    time_limit: Optional[float] = None
    parallel: bool = False
    n_workers: int = 1

    # Output parameters
    verbose: bool = False
    save_history: bool = True
    convergence_tolerance: float = 1e-6
    stagnation_generations: int = 20


@dataclass
class OptimizationResult:
    """Standard result structure for all solvers."""
    # Solutions
    pareto_solutions: np.ndarray
    pareto_objectives: np.ndarray

    # Metadata
    generations: int
    evaluations: int
    elapsed_time: float
    converged: bool

    # Optional data
    history: Optional[Dict[str, Any]] = None
    convergence_data: Optional[Dict[str, Any]] = None
    solver_info: Optional[Dict[str, Any]] = None

    # Performance metrics
    hypervolume: Optional[float] = None
    diversity_metric: Optional[float] = None
    convergence_metric: Optional[float] = None


class BaseSolver(ABC):
    """
    Abstract base class for all optimization solvers.
    Provides unified interface and common functionality.
    """

    def __init__(
        self,
        problem: BlackBoxProblem,
        config: Optional[Union[SolverConfig, Dict[str, Any], str, Path]] = None,
    ):
        """
        Initialize solver with problem and configuration.

        Args:
            problem: Optimization problem to solve
            config: Solver configuration (optional)
        """
        self.problem = problem
        self.config = self._normalize_config(config)

        # Set random seed if specified
        if self.config.random_seed is not None:
            np.random.seed(self.config.random_seed)

        # Internal state
        self._current_generation = 0
        self._evaluation_count = 0
        self._start_time = None
        self._best_objectives = None
        self._converged = False
        self._stagnation_count = 0

        # History tracking
        self.history = {
            'objectives': [],
            'solutions': [],
            'fitness': [],
            'diversity': [],
            'convergence': []
        }

        # Optional features
        self._bias_module = None
        self._parallel_evaluator = None
        self._memory_optimizer = None

        # Initialize solver-specific components
        self._initialize()

    @abstractmethod
    def _initialize(self) -> None:
        """Initialize solver-specific components."""
        pass

    def _normalize_config(
        self,
        config: Optional[Union[SolverConfig, Dict[str, Any], str, Path]],
    ) -> SolverConfig:
        if isinstance(config, SolverConfig):
            return config
        if isinstance(config, (dict, str, Path)):
            try:
                config_data = load_config(config)
                built, unknown = build_dataclass_config(SolverConfig, config_data, strict=False)
                if unknown:
                    print(f"Warning: Unknown config keys: {', '.join(sorted(unknown))}")
                return built
            except ConfigError as exc:
                print(f"Warning: Failed to load config: {exc}")
        return SolverConfig()

    @abstractmethod
    def _evolve_generation(self) -> None:
        """Perform one generation of evolution."""
        pass

    @abstractmethod
    def _evaluate_population(self, population: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Evaluate population fitness and constraints.

        Args:
            population: Population to evaluate

        Returns:
            Tuple of (objectives, constraint_violations)
        """
        pass

    def optimize(self) -> OptimizationResult:
        """
        Run the optimization process.

        Returns:
            OptimizationResult with solution and metadata
        """
        import time
        self._start_time = time.time()

        try:
            # Run optimization loop
            while not self._should_terminate():
                self._evolve_generation()
                self._update_history()
                self._check_convergence()
                self._current_generation += 1

            # Finalize and return results
            return self._create_result()

        except KeyboardInterrupt:
            print("Optimization interrupted by user")
            return self._create_result()
        except Exception as e:
            raise RuntimeError(f"Optimization failed: {e}") from e

    def _should_terminate(self) -> bool:
        """Check if optimization should terminate."""
        # Check generation limit
        if self._current_generation >= self.config.max_generations:
            return True

        # Check evaluation budget
        if (self.config.evaluation_budget is not None and
            self._evaluation_count >= self.config.evaluation_budget):
            return True

        # Check time limit
        if self.config.time_limit is not None:
            import time
            if time.time() - self._start_time > self.config.time_limit:
                return True

        # Check convergence
        if self._converged:
            return True

        return False

    def _update_history(self) -> None:
        """Update optimization history."""
        if not self.config.save_history:
            return

        # Get current best solutions
        current_pareto = self._get_pareto_front()
        if current_pareto is not None:
            objectives = current_pareto['objectives']
            solutions = current_pareto['solutions']

            self.history['objectives'].append(objectives)
            self.history['solutions'].append(solutions)

            # Calculate diversity and convergence metrics
            if len(objectives) > 1:
                diversity = self._calculate_diversity(objectives)
                convergence = self._calculate_convergence(objectives)

                self.history['diversity'].append(diversity)
                self.history['convergence'].append(convergence)

    def _check_convergence(self) -> None:
        """Check for convergence."""
        if len(self.history['convergence']) < 2:
            return

        current_convergence = self.history['convergence'][-1]
        previous_convergence = self.history['convergence'][-2]

        # Check if improvement is below tolerance
        if abs(current_convergence - previous_convergence) < self.config.convergence_tolerance:
            self._stagnation_count += 1
        else:
            self._stagnation_count = 0

        # Check stagnation
        if self._stagnation_count >= self.config.stagnation_generations:
            self._converged = True
            if self.config.verbose:
                print(f"Converged after {self._current_generation} generations")

    def _get_pareto_front(self) -> Optional[Dict[str, np.ndarray]]:
        """Get current Pareto front."""
        # This should be implemented by subclasses
        # Provide a basic implementation for now
        return None

    def _calculate_diversity(self, objectives: np.ndarray) -> float:
        """Calculate diversity metric."""
        if len(objectives) < 2:
            return 0.0

        # Simple diversity measure: average distance between solutions
        distances = []
        for i in range(len(objectives)):
            for j in range(i + 1, len(objectives)):
                dist = np.linalg.norm(objectives[i] - objectives[j])
                distances.append(dist)

        return np.mean(distances) if distances else 0.0

    def _calculate_convergence(self, objectives: np.ndarray) -> float:
        """Calculate convergence metric."""
        if len(objectives) == 0:
            return float('inf')

        # Simple convergence measure: distance to ideal point
        ideal_point = np.min(objectives, axis=0)
        distances = [np.linalg.norm(obj - ideal_point) for obj in objectives]
        return np.mean(distances)

    def _create_result(self) -> OptimizationResult:
        """Create optimization result."""
        import time

        pareto_data = self._get_pareto_front()
        if pareto_data is None:
            # Fallback: return empty results
            pareto_data = {
                'solutions': np.array([]),
                'objectives': np.array([])
            }

        elapsed_time = time.time() - self._start_time if self._start_time else 0.0

        # Calculate performance metrics
        hypervolume = self._calculate_hypervolume(pareto_data['objectives'])
        diversity = self._calculate_diversity(pareto_data['objectives'])
        convergence = self._calculate_convergence(pareto_data['objectives'])

        result = OptimizationResult(
            pareto_solutions=pareto_data['solutions'],
            pareto_objectives=pareto_data['objectives'],
            generations=self._current_generation,
            evaluations=self._evaluation_count,
            elapsed_time=elapsed_time,
            converged=self._converged,
            history=self.history if self.config.save_history else None,
            solver_info={
                'algorithm': self.__class__.__name__,
                'config': self.config,
                'problem': type(self.problem).__name__
            },
            hypervolume=hypervolume,
            diversity_metric=diversity,
            convergence_metric=convergence
        )

        return result

    def _calculate_hypervolume(self, objectives: np.ndarray) -> Optional[float]:
        """Calculate hypervolume indicator."""
        if len(objectives) == 0:
            return 0.0

        # For 2D problems, use simple calculation
        if objectives.shape[1] == 2:
            # Reference point (worse than all objectives)
            ref_point = np.max(objectives, axis=0) * 1.1

            # Sort by first objective
            sorted_idx = np.argsort(objectives[:, 0])
            sorted_obj = objectives[sorted_idx]

            volume = 0.0
            for i in range(len(sorted_obj)):
                if i == 0:
                    volume += (ref_point[0] - sorted_obj[i, 0]) * (ref_point[1] - sorted_obj[i, 1])
                else:
                    volume += (ref_point[0] - sorted_obj[i, 0]) * (sorted_obj[i-1, 1] - sorted_obj[i, 1])

            return volume

        # For higher dimensions, we could use pymoo or other libraries
        # For now, return None
        return None

    # Visualization methods
    def plot_pareto_front(self, save_path: Optional[str] = None) -> None:
        """Plot Pareto front."""
        if not check_optional_dependency('visualization'):
            print("Visualization dependencies not available")
            return

        pareto_data = self._get_pareto_front()
        if pareto_data is None or len(pareto_data['objectives']) == 0:
            print("No Pareto solutions to plot")
            return

        objectives = pareto_data['objectives']

        if objectives.shape[1] == 2:
            # 2D plot
            if matplotlib is not None:
                import matplotlib.pyplot as plt
                plt.figure(figsize=(10, 6))
                plt.scatter(objectives[:, 0], objectives[:, 1], alpha=0.7)
                plt.xlabel('Objective 1')
                plt.ylabel('Objective 2')
                plt.title('Pareto Front')
                plt.grid(True, alpha=0.3)

                if save_path:
                    plt.savefig(save_path, dpi=300, bbox_inches='tight')
                else:
                    plt.show()
        elif objectives.shape[1] == 3 and plotly is not None:
            # 3D interactive plot
            import plotly.graph_objects as go
            fig = go.Figure(data=[go.Scatter3d(
                x=objectives[:, 0],
                y=objectives[:, 1],
                z=objectives[:, 2],
                mode='markers',
                marker=dict(size=5)
            )])
            fig.update_layout(
                title='Pareto Front (3D)',
                scene=dict(
                    xaxis_title='Objective 1',
                    yaxis_title='Objective 2',
                    zaxis_title='Objective 3'
                )
            )

            if save_path:
                fig.write_html(save_path)
            else:
                fig.show()

    def plot_convergence_history(self, save_path: Optional[str] = None) -> None:
        """Plot convergence history."""
        if not check_optional_dependency('visualization') or matplotlib is None:
            print("Visualization dependencies not available")
            return

        import matplotlib.pyplot as plt

        if len(self.history['convergence']) == 0:
            print("No convergence history to plot")
            return

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))

        # Convergence plot
        ax1.plot(self.history['convergence'])
        ax1.set_xlabel('Generation')
        ax1.set_ylabel('Convergence Metric')
        ax1.set_title('Convergence History')
        ax1.grid(True, alpha=0.3)

        # Diversity plot
        if len(self.history['diversity']) > 0:
            ax2.plot(self.history['diversity'])
            ax2.set_xlabel('Generation')
            ax2.set_ylabel('Diversity Metric')
            ax2.set_title('Diversity History')
            ax2.grid(True, alpha=0.3)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        else:
            plt.show()

    # Configuration methods
    def set_config(self, **kwargs) -> None:
        """Update solver configuration."""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
            else:
                print(f"Warning: Unknown config parameter: {key}")

    def get_config(self) -> SolverConfig:
        """Get current solver configuration."""
        return self.config

    # Bias system integration
    def set_bias_module(self, bias_module) -> None:
        """Set bias module for optimization."""
        self._bias_module = bias_module

    def enable_memory_optimization(self, enable: bool = True) -> None:
        """Enable/disable memory optimization."""
        if enable and self._memory_optimizer is None:
            try:
                from ....utils.performance.memory_manager import OptimizationMemoryOptimizer
                self._memory_optimizer = OptimizationMemoryOptimizer(self)
            except ImportError:
                print("Memory optimization not available")

    def enable_parallel_evaluation(self, enable: bool = True, n_workers: int = None, **parallel_kwargs) -> None:
        """Enable/disable parallel evaluation."""
        if enable and self._parallel_evaluator is None:
            try:
                from ..utils.parallel import ParallelEvaluator
                self._parallel_evaluator = ParallelEvaluator(
                    max_workers=n_workers or self.config.n_workers,
                    **parallel_kwargs,
                )
            except ImportError:
                print("Parallel evaluation not available")
