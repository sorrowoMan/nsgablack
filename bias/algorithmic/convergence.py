"""
Convergence bias implementations.

These biases guide the search toward convergence, balancing exploration
and exploitation based on the current optimization stage.
"""

import numpy as np
from typing import List, Optional
from ..core.base import AlgorithmicBias, OptimizationContext


class ConvergenceBias(AlgorithmicBias):
    """
    Standard convergence bias that varies strength based on optimization stage.

    Increases bias as optimization progresses to accelerate convergence.
    """
    context_requires = ("generation", "population")
    requires_metrics = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Algorithmic bias: reads metrics and outputs scalar guidance."


    def __init__(self, weight: float = 0.1, early_gen: int = 10, late_gen: int = 50):
        super().__init__("convergence", weight, adaptive=True)
        self.early_gen = early_gen
        self.late_gen = late_gen

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        gen = context.generation

        if gen < self.early_gen:
            # Early stage - minimal convergence bias
            stage_factor = 0.1
        elif gen < self.late_gen:
            # Middle stage - gradual increase
            progress = (gen - self.early_gen) / (self.late_gen - self.early_gen)
            stage_factor = 0.1 + 0.9 * progress
        else:
            # Late stage - maximum convergence bias
            stage_factor = 1.0

        return self.weight * stage_factor * self._calculate_convergence_direction(x, context)

    def _calculate_convergence_direction(self, x: np.ndarray, context: OptimizationContext) -> float:
        """Calculate convergence direction bias."""
        # For simplicity, use distance to center of population
        if len(context.population) > 0:
            population_center = np.mean(context.population, axis=0)
            distance_to_center = np.linalg.norm(x - population_center)
            # Reward individuals closer to population center (convergence)
            return 1.0 / (1.0 + distance_to_center)
        return 0.0


class AdaptiveConvergenceBias(AlgorithmicBias):
    """
    Adaptive convergence bias that adjusts based on convergence rate.

    Monitors improvement rate and adjusts convergence bias accordingly.
    """
    context_requires = ()
    requires_metrics = ("best_fitness", "elite_solutions")
    metrics_fallback = "default"
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Algorithmic bias: reads metrics and outputs scalar guidance."


    def __init__(
        self,
        weight: float = 0.15,
        window_size: int = 10,
        improvement_threshold: float = 0.01
    ):
        super().__init__("adaptive_convergence", weight, adaptive=True)
        self.window_size = window_size
        self.improvement_threshold = improvement_threshold
        self.fitness_history = []

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        # Get current fitness from context metrics
        current_fitness = context.metrics.get('best_fitness', 0.0)
        self.fitness_history.append(current_fitness)

        # Calculate improvement rate
        improvement_rate = self._calculate_improvement_rate()

        # Adapt weight based on improvement
        if improvement_rate < self.improvement_threshold:
            # Slow improvement - increase convergence bias
            adapted_weight = self.weight * 1.5
        else:
            # Good improvement - normal convergence bias
            adapted_weight = self.weight

        return adapted_weight * self._calculate_convergence_value(x, context)

    def _calculate_improvement_rate(self) -> float:
        """Calculate rate of improvement over recent history."""
        if len(self.fitness_history) < self.window_size:
            return float('inf')  # Not enough history

        recent_window = self.fitness_history[-self.window_size:]
        if len(recent_window) < 2:
            return float('inf')

        # Calculate relative improvement
        initial_fitness = recent_window[0]
        final_fitness = recent_window[-1]

        if initial_fitness == 0:
            return 0.0

        improvement = (initial_fitness - final_fitness) / abs(initial_fitness)
        return improvement / self.window_size

    def _calculate_convergence_value(self, x: np.ndarray, context: OptimizationContext) -> float:
        """Calculate convergence value based on position relative to elite solutions."""
        # Simple implementation: reward proximity to best solutions
        best_solutions = context.metrics.get('elite_solutions', [])
        if len(best_solutions) > 0:
            min_distance = min(np.linalg.norm(x - elite) for elite in best_solutions)
            return 1.0 / (1.0 + min_distance)
        return 0.0


