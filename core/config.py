"""Core configuration schema (stable).

This module intentionally contains only lightweight dataclasses and should not
import optional heavy dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np


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

    pareto_solutions: np.ndarray
    pareto_objectives: np.ndarray

    generations: int
    evaluations: int
    elapsed_time: float
    converged: bool

    history: Optional[Dict[str, Any]] = None
    convergence_data: Optional[Dict[str, Any]] = None
    solver_info: Optional[Dict[str, Any]] = None

    hypervolume: Optional[float] = None
    diversity_metric: Optional[float] = None
    convergence_metric: Optional[float] = None


__all__ = ["SolverConfig", "OptimizationResult"]

