"""Interfaces and optional module hooks for solver integration.

These Protocols standardize extension points so components can be injected
without hard dependencies.
"""

from typing import Protocol, Any, Optional, List, Dict
import logging
import numpy as np

logger = logging.getLogger(__name__)


class OptimizationContext(Protocol):
    """Optimization context passed to biases/plugins."""

    generation: int
    population: List[np.ndarray]
    objectives: List[np.ndarray]
    best_individual: Optional[np.ndarray]
    best_objective: Optional[float]

    def get_statistics(self) -> Dict[str, float]:
        """Return summary statistics."""
        ...


class BiasInterface(Protocol):
    """Bias module interface."""

    def compute_bias(self, x: np.ndarray, context: Any) -> float:
        """Compute bias value for a candidate."""
        ...

    def add_bias(self, bias: Any, weight: float = 1.0, name: Optional[str] = None) -> bool:
        """Register a bias component."""
        ...

    def is_enabled(self) -> bool:
        """Return whether bias module is enabled."""
        ...

    def enable(self) -> None:
        """Enable bias module."""
        ...

    def disable(self) -> None:
        """Disable bias module."""
        ...


class RepresentationInterface(Protocol):
    """Representation/pipeline interface."""

    def init(self, problem: Any, context: Optional[Any] = None) -> np.ndarray:
        """Initialize a single candidate (RepresentationPipeline.init)."""
        ...

    def initialize(self, problem: Any, pop_size: int, context: Optional[Any] = None) -> List[np.ndarray]:
        """Initialize a population."""
        ...

    def mutate(self, x: np.ndarray, context: Optional[Any] = None) -> np.ndarray:
        """Mutate a candidate."""
        ...

    def repair(self, x: np.ndarray, context: Optional[Any] = None) -> np.ndarray:
        """Repair a candidate (hard constraints)."""
        ...

    def encode(self, x: Any, context: Optional[Any] = None) -> np.ndarray:
        """Encode a candidate."""
        ...

    def decode(self, x: np.ndarray, context: Optional[Any] = None) -> Any:
        """Decode a candidate."""
        ...


class VisualizationInterface(Protocol):
    """Visualization mixin interface."""

    def plot_pareto_front(
        self,
        solutions: List[np.ndarray],
        objectives: List[np.ndarray],
        save_path: Optional[str] = None,
    ) -> None:
        """Plot Pareto front."""
        ...

    def plot_convergence(self, history: List[float], save_path: Optional[str] = None) -> None:
        """Plot convergence curve."""
        ...

    def plot_diversity(self, population: List[np.ndarray], save_path: Optional[str] = None) -> None:
        """Plot population diversity."""
        ...


class PluginInterface(Protocol):
    """Plugin lifecycle interface."""

    def on_solver_init(self, solver: Any) -> None:
        ...

    def on_population_init(self, population: Any, objectives: Any, violations: Any) -> None:
        ...

    def on_generation_start(self, generation: int) -> None:
        ...

    def on_generation_end(self, generation: int) -> None:
        ...

    def on_step(self, solver: Any, generation: int) -> None:
        ...

    def on_solver_finish(self, result: Dict[str, Any]) -> None:
        ...


class ExperimentResultInterface(Protocol):
    """Structured experiment result container."""

    def add_result(self, key: str, value: Any) -> None:
        ...

    def save(self, path: str) -> None:
        ...

    def to_dict(self) -> Dict[str, Any]:
        ...


def has_bias_module() -> bool:
    """Return True if bias module is available."""
    try:
        from ..bias import BiasModule
        return True
    except ImportError:
        return False


def has_representation_module() -> bool:
    """Return True if representation module is available."""
    try:
        from ..representation import RepresentationPipeline  # noqa: F401
        return True
    except ImportError:
        return False


def has_visualization_module() -> bool:
    """Return True if visualization module is available."""
    try:
        import matplotlib  # noqa: F401
        from ..utils.viz import SolverVisualizationMixin  # noqa: F401
        return True
    except ImportError:
        return False


def has_numba() -> bool:
    """Return True if numba is available."""
    try:
        import numba  # noqa: F401
        return True
    except Exception as exc:
        logger.debug("Optional dependency numba unavailable; fallback to non-numba path: %s", exc)
        return False


def load_bias_module() -> Optional["BiasInterface"]:
    """Load bias module if available."""
    try:
        from ..bias import BiasModule
        return BiasModule()
    except ImportError:
        return None


def load_representation_pipeline(config: Optional[Dict] = None) -> Optional["RepresentationInterface"]:
    """Load representation pipeline (optionally with config)."""
    try:
        from ..representation import RepresentationPipeline
        if config:
            return RepresentationPipeline(**config)
        return RepresentationPipeline()
    except ImportError:
        return None


def create_bias_context(
    generation: int,
    population: List[np.ndarray],
    objectives: List[np.ndarray],
    best_individual: Optional[np.ndarray] = None,
    best_objective: Optional[float] = None,
) -> Any:
    """Create a minimal bias context object."""

    class SimpleContext:
        def __init__(self):
            self.generation = generation
            self.population = population
            self.objectives = objectives
            self.best_individual = best_individual
            self.best_objective = best_objective

        def get_statistics(self):
            return {
                "generation": generation,
                "population_size": len(population),
                "best_objective": best_objective,
            }

    return SimpleContext()


BiasModuleType = BiasInterface
RepresentationPipelineType = RepresentationInterface
VisualizationMixinType = VisualizationInterface
PluginType = PluginInterface


__all__ = [
    "OptimizationContext",
    "BiasInterface",
    "RepresentationInterface",
    "VisualizationInterface",
    "PluginInterface",
    "ExperimentResultInterface",
    "has_bias_module",
    "has_representation_module",
    "has_visualization_module",
    "has_numba",
    "load_bias_module",
    "load_representation_pipeline",
    "create_bias_context",
    "BiasModuleType",
    "RepresentationPipelineType",
    "VisualizationMixinType",
    "PluginType",
]