class PrecisionBias(AlgorithmicBias):
    """
    Precision bias for fine-grained search around good solutions.

    Encourages precise exploration in promising regions.
    """
    context_requires = ()
    requires_metrics = ("best_fitness", "current_fitness")
    metrics_fallback = "default"
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Algorithmic bias: reads metrics and outputs scalar guidance."


    def __init__(self, weight: float = 0.1, precision_radius: float = 0.05):
        super().__init__("precision", weight, adaptive=True)
        self.precision_radius = precision_radius

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        # Check if individual is in a promising region
        is_promising = self._is_promising_region(x, context)

        if is_promising:
            # Apply precision bias in promising regions
            return self.weight * self._calculate_precision_value(x, context)
        return 0.0

    def _is_promising_region(self, x: np.ndarray, context: OptimizationContext) -> bool:
        """Check if individual is in a promising region."""
        best_fitness = context.metrics.get('best_fitness', float('inf'))
        current_fitness = context.metrics.get('current_fitness', float('inf'))

        # Consider region promising if close to best fitness
        if best_fitness != float('inf') and current_fitness != float('inf'):
            relative_fitness = abs(current_fitness - best_fitness) / max(1.0, abs(best_fitness))
            return relative_fitness < 0.1  # Within 10% of best fitness
        return False

    def _calculate_precision_value(self, x: np.ndarray, context: OptimizationContext) -> float:
        """Calculate precision value based on local exploration."""
        # Reward fine-grained movements in promising regions
        return 1.0


class LateStageConvergenceBias(AlgorithmicBias):
    """
    Convergence bias specifically for late optimization stages.

    Strongly promotes convergence in final generations.
    """
    context_requires = ("generation",)
    requires_metrics = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Algorithmic bias: reads metrics and outputs scalar guidance."


    def __init__(
        self,
        weight: float = 0.2,
        activation_gen: int = 70,
        max_gen: int = 100
    ):
        super().__init__("late_stage_convergence", weight, adaptive=True)
        self.activation_gen = activation_gen
        self.max_gen = max_gen

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        gen = context.generation

        if gen < self.activation_gen:
            return 0.0  # Not activated yet

        # Calculate activation strength (increases rapidly in late stage)
        progress = (gen - self.activation_gen) / (self.max_gen - self.activation_gen)
        activation_strength = progress ** 2  # Quadratic increase

        return self.weight * activation_strength * self._calculate_intensity(x, context)

    def _calculate_intensity(self, x: np.ndarray, context: OptimizationContext) -> float:
        """Calculate convergence intensity."""
        # Intensify convergence pressure in late stage
        return 1.0


class MultiStageConvergenceBias(AlgorithmicBias):
    """
    Multi-stage convergence bias with different strategies per stage.

    Implements different convergence strategies for different optimization phases.
    """
    context_requires = ("generation",)
    requires_metrics = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Algorithmic bias: reads metrics and outputs scalar guidance."


    def __init__(self, weight: float = 0.15, stages: Optional[List[dict]] = None):
        super().__init__("multi_stage_convergence", weight, adaptive=True)
        self.stages = stages or [
            {'end_gen': 20, 'strategy': 'exploration', 'factor': 0.2},
            {'end_gen': 50, 'strategy': 'balanced', 'factor': 0.5},
            {'end_gen': 80, 'strategy': 'exploitation', 'factor': 0.8},
            {'end_gen': 100, 'strategy': 'convergence', 'factor': 1.2}
        ]

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        gen = context.generation
        current_stage = self._get_current_stage(gen)

        if current_stage is None:
            return 0.0

        stage_factor = current_stage['factor']
        strategy = current_stage['strategy']

        base_bias = self._calculate_strategy_bias(strategy, x, context)
        return self.weight * stage_factor * base_bias

    def _get_current_stage(self, generation: int) -> Optional[dict]:
        """Get current optimization stage."""
        for stage in self.stages:
            if generation <= stage['end_gen']:
                return stage
        return self.stages[-1] if self.stages else None

    def _calculate_strategy_bias(self, strategy: str, x: np.ndarray, context: OptimizationContext) -> float:
        """Calculate bias based on strategy."""
        if strategy == 'exploration':
            return 0.1  # Minimal convergence bias
        elif strategy == 'balanced':
            return 0.5  # Moderate convergence bias
        elif strategy == 'exploitation':
            return 0.8  # Strong convergence bias
        elif strategy == 'convergence':
            return 1.0  # Maximum convergence bias
        else:
            return 0.5
